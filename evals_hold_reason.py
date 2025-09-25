import csv
from datetime import datetime
from typing import List, Dict
from src.api_client import FieldServicesAPIClient
try:
    import openai
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not available. Follow-up answers will not be generated.")


def generate_follow_up_answer(hold_reason: str, follow_up_question: str, work_order_description: str, 
                             plant: str, hold_reason_type: str) -> str:
    """Generate a realistic technician response to follow-up question using LLM."""
    
    prompt = f"""
You are a field technician responding to a follow-up question about a work order hold.

CONTEXT:
Work Order Description: {work_order_description}
Plant: {plant}
Hold Reason Type: {hold_reason_type}
Original Hold Reason: {hold_reason}

FOLLOW-UP QUESTION: {follow_up_question}

Generate a realistic, concise technician response (2-3 sentences) that:
1. Directly answers the follow-up question
2. Uses appropriate technical terminology for the equipment/plant
3. Sounds like a field technician would write it
4. Provides specific details when possible
5. Maintains professional but informal tone

Response:"""

    if not OPENAI_AVAILABLE:
        return "OpenAI not available - follow-up answer not generated."
        
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating follow-up answer: {e}")
        return "Unable to generate response at this time."


def load_summary_notes(summary_csv: str) -> Dict[str, str]:
    """Map work_order_id -> concatenated 'summary' + 'notes' text from test_summary_output.csv."""
    mapping: Dict[str, str] = {}
    with open(summary_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wo_id = row.get("work_order_id") or row.get("Work order") or ""
            if not wo_id:
                continue
            text_parts = []
            if row.get("summary"):
                text_parts.append(row["summary"]) 
            if row.get("notes"):
                text_parts.append(row["notes"]) 
            combined = ". ".join([p.strip() for p in text_parts if p and p.strip()])
            if not combined:
                continue
            # Prefer the longest/most detailed entry per work order
            prev = mapping.get(wo_id, "")
            if len(combined) > len(prev):
                mapping[wo_id] = combined
    return mapping


def extract_context_from_notes(notes_text: str) -> Dict[str, str]:
    """Heuristically extract equipment, component/part, and process from notes text."""
    text = (notes_text or "").lower()
    equipment = None
    part = None
    process = None

    # Equipment candidates
    if "string power controller" in text or "spc" in text:
        equipment = "String Power Controller"
    elif "network control unit" in text or "ncu" in text:
        equipment = "Network Control Unit"
    elif "inverter" in text or "inv " in text or "inv " in text:
        equipment = "Inverter"
    elif "line break device" in text or "lbd" in text:
        equipment = "Line Break Device"

    # Part/component candidates
    if "mc4" in text:
        part = "MC4 connector"
    elif "contactor" in text:
        part = "DC Contactor"
    elif "board" in text or "comm board" in text or "dst board" in text:
        part = "control/communication board"
    elif "module" in text or "modules" in text:
        part = "PV modules"

    # Process/action
    if "reconnect" in text or "reconnected" in text:
        process = "reconnection"
    elif "replace" in text or "replaced" in text or "swap" in text:
        process = "replacement"
    elif "claim" in text or "warranty" in text:
        process = "warranty claim"
    elif "inspect" in text or "inspection" in text or "troubleshoot" in text:
        process = "inspection/troubleshooting"

    return {
        "equipment": equipment or "equipment",
        "part": part or "component",
        "process": process or "action",
    }


def load_target_work_orders_from_test_data(test_csv: str) -> List[Dict]:
    """Load the subset of work orders present in test_data.csv, return their IDs."""
    ids: List[str] = []
    with open(test_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wo = row.get("Work order") or row.get("work_order_id") or ""
            if wo and wo not in ids:
                ids.append(wo)
    return ids


def map_work_order_metadata(work_orders_csv: str) -> Dict[str, Dict]:
    """Map work_order_id -> {description, wo_type, plant}."""
    mapping: Dict[str, Dict] = {}
    with open(work_orders_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["work_order_id"]] = {
                "description": row.get("description", ""),
                "wo_type": row.get("wo_type", ""),
                "plant": row.get("plant", ""),
            }
    return mapping


def build_cases_for_work_order(wo_id: str, meta: Dict, notes_text: str) -> List[Dict]:
    """Create Bad/Average/Good cases per hold type using WO description, plant, and extracted notes context."""
    cases: List[Dict] = []
    work_order_type = meta.get("wo_type") or "Corrective"
    work_order_description = meta.get("description") or ""
    plant = meta.get("plant") or ""
    wo_status_and_notes_table = f"No previous logs for {wo_id} at {plant}"
    ctx = extract_context_from_notes(notes_text)
    eqp = ctx["equipment"]
    part = ctx["part"]

    # Definitions per hold_reason_types core requirements
    # Core fields for holds: reason (what/why), ETA (or unknown), waiting_for (what is needed)

    # Warranty
    cases += [
        {
            "label": "Bad",
            "hold_reason_label": "Warranty",
            "hold_reason": f"Waiting for warranty claim",  # Missing specifics, no ETA, no waiting for
        },
        {
            "label": "Average",
            "hold_reason_label": "Warranty",
            "hold_reason": (
                f"Warranty claim submitted to OEM for {eqp} {part} "
                "ETA unknown."
            ),  # Has reason, waiting_for, ETA unknown
        },
        {
            "label": "Good",
            "hold_reason_label": "Warranty",
            "hold_reason": (
                f"Warranty hold for {eqp} {part}. Claim submitted to OEM; "
                "awaiting approval and RMA shipment. ETA 3-5 business days."
            ),
        },
    ]

    # Parts unavailable
    cases += [
        {
            "label": "Bad",
            "hold_reason_label": "Parts unavailable",
            "hold_reason": f"Waiting for Parts",  # Too vague
        },
        {
            "label": "Average",
            "hold_reason_label": "Parts unavailable",
            "hold_reason": (
                f"Parts request submitted for {eqp}; supplier confirmation pending."
            ),
        },
        {
            "label": "Good",
            "hold_reason_label": "Parts unavailable",
            "hold_reason": (
                f"Parts hold: {part} for {eqp}. Item(s) listed on PO; supplier confirmed. "
                "ETA 2025-10-05. Work resumes after arrival."
            ),
        },
    ]

    # Others
    cases += [
        {
            "label": "Bad",
            "hold_reason_label": "Others",
            "hold_reason": f"Access/weather hold at {plant}",  # Missing details
        },
        {
            "label": "Average",
            "hold_reason_label": "Others",
            "hold_reason": (
                f"Site access restricted at {plant}; awaiting clearance to resume work on {eqp}."
            ),
        },
        {
            "label": "Good",
            "hold_reason_label": "Others",
            "hold_reason": (
                f"Access hold at {plant} due to safety lockout. Work on {eqp} will resume after client safety "
                "inspection tomorrow 10:00 AM; ETA 2025-09-26 10:00 AM. Waiting for client approval."
            ),
        },
    ]

    # Attach shared context
    for c in cases:
        c["work_order_type"] = work_order_type
        c["work_order_description"] = work_order_description
        c["plant"] = plant
        c["work_order_id"] = wo_id
        c["wo_status_and_notes"] = wo_status_and_notes_table
    return cases


def run() -> None:
    client = FieldServicesAPIClient()
    target_wos = load_target_work_orders_from_test_data("Data/test_data/test_data.csv")
    wo_meta = map_work_order_metadata("Database/work_orders.csv")
    wo_notes = load_summary_notes("Data/test_data/test_summary_output.csv")
    cases: List[Dict] = []
    for wo_id in target_wos:
        meta = wo_meta.get(wo_id)
        if not meta:
            continue
        cases.extend(build_cases_for_work_order(wo_id, meta, wo_notes.get(wo_id, "")))
    rows: List[Dict] = []

    for idx, c in enumerate(cases, start=1):
        # Build up to 3-turn conversation, stop early if valid
        messages = [{"role": "user", "content": c["hold_reason"]}]
        turn_input_text = c["hold_reason"]
        for turn in range(1, 4):
            payload_loop = {
                "hold_reason": c["hold_reason_label"],
                "work_order_type": c["work_order_type"],
                "work_order_description": c["work_order_description"],
                "plant": c["plant"],
                "wo_status_and_notes_with_time_allocation_table": c["wo_status_and_notes"],
                "follow_up_questions_answers_table": messages,
            }
            result_loop = client._make_request("POST", "/validate-reason-for-hold", data=payload_loop)
            response_valid = None if not result_loop else result_loop.get("valid")
            follow_up_question = None if not result_loop else result_loop.get("follow_up_question")

            rows.append({
                "id": f"{idx}_{turn}",
                "turn": turn,
                "label": c["label"],
                "work_order_id": c.get("work_order_id", ""),
                "hold_reason_type": c["hold_reason_label"],
                "input_hold_reason": turn_input_text,
                "work_order_type": c["work_order_type"],
                "work_order_description": c["work_order_description"],
                "plant": c.get("plant", ""),
                "response_valid": response_valid,
                "follow_up_question": follow_up_question,
            })

            if response_valid is True or not follow_up_question or turn == 3:
                break

            # Generate next answer and continue the conversation
            follow_up_answer = generate_follow_up_answer(
                hold_reason=c["hold_reason"],
                follow_up_question=follow_up_question,
                work_order_description=c["work_order_description"],
                plant=c["plant"],
                hold_reason_type=c["hold_reason_label"],
            )
            messages.append({"role": "assistant", "content": follow_up_question})
            messages.append({"role": "user", "content": follow_up_answer})
            turn_input_text = follow_up_answer

    out_path = "Data/test_data/hold_reason_test_data.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    run()


