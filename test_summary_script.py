#!/usr/bin/env python3
"""
Client Summary Test Script

Calls the /convert-to-client-summary endpoint for each conversation in test_data.csv
and saves the results to test_summary_output.csv.

The script groups rows by conversation_id and constructs conversation tables
with technician and AI assistant messages, then calls the endpoint to get
client-friendly summaries and notes.
"""

import csv
import os
import sys
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import requests
import yaml

# ===============================
# Configuration
# ===============================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(PROJECT_ROOT, "Data", "test_data", "test_data.csv")
WORK_ORDERS_PATH = os.path.join(PROJECT_ROOT, "Database", "work_orders.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "Data", "test_data", "test_summary_output.csv")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

def get_api_base_url() -> str:
    """Get API base URL from config file"""
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
    """Load work orders CSV into a dictionary indexed by work_order_id"""
    index: Dict[str, Dict[str, str]] = {}
    if not os.path.exists(path):
        return index
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            index[row.get("work_order_id", "")] = row
    return index

def load_dataset(path: str) -> List[Dict[str, str]]:
    """Load test dataset CSV"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def parse_work_pct(work_pct_raw: Optional[str]) -> Optional[Dict[str, Dict[str, int]]]:
    """Parse Work_pct strings into dict format for API"""
    if not work_pct_raw:
        return None
    s = work_pct_raw.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return None
    result: Dict[str, Dict[str, int]] = {}
    for part in parts:
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

def build_conversation_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Build conversation table from conversation rows"""
    conversation = []
    
    for row in rows:
        # Add technician message
        tech_message = (row.get("Answer", "") or "").strip()
        if tech_message:
            conversation.append({
                "role": "technician",
                "content": tech_message
            })
        
        # Add AI assistant follow-up if present
        follow_up = (row.get("Follow up question", "") or "").strip()
        if follow_up and follow_up.lower() not in ["success", "failure"]:
            conversation.append({
                "role": "assistant", 
                "content": follow_up
            })
    
    return conversation

def call_client_summary_endpoint(
    session: requests.Session, 
    base_url: str, 
    conversation_table: List[Dict[str, str]],
    work_order_description: str,
    work_status: Dict[str, Dict[str, int]],
    plant: str,
    work_order_type: str
) -> Tuple[bool, str, str, str]:
    """Call the /convert-to-client-summary endpoint"""
    try:
        payload = {
            "conversation_tech_ai_client_table": conversation_table,
            "work_order_description": work_order_description,
            "work_status": work_status,
            "plant": plant,
            "work_order_type": work_order_type
        }
        
        resp = session.post(f"{base_url}/convert-to-client-summary", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json() or {}
        
        # Determine success based on presence of content and absence of error
        error = data.get("error_message", "")
        summary = data.get("summary", "")
        notes = data.get("notes", "")
        success = not error and bool(summary) and bool(notes)
        
        return success, summary, notes, error
        
    except Exception as e:
        return False, "", "", str(e)

def process_conversations(
    session: requests.Session,
    base_url: str,
    grouped_conversations: Dict[str, List[Dict[str, str]]],
    wo_index: Dict[str, Dict[str, str]]
) -> List[Dict[str, str]]:
    """Process all conversations and call the client summary endpoint"""
    results = []
    
    for conv_id, rows in grouped_conversations.items():
        if not rows:
            continue
            
        # Get work order info from first row
        first_row = rows[0]
        work_order_id = first_row.get("Work order", "").strip().strip('"')
        wo_db = wo_index.get(work_order_id, {})
        
        # Build conversation table
        conversation_table = build_conversation_table(rows)
        
        # Prepare API parameters
        work_order_description = wo_db.get("description", first_row.get("WO_Describtion", ""))
        work_order_type = wo_db.get("wo_type", first_row.get("WO_Type", "Work"))
        plant = wo_db.get("plant", "")
        
        # Parse work status from Work_pct
        work_pct_raw = first_row.get("Work_pct", "")
        work_status = parse_work_pct(work_pct_raw) or {"Work": {"percentage": 100}}
        
        # Call the endpoint
        success, summary, notes, error = call_client_summary_endpoint(
            session, base_url, conversation_table, work_order_description,
            work_status, plant, work_order_type
        )
        
        # Store results
        result = {
            "conversation_id": conv_id,
            "work_order_id": work_order_id,
            "tech_name": first_row.get("Tech_name", ""),
            "wo_type": work_order_type,
            "plant": plant,
            "work_order_description": work_order_description,
            "work_status": json.dumps(work_status),
            "tech_note_type": first_row.get("tech_note_type", ""),
            "conversation_length": str(len(conversation_table)),
            "success": str(success),
            "summary": summary,
            "notes": notes,
            "error_message": error
        }
        
        results.append(result)
        print(f"Processed conversation {conv_id}: {'✓' if success else '✗'}")
    
    return results

def write_results(results: List[Dict[str, str]], output_path: str) -> None:
    """Write results to CSV file"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fieldnames = [
        "conversation_id", "work_order_id", "tech_name", "wo_type", "plant",
        "work_order_description", "work_status", "tech_note_type", "conversation_length",
        "success", "summary", "notes", "error_message"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

def main() -> int:
    """Main function"""
    try:
        # Load data
        dataset = load_dataset(DATASET_PATH)
        wo_index = load_work_orders_index(WORK_ORDERS_PATH)
        
        # Group by conversation_id
        grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        for row in dataset:
            conv_id = row.get("conversation_id", "")
            if conv_id:
                grouped[conv_id].append(row)
        
        print(f"Found {len(grouped)} conversations to process")
        
        # Setup API connection
        base_url = get_api_base_url()
        session = requests.Session()
        
        # Process conversations
        results = process_conversations(session, base_url, grouped, wo_index)
        
        # Write results
        write_results(results, OUTPUT_PATH)
        
        # Summary
        successful = sum(1 for r in results if r["success"].lower() == "true")
        total = len(results)
        
        print(f"\nSummary:")
        print(f"  Total conversations: {total}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {total - successful}")
        print(f"  Results saved to: {OUTPUT_PATH}")
        
        return 0 if successful == total else 1
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
