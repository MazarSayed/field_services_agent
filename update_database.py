#!/usr/bin/env python3
"""
Enhanced Database Update Script
Extracts work orders of different types from FSM Data and updates the database files
with the following logic:
- For each employee, select work orders from 5 types: Preventive, Corrective, Ad Hoc, Project, OEM Repair Work
- Include asset description and equipment information
- Split work orders 50/50 between completed and pending
- Move pending work order logs to test data
- Keep completed work order logs in the main database
"""

import pandas as pd
import csv
import shutil
from datetime import datetime
import os
from typing import List, Dict, Any, Tuple
import random

def parse_date(date_str: str) -> str:
    """Parse date string from FSM data format to YYYY-MM-DD"""
    try:
        # Handle format like "Wednesday, March 27, 2024"
        if date_str and ',' in date_str:
            # Split by comma and get the date part (month day, year)
            parts = date_str.split(',')
            if len(parts) >= 3:
                # Extract month day, year part and ensure proper spacing
                month_day = parts[1].strip()
                year = parts[2].strip()
                date_part = f"{month_day}, {year}"
                # Parse the date
                dt = datetime.strptime(date_part, "%B %d, %Y")
                return dt.strftime("%Y-%m-%d")
        return ""
    except Exception as e:
        print(f"  Date parsing error for '{date_str}': {e}")
        return ""

def extract_work_orders_by_type():
    """Extract work orders of different types from FSM data"""
    print("Reading FSM data...")
    
    # Read the FSM data with different encoding options
    try:
        fsm_data = pd.read_csv("Data/FSM Data With Log_Escalante_Golden Triangle.csv", encoding='utf-8')
    except UnicodeDecodeError:
        try:
            fsm_data = pd.read_csv("Data/FSM Data With Log_Escalante_Golden Triangle.csv", encoding='latin-1')
        except UnicodeDecodeError:
            fsm_data = pd.read_csv("Data/FSM Data With Log_Escalante_Golden Triangle.csv", encoding='cp1252')
    
    # Filter for main work order types - now including Project and OEM Repair Work
    main_types = ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']
    filtered_data = fsm_data[fsm_data['WO Type'].isin(main_types)]
    
    print(f"Found {len(filtered_data)} work orders of main types")
    print(f"Work order types: {filtered_data['WO Type'].value_counts().to_dict()}")
    
    return filtered_data

def select_work_orders_per_employee(filtered_data: pd.DataFrame) -> Dict[str, List[Dict]]:
    """Select work orders per employee (3 from each type if available, otherwise keep available amount)"""
    print("Selecting work orders per employee...")
    
    employee_work_orders = {}
    
    # Group by employee
    for tech_name, tech_data in filtered_data.groupby('User Resource: Full Name'):
        if pd.isna(tech_name):
            continue
            
        print(f"\nProcessing employee: {tech_name}")
        
        # Get unique work orders for this employee
        unique_work_orders = tech_data.groupby('Work Order').agg({
            'WO Type': 'first',
            'Asset Description': 'first',
            'Description': 'first',
            'Work Date': 'first',
            'Status': 'first',
            'Asset ID': 'first',
            'Plant': 'first'
        }).reset_index()
        
        print(f"  Found {len(unique_work_orders)} unique work orders")
        
        # Select work orders from each type (if available)
        selected_orders = []
        
        for wo_type in ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']:
            type_orders = unique_work_orders[unique_work_orders['WO Type'] == wo_type]
            
            if len(type_orders) >= 3:
                # Randomly select 3
                selected = type_orders.sample(n=3, random_state=42)
                selected_orders.extend(selected.to_dict('records'))
                print(f"    Selected 3 {wo_type} work orders")
            elif len(type_orders) > 0:
                # Take all available (don't fill from other types)
                selected_orders.extend(type_orders.to_dict('records'))
                print(f"    Selected {len(type_orders)} {wo_type} work orders (limited availability)")
            else:
                print(f"    No {wo_type} work orders found")
        
        employee_work_orders[tech_name] = selected_orders
        print(f"  Final selection: {len(selected_orders)} work orders")
    
    return employee_work_orders

def split_work_orders_by_status(employee_work_orders: Dict[str, List[Dict]]) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """Split work orders into completed (50%) and pending (50%) per employee"""
    print("\nSplitting work orders into completed and pending (50/50 split)...")
    
    completed_orders = {}
    pending_orders = {}
    
    for tech_name, work_orders in employee_work_orders.items():
        total_orders = len(work_orders)
        
        if total_orders > 0:
            # Calculate 50/50 split
            completed_count = total_orders // 2
            pending_count = total_orders - completed_count
            
            # Split the work orders
            completed_orders[tech_name] = work_orders[:completed_count]
            pending_orders[tech_name] = work_orders[completed_count:]
            
            # Mark pending orders as 'Pending' status
            for order in pending_orders[tech_name]:
                order['Status'] = 'Pending'
            
            print(f"{tech_name}: {completed_count} completed, {pending_count} pending (Total: {total_orders})")
        else:
            completed_orders[tech_name] = []
            pending_orders[tech_name] = []
            print(f"{tech_name}: 0 completed, 0 pending")
    
    return completed_orders, pending_orders

def update_work_orders(completed_orders: Dict[str, List[Dict]], pending_orders: Dict[str, List[Dict]]):
    """Update work_orders.csv with selected work orders"""
    print("Updating work_orders.csv...")
    
    work_orders = []
    id_counter = 1
    
    # Process completed orders
    for tech_name, orders in completed_orders.items():
        for order in orders:
            work_date = parse_date(order['Work Date'])
            if not work_date:
                work_date = '2024-01-15'  # Default date
            
            work_order = {
                'id': id_counter,
                'work_order_id': order['Work Order'],
                'tech_name': tech_name,
                'status': 'Completed',
                'work_date': work_date,
                'description': order['Description'],
                'wo_type': order['WO Type'],
                'time_type': 'Work',
                'asset_description': order['Asset Description'],
                'asset_id': order['Asset ID'],
                'plant': order['Plant'],
                'created_at': f"{work_date} 08:00:00",
                'updated_at': f"{work_date} 08:00:00"
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Process pending orders
    for tech_name, orders in pending_orders.items():
        for order in orders:
            work_date = parse_date(order['Work Date'])
            if not work_date:
                work_date = '2024-01-15'  # Default date
            
            work_order = {
                'id': id_counter,
                'work_order_id': order['Work Order'],
                'tech_name': tech_name,
                'status': 'Pending',
                'work_date': work_date,
                'description': order['Description'],
                'wo_type': order['WO Type'],
                'time_type': 'Work',
                'asset_description': order['Asset Description'],
                'asset_id': order['Asset ID'],
                'plant': order['Plant'],
                'created_at': f"{work_date} 08:00:00",
                'updated_at': f"{work_date} 08:00:00"
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'status', 'description', 
                  'wo_type', 'time_type', 'asset_description', 'asset_id', 'plant', 
                  'created_at', 'updated_at']
    
    with open('Database/work_orders.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_orders)
    
    print(f"Updated work_orders.csv with {len(work_orders)} entries")
    return work_orders

def update_technicians(completed_orders: Dict[str, List[Dict]], pending_orders: Dict[str, List[Dict]]):
    """Update technicians.csv with technician data"""
    print("Updating technicians.csv...")
    
    # Get all unique technicians
    all_techs = set(list(completed_orders.keys()) + list(pending_orders.keys()))
    
    technicians = []
    id_counter = 1
    
    for tech_name in all_techs:
        # Get sample data for this technician
        sample_order = None
        if tech_name in completed_orders and completed_orders[tech_name]:
            sample_order = completed_orders[tech_name][0]
        elif tech_name in pending_orders and pending_orders[tech_name]:
            sample_order = pending_orders[tech_name][0]
        
        if sample_order:
            plant = sample_order.get('Plant', 'Escalante')
            email = f'{tech_name.lower().replace(" ", ".")}@origisservices.com'
            
            technician = {
                'id': id_counter,
                'tech_name': tech_name,
                'email': email,
                'phone': '+1-555-0000',
                'specialization': f"{plant} Field Service Technician",
                'hire_date': '2023-01-01',
                'status': 'Active',
                'created_at': '2024-01-15 08:00:00',
                'updated_at': '2024-01-15 08:00:00'
            }
            
            technicians.append(technician)
            id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'tech_name', 'email', 'phone', 'specialization', 'hire_date', 'status', 'created_at', 'updated_at']
    
    with open('Database/technicians.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(technicians)
    
    print(f"Updated technicians.csv with {len(technicians)} entries")
    return technicians

def create_test_data_files(pending_orders: Dict[str, List[Dict]], fsm_data: pd.DataFrame):
    """Create test data files for pending work orders with enhanced information"""
    print("Creating test data files for pending work orders...")
    
    # Get all pending work order IDs
    pending_wo_ids = []
    for orders in pending_orders.values():
        for order in orders:
            pending_wo_ids.append(order['Work Order'])
    
    print(f"Pending work order IDs: {pending_wo_ids}")
    
    # Filter FSM data for pending work orders
    pending_data = fsm_data[fsm_data['Work Order'].isin(pending_wo_ids)]
    
    # Create test work status logs with enhanced information
    test_work_status_logs = []
    id_counter = 1
    
    for _, row in pending_data.iterrows():
        work_date = parse_date(row['Work Date'])
        if not work_date:
            continue
            
        tech_name = row.get('User Resource: Full Name', 'Unknown Technician')
        if pd.isna(tech_name):
            continue
        
        # Get additional context from the work order
        work_order_id = row.get('Work Order', 'Unknown')
        description = row.get('Description', '')
        asset_description = row.get('Asset Description', '')
        asset_id = row.get('Asset ID', '')
        plant = row.get('Plant', '')
        wo_type = row.get('WO Type', 'Unknown')
        
        work_status_log = {
            'id': id_counter,
            'work_order_id': work_order_id,
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('Time Type', 'Work'),
            'time_spent': row.get('Total Labor Hours', 0.5),
            'notes': row.get('Completion Notes', ''),
            'summary': f"Test data for pending work order {work_order_id}",
            'description': description,
            'wo_type': wo_type,
            'asset_description': asset_description,
            'asset_id': asset_id,
            'plant': plant,
            'created_at': f"{work_date} 08:00:00",
            'updated_at': f"{work_date} 08:00:00"
        }
        
        test_work_status_logs.append(work_status_log)
        id_counter += 1
    
    # Write test work status logs with enhanced fields
    with open('Data/test_data/pending_work_status_logs_test.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 
                     'summary', 'description', 'wo_type', 'asset_description', 'asset_id', 'plant', 
                     'created_at', 'updated_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_work_status_logs)
    
    # Create test completion notes with enhanced information
    test_completion_notes = []
    id_counter = 1
    
    for _, row in pending_data.iterrows():
        work_date = parse_date(row['Work Date'])
        if not work_date:
            continue
            
        tech_name = row.get('User Resource: Full Name', 'Unknown Technician')
        if pd.isna(tech_name):
            continue
        
        # Get additional context from the work order
        work_order_id = row.get('Work Order', 'Unknown')
        description = row.get('Description', '')
        asset_description = row.get('Asset Description', '')
        asset_id = row.get('Asset ID', '')
        plant = row.get('Plant', '')
        wo_type = row.get('WO Type', 'Unknown')
        
        completion_note = {
            'id': id_counter,
            'work_order_id': work_order_id,
            'tech_name': tech_name,
            'work_date': work_date,
            'completion_notes': row.get('Completion Notes', f"Test note for pending work order {work_order_id}"),
            'wo_type': wo_type,
            'time_type': row.get('Time Type', 'Work'),
            'description': description,
            'asset_description': asset_description,
            'asset_id': asset_id,
            'plant': plant,
            'created_at': f"{work_date} 08:00:00"
        }
        
        test_completion_notes.append(completion_note)
        id_counter += 1
    
    # Write test completion notes with enhanced fields
    with open('Data/test_data/pending_completion_notes_test.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'completion_notes', 'wo_type', 'time_type',
                     'description', 'asset_description', 'asset_id', 'plant', 'created_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_completion_notes)
    
    print(f"Created enhanced test data files:")
    print(f"  - Test work status logs: {len(test_work_status_logs)} entries")
    print(f"  - Test completion notes: {len(test_completion_notes)} entries")
    print(f"  - Enhanced with: description, asset_description, asset_id, plant, wo_type")

def update_work_status_logs(completed_orders: Dict[str, List[Dict]], fsm_data: pd.DataFrame):
    """Update work_status_logs.csv with completed work orders only"""
    print("Updating work_status_logs.csv with completed work orders...")
    
    # Get all completed work order IDs
    completed_wo_ids = []
    for orders in completed_orders.values():
        for order in orders:
            completed_wo_ids.append(order['Work Order'])
    
    # Filter FSM data for completed work orders only
    completed_data = fsm_data[fsm_data['Work Order'].isin(completed_wo_ids)]
    
    work_status_logs = []
    id_counter = 1
    
    for _, row in completed_data.iterrows():
        work_date = parse_date(row['Work Date'])
        if not work_date:
            continue
            
        tech_name = row.get('User Resource: Full Name', 'Unknown Technician')
        if pd.isna(tech_name):
            continue
        
        work_status_log = {
            'id': id_counter,
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('Time Type', 'Work'),
            'time_spent': row.get('Total Labor Hours', 0.5),
            'notes': row.get('Completion Notes', ''),
            'summary': f"Completed work order {row.get('Work Order', 'Unknown')}",
            'work_order_id': row.get('Work Order', f'WO-{id_counter:06d}'),
            'created_at': f"{work_date} 08:00:00",
            'updated_at': f"{work_date} 08:00:00"
        }
        
        work_status_logs.append(work_status_log)
        id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 'summary', 'work_order_id', 'created_at', 'updated_at']
    
    with open('Database/work_status_logs.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_status_logs)
    
    print(f"Updated work_status_logs.csv with {len(work_status_logs)} entries")
    return work_status_logs

def update_completion_notes(completed_orders: Dict[str, List[Dict]], fsm_data: pd.DataFrame):
    """Update completion_notes.csv with completed work orders only"""
    print("Updating completion_notes.csv with completed work orders...")
    
    # Get all completed work order IDs
    completed_wo_ids = []
    for orders in completed_orders.values():
        for order in orders:
            completed_wo_ids.append(order['Work Order'])
    
    # Filter FSM data for completed work orders only
    completed_data = fsm_data[fsm_data['Work Order'].isin(completed_wo_ids)]
    
    completion_notes = []
    id_counter = 1
    
    for _, row in completed_data.iterrows():
        work_date = parse_date(row['Work Date'])
        if not work_date:
            continue
            
        tech_name = row.get('User Resource: Full Name', 'Unknown Technician')
        if pd.isna(tech_name):
            continue
        
        notes = row.get('Completion Notes', '')
        if pd.isna(notes):
            notes = row.get('pffsm__Comments__c', '')
        if pd.isna(notes):
            notes = f"Completed {row.get('pffsm__WT_Description__c', 'work order task')}"
        
        completion_note = {
            'id': id_counter,
            'completion_notes': notes,
            'wo_type': row.get('WO Type', 'Preventive'),
            'time_type': row.get('Time Type', 'Work'),
            'work_order_id': row.get('Work Order', f'WO-{id_counter:06d}'),
            'tech_name': tech_name,
            'work_date': work_date,
            'created_at': f"{work_date} 08:00:00"
        }
        
        completion_notes.append(completion_note)
        id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'completion_notes', 'wo_type', 'time_type', 'work_order_id', 'tech_name', 'work_date', 'created_at']
    
    with open('Database/completion_notes.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(completion_notes)
    
    print(f"Updated completion_notes.csv with {len(completion_notes)} entries")
    return completion_notes

def main():
    """Main function to update all database files with new logic"""
    print("Starting enhanced database update with 5 work order types and 50/50 split...")
    
    try:
        # Extract work orders by type (now including Project and OEM Repair Work)
        filtered_data = extract_work_orders_by_type()
        
        if len(filtered_data) == 0:
            print("No work orders found!")
            return
        
        # Select work orders per employee (3 from each type if available, otherwise keep available amount)
        employee_work_orders = select_work_orders_per_employee(filtered_data)
        
        if not employee_work_orders:
            print("No work orders selected for any employee!")
            return
        
        # Split into completed (50%) and pending (50%)
        completed_orders, pending_orders = split_work_orders_by_status(employee_work_orders)
        
        # Update all database files
        work_orders = update_work_orders(completed_orders, pending_orders)
        technicians = update_technicians(completed_orders, pending_orders)
        work_status_logs = update_work_status_logs(completed_orders, filtered_data)
        completion_notes = update_completion_notes(completed_orders, filtered_data)
        
        # Create test data files for pending work orders
        create_test_data_files(pending_orders, filtered_data)
        
        print("\n✅ Enhanced database update completed successfully!")
        print(f"📊 Summary:")
        print(f"   - Total Work Orders: {len(work_orders)}")
        print(f"   - Technicians: {len(technicians)}")
        print(f"   - Work Status Logs (Completed): {len(work_status_logs)}")
        print(f"   - Completion Notes (Completed): {len(completion_notes)}")
        
        # Count pending vs completed
        total_pending = sum(len(orders) for orders in pending_orders.values())
        total_completed = sum(len(orders) for orders in completed_orders.values())
        print(f"   - Work Orders Status:")
        print(f"     * Completed: {total_completed}")
        print(f"     * Pending (moved to test data): {total_pending}")
        print(f"   - Work Order Types: Preventive, Corrective, Ad Hoc, Project, OEM Repair Work")
        print(f"   - Split Strategy: 50% completed, 50% pending per employee")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
