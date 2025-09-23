#!/usr/bin/env python3
"""
CAR Completion Test Script

Generates CAR outputs for each work order × tech note type combination
Uses test_summary_output.csv, test_completion_notes.csv, and test_data.csv
Calls the /convert-to-car endpoint for each combination
"""

import csv
import json
import requests
from typing import Dict, List, Any
from collections import defaultdict

# Configuration
API_BASE_URL = "http://localhost:8000"
SUMMARY_OUTPUT_FILE = "Data/test_data/test_summary_output.csv"
COMPLETION_NOTES_FILE = "Data/test_data/test_completion_notes.csv"
TEST_DATA_FILE = "Data/test_data/test_data.csv"
OUTPUT_FILE = "Data/test_data/CAR_completion.csv"

def load_summary_logs(file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load summary logs grouped by work order ID"""
    summary_logs = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            work_order_id = row['work_order_id']
            # Parse work_status JSON
            work_status = json.loads(row['work_status']) if row['work_status'] else {}
            
            summary_logs[work_order_id].append({
                'conversation_id': row['conversation_id'],
                'tech_name': row['tech_name'],
                'wo_type': row['wo_type'],
                'plant': row['plant'],
                'work_order_description': row['work_order_description'],
                'work_status': work_status,
                'tech_note_type': row['tech_note_type'],
                'summary': row['summary'],
                'notes': row['notes'],
                'conversation_length': row['conversation_length']
            })
    
    return dict(summary_logs)

def load_completion_notes(file_path: str) -> Dict[str, List[Dict[str, str]]]:
    """Load completion notes grouped by work order ID"""
    completion_notes = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            work_order_id = row['work_order_id']
            completion_notes[work_order_id].append({
                'conversation_id': row['conversation_id'],
                'tech_notes_type': row['tech_notes_type'],
                'completion_notes': row['completion_notes'],
                'tech_name': row['tech_name'],
                'wo_type': row['wo_type'],
                'plant': row['plant'],
                'description': row['description']
            })
    
    return dict(completion_notes)

def load_test_data(file_path: str) -> Dict[str, Dict[str, str]]:
    """Load test data to get work order details"""
    test_data = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            work_order_id = row['Work order'].strip().strip('"')
            if work_order_id not in test_data:
                test_data[work_order_id] = {
                    'work_order_description': row['WO_Describtion'],
                    'wo_type': row['WO_Type'],
                    'work_pct': row['Work_pct']
                }
    
    return test_data

def create_work_status_table(summary_logs: List[Dict[str, Any]], tech_note_type: str = None) -> str:
    """Create wo_status_and_notes_with_time_allocation_table format from summary logs"""
    if not summary_logs:
        return "No work logs found for this work order."
    
    # Filter by tech note type if specified
    filtered_logs = summary_logs
    if tech_note_type:
        filtered_logs = [log for log in summary_logs if log.get('tech_note_type') == tech_note_type]
    
    if not filtered_logs:
        return f"No work logs found for this work order and tech note type: {tech_note_type}."
    
    # Create table header
    table = "Date | Tech Name | Time allocation | Notes | Summary\n"
    
    for log in filtered_logs:
        # Use conversation_id as a pseudo-date for now
        date = f"2024-{int(log['conversation_id']):02d}-01"  # Pseudo date based on conversation ID
        
        tech_name = log['tech_name']
        
        # Convert work_status dict to readable format
        work_status = log['work_status']
        time_allocation = ", ".join([f"{k}: {v.get('percentage', 0)}%" for k, v in work_status.items()])
        
        # Clean notes and summary to remove newlines and quotes
        notes = log['notes'].replace('\n', ' ').replace('"', "'").strip()
        summary = log['summary'].replace('\n', ' ').replace('"', "'").strip()
        
        table += f"{date} | {tech_name} | {time_allocation} | {notes} | {summary}\n"
    
    return table

def call_car_conversion_endpoint(completion_note: str, work_status_table: str, work_order_data: Dict[str, str]) -> Dict[str, Any]:
    """Call the CAR conversion endpoint"""
    url = f"{API_BASE_URL}/convert-to-car"
    
    payload = {
        "completion_notes": completion_note,
        "wo_status_and_notes_with_time_allocation_table": work_status_table,
        "work_order_id": work_order_data.get('work_order_id', ''),
        "work_order_description": work_order_data.get('work_order_description', ''),
        "work_order_type": work_order_data.get('wo_type', '')
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "cause": "",
            "action": "",
            "result": "",
            "error_message": f"API call failed: {str(e)}"
        }

def main():
    """Main function to process all work order × tech note type combinations"""
    print("Loading summary logs...")
    summary_logs = load_summary_logs(SUMMARY_OUTPUT_FILE)
    
    print("Loading completion notes...")
    completion_notes = load_completion_notes(COMPLETION_NOTES_FILE)
    
    print("Loading test data...")
    test_data = load_test_data(TEST_DATA_FILE)
    
    print(f"Found {len(summary_logs)} work orders with summary logs")
    print(f"Found {len(completion_notes)} work orders with completion notes")
    print(f"Found {len(test_data)} work orders in test data")
    
    # Get the 8 work orders that have both summary logs and completion notes
    work_orders_with_data = set(summary_logs.keys()) & set(completion_notes.keys())
    selected_work_orders = sorted(list(work_orders_with_data))[:8]  # Take first 8
    
    print(f"Processing {len(selected_work_orders)} work orders: {selected_work_orders}")
    
    # Prepare results
    results = []
    
    # Process each work order
    for work_order_id in selected_work_orders:
        print(f"\nProcessing work order: {work_order_id}")
        
        work_order_summary_logs = summary_logs[work_order_id]
        work_order_completion_notes = completion_notes[work_order_id]
        work_order_test_data = test_data.get(work_order_id, {})
        
        # Add work_order_id to work_order_data for API calls
        work_order_data = {
            'work_order_id': work_order_id,
            'work_order_description': work_order_test_data.get('work_order_description', ''),
            'wo_type': work_order_test_data.get('wo_type', '')
        }
        
        # Process each tech note type (Bad, Average, Good)
        for tech_note_type in ["Bad", "Average", "Good"]:
            print(f"  Processing {tech_note_type} tech note type...")
            
            # Find matching completion note for this tech note type
            matching_completion_note = None
            for completion_note in work_order_completion_notes:
                if completion_note['tech_notes_type'] == tech_note_type:
                    matching_completion_note = completion_note
                    break
            
            if not matching_completion_note:
                print(f"    No {tech_note_type} completion note found, skipping...")
                continue
            
            # Create work status table filtered by tech note type
            work_status_table = create_work_status_table(work_order_summary_logs, tech_note_type)
            
            # Call the CAR conversion endpoint
            car_result = call_car_conversion_endpoint(
                matching_completion_note['completion_notes'], 
                work_status_table, 
                work_order_data
            )
            
            # Store result
            def clean_text(text):
                if text is None:
                    return ''
                return str(text).replace('\n', ' ').replace('"', "'").strip()
            
            # Determine success based on whether there's an error message
            error_message = clean_text(car_result.get('error_message', ''))
            success = not error_message and car_result.get('cause', '') and car_result.get('action', '') and car_result.get('result', '')
            
            # Count matching logs for this tech note type
            matching_logs = [log for log in work_order_summary_logs if log.get('tech_note_type') == tech_note_type]
            
            result = {
                'work_order_id': work_order_id,
                'tech_note_type': tech_note_type,
                'tech_name': matching_completion_note['tech_name'],
                'wo_type': matching_completion_note['wo_type'],
                'plant': matching_completion_note['plant'],
                'description': matching_completion_note['description'],
                'completion_notes': clean_text(matching_completion_note['completion_notes']),
                'conversation_count': len(matching_logs),
                'work_status_table': clean_text(work_status_table),
                'car_cause': clean_text(car_result.get('cause', '')),
                'car_action': clean_text(car_result.get('action', '')),
                'car_result': clean_text(car_result.get('result', '')),
                'success': success,
                'error_message': error_message
            }
            
            results.append(result)
    
    # Write results to CSV
    print(f"\nWriting results to {OUTPUT_FILE}...")
    write_results_to_csv(results, OUTPUT_FILE)
    
    # Print summary
    total_processed = len(results)
    total_successful = sum(1 for r in results if r['success'])
    total_failed = total_processed - total_successful
    
    print(f"Results written to {OUTPUT_FILE}")
    print(f"Total entries processed: {total_processed}")
    print(f"\nSummary:")
    print(f"  Successful conversions: {total_successful}")
    print(f"  Failed conversions: {total_failed}")
    
    print(f"\nWork Order Summary:")
    work_order_summary = {}
    for r in results:
        wo_id = r['work_order_id']
        if wo_id not in work_order_summary:
            work_order_summary[wo_id] = {'total': 0, 'successful': 0}
        work_order_summary[wo_id]['total'] += 1
        if r['success']:
            work_order_summary[wo_id]['successful'] += 1
    
    for wo_id, counts in work_order_summary.items():
        print(f"  {wo_id}: {counts['successful']}/{counts['total']} successful")

def write_results_to_csv(results: List[Dict[str, Any]], output_file: str):
    """Write results to CSV file"""
    if not results:
        return
    
    fieldnames = [
        'work_order_id', 'tech_note_type', 'tech_name', 'wo_type', 'plant', 'description',
        'completion_notes', 'conversation_count', 'work_status_table',
        'car_cause', 'car_action', 'car_result', 'success', 'error_message'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

if __name__ == "__main__":
    main()
