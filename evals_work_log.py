#!/usr/bin/env python3
"""
Work Log Evaluator

Evaluates work logs in Data/test_data/test_data.csv against the
/validate-work-status endpoint, threading conversation turns and
judging follow-up question similarity (LLM-backed, 60% threshold).

Dataset expectations:
- CSV includes column conversation_id to identify a single conversation thread.
- The first row of a conversation is the initial note (no prior follow-ups).
- For subsequent rows in the same conversation_id, we pass prior assistant
  follow-ups and the technician's replies as conversation history.

Outputs:
- Row results  -> Data/test_data/evals_results.csv
- Group summary -> Data/test_data/evals_results_summary.csv (one row per conversation_id)
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import requests
import yaml
import openai
from dotenv import load_dotenv

# ===============================
# Configuration & Constants
# ===============================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(PROJECT_ROOT, "Data", "test_data", "test_data.csv")
WORK_ORDERS_PATH = os.path.join(PROJECT_ROOT, "Database", "work_orders.csv")
RESULTS_PATH = os.path.join(PROJECT_ROOT, "Data", "test_data", "evals_results.csv")
SUMMARY_PATH = os.path.join(PROJECT_ROOT, "Data", "test_data", "evals_results_summary.csv")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")
SIMILARITY_THRESHOLD = 0.60

# Optional OpenAI client (consistent with ai_classifier)
load_dotenv()
try:
    openai_client_available = True
except Exception:
    openai_client_available = False

# ===============================
# Utility: API base URL & data loading
# ===============================

def get_api_base_url() -> str:
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f)
            host = cfg["api"]["host"]
            port = cfg["api"]["port"]
            if host == "0.0.0.0":
                host = "localhost"
            return f"http://{host}:{port}"
    except Exception:
        return "http://localhost:8000"


def load_work_orders_index(path: str) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    if not os.path.exists(path):
        return index
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            index[row.get("work_order_id", "")] = row
    return index


def load_dataset(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ===============================
# Work_pct Parsing
# ===============================

def parse_work_pct(work_pct_raw: Optional[str]) -> Optional[Dict[str, Dict[str, int]]]:
    """Parse Work_pct strings like "{Trouble shooting: 50%, Repair Work: 50%}" into
    a dict of { type: {"percentage": int} } suitable for the payload.

    Returns None if parsing fails or input is empty.
    """
    if not work_pct_raw:
        return None
    s = work_pct_raw.strip()
    # Remove surrounding braces if present
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    if not s:
        return None
    # Split by commas at top level
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return None
    result: Dict[str, Dict[str, int]] = {}
    for part in parts:
        # Expect "Label: 50%" possibly with extra spaces
        if ":" not in part:
            continue
        label, value = part.split(":", 1)
        label = label.strip()
        value = value.strip().rstrip("% ")
        try:
            pct = int(float(value))
        except Exception:
            continue
        if label:
            result[label] = {"percentage": pct}
    return result or None


def llm_similarity(expected: str, returned: str, retries: int = 2) -> Optional[float]:
    """Ask an LLM to score similarity in percent (0-100). Returns None if not available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not (openai_client_available and api_key):
        return None
    try:
        client = openai.OpenAI()
        prompt = (
            "You are a strict grader. Compare two follow-up questions. "
            "Output only one number from 0 to 100 representing semantic similarity in meaning.\n"
            f"Expected: {expected}\n"
            f"Generated: {returned}\n"
            "Answer in percentage format. Example: 90, or 10, or 20\n"
            "Answer:"
        )
        # Retry loop for robustness
        last_exc: Optional[Exception] = None
        for _ in range(max(1, retries)):
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=10,
                )
                text = (resp.choices[0].message.content or "").strip()
                import re
                m = re.search(r"^(\d{1,3})(?:\.\d+)?", text)
                if not m:
                    # try to find any number anywhere
                    m = re.search(r"(\d{1,3})(?:\.\d+)?", text)
                if m:
                    score = float(m.group(1))
                    score = max(0.0, min(100.0, score))
                    return score / 100.0
            except Exception as e:
                last_exc = e
                continue
        # If we get here, return None to signal failure
        return None
    except Exception:
        return None


def judge_similarity(expected: str, returned: str) -> tuple[float, str]:
    """Return (score, source) where score in [0,1] using LLM only. Never returns None."""
    llm_score = llm_similarity(expected, returned)
    if llm_score is None:
        # If the LLM fails entirely, treat as 0 similarity to remain strict
        return 0.0, "llm"
    return llm_score, "llm"


def call_validate(session: requests.Session, base_url: str, payload: Dict) -> Tuple[bool, str, Dict]:
    try:
        resp = session.post(f"{base_url}/validate-work-status", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json() or {}
        return bool(data.get("valid", False)), data.get("follow_up_question", "") or "", data
    except Exception as e:
        return False, "", {"error": str(e)}


def expected_outcome_from_row(row: Dict[str, str]) -> Tuple[bool, str]:
    label = (row.get("Follow up question", "") or "").strip()
    if label.lower() == "success":
        return True, ""
    if label.lower() == "failure":
        return False, ""
    return False, label


def make_payload(row: Dict[str, str], messages: List[Dict[str, str]], wo_index: Dict[str, Dict[str, str]]) -> Tuple[Dict, Dict[str, str]]:
    work_order_id = row.get("Work order", "").strip().strip('"')
    wo_db = wo_index.get(work_order_id, {})

    # Prefer DB type; fallback to row type; last-resort "Work"
    work_status_value = (wo_db.get("wo_type") or row.get("WO_Type") or "Work").strip()
    # If Work_pct provided, parse and pass as dict payload
    work_pct_raw = row.get("Work_pct")
    work_status_payload = parse_work_pct(work_pct_raw) or work_status_value

    payload = {
        "operational_log": (row.get("Answer", "") or "").strip(),
        "work_status": work_status_payload,
        "work_order_id": work_order_id,
        "follow_up_questions_answers_table": messages,
    }

    # Context for traceability in results
    context = {
        "plant": wo_db.get("plant", ""),
        "work_order_description": wo_db.get("description", ""),
        "work_status_value": work_status_value,
        "db_tech": wo_db.get("tech_name", ""),
    }
    return payload, context


def evaluate_conversation(
    session: requests.Session,
    base_url: str,
    rows: List[Dict[str, str]],
    wo_index: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    messages: List[Dict[str, str]] = []

    for idx, row in enumerate(rows):
        expected_valid, expected_follow = expected_outcome_from_row(row)
        payload, ctx = make_payload(row, messages, wo_index)

        returned_valid, returned_follow, api_raw = call_validate(session, base_url, payload)

        # Similarity check when follow-up text is expected
        pass_flag = True
        notes: List[str] = []
        if expected_valid != returned_valid:
            pass_flag = False
            notes.append(f"valid mismatch: expected={expected_valid} got={returned_valid}")
        if expected_follow:
            sim, sim_src = judge_similarity(expected_follow, returned_follow)
            if sim < SIMILARITY_THRESHOLD:
                pass_flag = False
                notes.append(f"follow_up similarity too low: {sim:.2f} (src={sim_src})")

        ds_tech = (row.get("Tech_name", "") or "").strip()
        if ctx["db_tech"] and ds_tech and ctx["db_tech"].lower() != ds_tech.lower():
            notes.append(f"db tech mismatch: {ctx['db_tech']} vs {ds_tech}")

        # Record row result
        results.append({
            "id": row.get("id", ""),
            "conversation_id": row.get("conversation_id", ""),
            "tech_notes_type": row.get("Tech Notes Type", ""),
            "work_order_id": row.get("Work order", ""),
            "tech_name": ds_tech or ctx["db_tech"],
            "wo_type": ctx["work_status_value"],
            "plant": ctx["plant"],
            "work_order_description": ctx["work_order_description"],
            "operational_log": payload["operational_log"],
            "expected_valid": str(expected_valid),
            "returned_valid": str(returned_valid),
            "expected_follow_up": expected_follow,
            "returned_follow_up": returned_follow,
            "pass": str(pass_flag),
            "notes": "; ".join(notes)
        })

        # Thread conversation to next row:
        if returned_follow:
            messages.append({"role": "assistant", "content": returned_follow})
        if idx + 1 < len(rows):
            next_answer = (rows[idx + 1].get("Answer", "") or "").strip()
            if next_answer:
                messages.append({"role": "technician", "content": next_answer})

    return results

# ===============================
# Output Writers
# ===============================

def write_row_results(rows: List[Dict[str, str]], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = [
        "id","conversation_id","tech_notes_type","work_order_id","tech_name","wo_type","plant","work_order_description","operational_log",
        "expected_valid","returned_valid","expected_follow_up","returned_follow_up","pass","notes"
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: List[Dict[str, str]], out_path: str) -> Tuple[int, int]:
    """Write a per-row summary (by id) including Tech Notes Type.
    A row passes if its 'pass' field is True. Reason is derived from its notes
    and expected/returned validity.
    """
    total_pass = 0
    total_fail = 0
    summary_rows: List[Dict[str, str]] = []

    import re
    for r in rows:
        passed = r.get("pass", "").lower() == "true"
        if passed:
            reason = ""
            total_pass += 1
        else:
            total_fail += 1
            # Derive per-row reason
            notes = r.get("notes", "")
            m = re.search(r"follow_up similarity too low:\s*([0-9]*\.?[0-9]+)", notes)
            if m:
                sim_pct = int(round(float(m.group(1)) * 100))
                reason = f"%mismatch between follow ups (sim={sim_pct}%)"
            else:
                exp = r.get("expected_valid", "").lower() == "true"
                got = r.get("returned_valid", "").lower() == "true"
                if exp and not got:
                    reason = "Conversation didn't end valid on time"
                elif (not exp) and got:
                    reason = "conversation ended before time"
                else:
                    reason = "failed"

        summary_rows.append({
            "id": r.get("id", ""),
            "conversation_id": r.get("conversation_id", ""),
            "work_order_id": r.get("work_order_id", ""),
            "tech_name": r.get("tech_name", ""),
            "wo_type": r.get("wo_type", ""),
            "Tech Notes Type": r.get("tech_notes_type", ""),
            "pass": str(passed),
            "reason": reason,
        })

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id","conversation_id","work_order_id","tech_name","wo_type","Tech Notes Type","pass","reason"
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    return total_pass, total_fail

# ===============================
# Main
# ===============================

def main() -> int:
    try:
        dataset = load_dataset(DATASET_PATH)
    except FileNotFoundError as e:
        print(str(e))
        return 1

    base_url = get_api_base_url()
    wo_index = load_work_orders_index(WORK_ORDERS_PATH)

    # Group rows by conversation_id preserving order of appearance
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in dataset:
        grouped[row.get("conversation_id", "")].append(row)

    session = requests.Session()
    all_results: List[Dict[str, str]] = []

    for _, rows in grouped.items():
        all_results.extend(evaluate_conversation(session, base_url, rows, wo_index))

    write_row_results(all_results, RESULTS_PATH)
    total_pass, total_fail = write_summary(all_results, SUMMARY_PATH)

    total_groups = total_pass + total_fail
    print(f"Work log summary (grouped by conversation_id): {total_pass}/{total_groups} passed, {total_fail} failed.")
    print(f"Row-level results: {RESULTS_PATH}")
    print(f"Summary results:   {SUMMARY_PATH}")

    return 0 if total_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
