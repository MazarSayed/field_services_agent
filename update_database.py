#!/usr/bin/env python3
"""
Enhanced Database Update Script
Extracts work orders from Origis Data Excel file and updates the database files
with the following logic:
- Select top 3 technicians based on log activity
- For each technician, select work orders from 5 types: Preventive, Corrective, Ad Hoc, Project, OEM Repair Work
- Include work order description, plant, and hours information
- Split work orders 50/50 between completed and pending
- Move pending work order logs and completion notes to test data
- Keep completed work order logs in the main database
- Sort operating logs by date/time within each work order x technician combination
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
    """Extract work orders of different types from Origis Data Excel file"""
    print("Reading Origis Data Excel file...")
    
    # Read the Excel file with both sheets
    work_orders_df = pd.read_excel("Data/Origis_Data (2).xlsx", sheet_name='Work Order')
    operating_logs_df = pd.read_excel("Data/Origis_Data (2).xlsx", sheet_name='Operating Logs')
    
    print(f"Work Orders sheet: {work_orders_df.shape}")
    print(f"Operating Logs sheet: {operating_logs_df.shape}")
    
    # Filter for main work order types
    main_types = ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']
    filtered_wo = work_orders_df[work_orders_df['pffsm__WO_Type__c'].isin(main_types)]
    
    print(f"Found {len(filtered_wo)} work orders of main types")
    print(f"Work order types: {filtered_wo['pffsm__WO_Type__c'].value_counts().to_dict()}")
    
    # Get top 3 technicians by log activity
    top_technicians = operating_logs_df['User FSM.Name'].value_counts().head(3)
    print(f"Top 3 technicians: {top_technicians.to_dict()}")
    
    # Filter operating logs for top 3 technicians
    filtered_logs = operating_logs_df[operating_logs_df['User FSM.Name'].isin(top_technicians.index)]
    
    # Get work orders that have logs from our top 3 technicians
    wo_with_logs = filtered_logs['Work Order'].unique()
    final_work_orders = filtered_wo[filtered_wo['Name'].isin(wo_with_logs)]
    
    print(f"Work orders with logs from top 3 technicians: {len(final_work_orders)}")
    
    return final_work_orders, filtered_logs, top_technicians

def select_work_orders_per_employee(work_orders_df: pd.DataFrame, operating_logs_df: pd.DataFrame, top_technicians: pd.Series) -> Dict[str, List[Dict]]:
    """Select work orders per employee based on their operating logs"""
    print("Selecting work orders per employee...")
    
    employee_work_orders = {}
    
    # For each top technician, get their work orders from operating logs
    for tech_name in top_technicians.index:
        print(f"\nProcessing employee: {tech_name}")
        
        # Get work orders this technician has logs for
        tech_logs = operating_logs_df[operating_logs_df['User FSM.Name'] == tech_name]
        tech_work_orders = tech_logs['Work Order'].unique()
        
        print(f"  Found {len(tech_work_orders)} work orders with logs")
        
        # Get work order details for these work orders
        tech_wo_details = work_orders_df[work_orders_df['Name'].isin(tech_work_orders)]
        
        # Group by work order type and select up to 3 from each type
        selected_orders = []
        
        for wo_type in ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']:
            type_orders = tech_wo_details[tech_wo_details['pffsm__WO_Type__c'] == wo_type]
            
            if len(type_orders) >= 3:
                # Randomly select 3
                selected = type_orders.sample(n=3, random_state=42)
                selected_orders.extend(selected.to_dict('records'))
                print(f"    Selected 3 {wo_type} work orders")
            elif len(type_orders) > 0:
                # Take all available
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
    """Update work_orders.csv with selected work orders using direct mapping"""
    print("Updating work_orders.csv...")
    
    work_orders = []
    id_counter = 1
    
    # Process completed orders
    for tech_name, orders in completed_orders.items():
        for order in orders:
            # Use actual completion date from data
            completion_date = order.get('pffsm__Completion_Date__c', '')
            if pd.isna(completion_date) or completion_date == '':
                work_date = ''
            else:
                work_date = str(completion_date)[:10]  # Extract YYYY-MM-DD
            
            work_order = {
                'id': id_counter,
                'work_order_id': order['Name'],
                'tech_name': tech_name,
                'status': order.get('pffsm__Status__c', ''),
                'work_date': work_date,
                'description': "",
                'wo_type': order.get('pffsm__WO_Type__c', ''),
                'time_type': 'Work',
                'asset_description': order.get('pffsm__Plant__c', ''),
                'asset_id': order.get('Id', ''),
                'plant': order.get('pffsm__Plant__c', ''),
                'hours': order.get('pffsm__Total_Actual_Labor_Hours__c', ''),
                'day_name': order.get('Day Name', ''),
                'is_weekend': order.get('IsWeekend', ''),
                'created_at': work_date + ' 08:00:00' if work_date else '',
                'updated_at': work_date + ' 08:00:00' if work_date else ''
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Process pending orders
    for tech_name, orders in pending_orders.items():
        for order in orders:
            # Use actual data from work order
            completion_date = order.get('pffsm__Completion_Date__c', '')
            if pd.isna(completion_date) or completion_date == '':
                work_date = ''
            else:
                work_date = str(completion_date)[:10]  # Extract YYYY-MM-DD
            
            work_order = {
                'id': id_counter,
                'work_order_id': order['Name'],
                'tech_name': tech_name,
                'status': 'Pending',  # Override status for pending
                'work_date': work_date,
                'description': "",
                'wo_type': order.get('pffsm__WO_Type__c', ''),
                'time_type': 'Work',
                'asset_description': order.get('pffsm__Plant__c', ''),
                'asset_id': order.get('Id', ''),
                'plant': order.get('pffsm__Plant__c', ''),
                'hours': order.get('pffsm__Total_Actual_Labor_Hours__c', ''),
                'car_flag': order.get('CAR_Flag', ''),
                'day_name': order.get('Day Name', ''),
                'is_weekend': order.get('IsWeekend', ''),
                'created_at': work_date + ' 08:00:00' if work_date else '',
                'updated_at': work_date + ' 08:00:00' if work_date else ''
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'status', 'description', 
                  'wo_type', 'time_type', 'asset_description', 'asset_id', 'plant', 'hours',
                  'car_flag', 'day_name', 'is_weekend', 'created_at', 'updated_at']
    
    with open('Database/work_orders.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_orders)
    
    print(f"Updated work_orders.csv with {len(work_orders)} entries")
    return work_orders

def update_technicians(completed_orders: Dict[str, List[Dict]], pending_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame):
    """Update technicians.csv with technician data using actual data from operating logs"""
    print("Updating technicians.csv...")
    
    # Get all unique technicians
    all_techs = set(list(completed_orders.keys()) + list(pending_orders.keys()))
    
    technicians = []
    id_counter = 1
    
    for tech_name in all_techs:
        # Get actual data for this technician from operating logs
        tech_logs = operating_logs_df[operating_logs_df['User FSM.Name'] == tech_name]
        
        if len(tech_logs) > 0:
            # Get actual email from the data
            email = tech_logs['User FSM.Email'].iloc[0] if not pd.isna(tech_logs['User FSM.Email'].iloc[0]) else ''
            
            technician = {
                'id': id_counter,
                'tech_name': tech_name,
                'email': email,
                'phone': '',  # Not available in data
                'specialization': '',  # Not available in data
                'hire_date': '',  # Not available in data
                'status': 'Active',
                'created_at': '',
                'updated_at': ''
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

def create_test_data_files(pending_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame):
    """Create test data files for pending work orders using only actual data"""
    print("Creating test data files for pending work orders...")
    
    # Get all pending work order IDs
    pending_wo_ids = []
    for orders in pending_orders.values():
        for order in orders:
            pending_wo_ids.append(order['Name'])
    
    print(f"Pending work order IDs: {pending_wo_ids}")
    
    # Filter operating logs for pending work orders
    pending_logs = operating_logs_df[operating_logs_df['Work Order'].isin(pending_wo_ids)]
    
    # Sort logs by work order, technician, and log time
    pending_logs = pending_logs.sort_values(['Work Order', 'User FSM.Name', 'Log Time'])
    
    # Remove duplicates based on work_order_id + tech_name + work_date + notes
    pending_logs = pending_logs.drop_duplicates(subset=['Work Order', 'User FSM.Name', 'Log Time', 'Log Note'], keep='first')
    
    # Create test work status logs using only actual data
    test_work_status_logs = []
    id_counter = 1
    
    for _, row in pending_logs.iterrows():
        tech_name = row.get('User FSM.Name', '')
        if pd.isna(tech_name) or tech_name == '':
            continue
        
        # Use actual log time
        log_time = row.get('Log Time', '')
        if pd.isna(log_time):
            continue
        
        work_date = str(log_time)[:10]  # Extract YYYY-MM-DD
        log_datetime = str(log_time)
        
        # Use only actual data from operating logs
        work_status_log = {
            'id': id_counter,
            'work_order_id': row.get('Work Order', ''),
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('Status', ''),
            'time_spent': '',  # Not available in operating logs
            'notes': row.get('Log Note', ''),
            'summary': "",
            'description': row.get('Log Note', ''),
            'wo_type': row.get('Work Order.pffsm__WO_Type__c', ''),
            'asset_description': row.get('Plant Description', ''),
            'asset_id': row.get('Work Order', ''),
            'plant': row.get('Plant Description', ''),
            'email': row.get('Email', ''),
            'is_weekend': row.get('IsWeekend', ''),
            'wo_status': row.get('Work Order.pffsm__WO_Status__c', ''),
            'user_resource': row.get('Task Labor.pffsm__User_Resource__c', ''),
            'user_fsm_email': row.get('User FSM.Email', ''),
            'created_at': log_datetime,
            'updated_at': log_datetime
        }
        
        test_work_status_logs.append(work_status_log)
        id_counter += 1
    
    # Write test work status logs with all actual fields
    with open('Data/test_data/pending_work_status_logs_test.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 
                     'summary', 'description', 'wo_type', 'asset_description', 'asset_id', 'plant', 'email',
                     'car_flag', 'is_weekend', 'wo_status', 'user_resource', 'user_fsm_email',
                     'created_at', 'updated_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_work_status_logs)
    
    # Create test completion notes using only actual data
    test_completion_notes = []
    id_counter = 1
    
    # Group by work order to get one completion note per work order
    for work_order_id in pending_wo_ids:
        wo_logs = pending_logs[pending_logs['Work Order'] == work_order_id]
        if len(wo_logs) == 0:
            continue
        
        # Get the first log entry for this work order
        first_log = wo_logs.iloc[0]
        tech_name = first_log.get('User FSM.Name', '')
        completion_notes = first_log.get('Work Order: Completion Notes', '')
        
        # Use actual log time
        log_time = first_log.get('Log Time', '')
        if pd.isna(log_time):
            continue
        
        work_date = str(log_time)[:10]  # Extract YYYY-MM-DD
        log_datetime = str(log_time)
        
        completion_note = {
            'id': id_counter,
            'work_order_id': work_order_id,
            'tech_name': tech_name,
            'work_date': work_date,
            'completion_notes': completion_notes,
            'wo_type': first_log.get('Work Order.pffsm__WO_Type__c', ''),
            'time_type': 'Work',
            'description': "",
            'asset_description': first_log.get('Plant Description', ''),
            'asset_id': work_order_id,
            'plant': first_log.get('Plant Description', ''),
            'created_at': log_datetime
        }
        
        test_completion_notes.append(completion_note)
        id_counter += 1
    
    # Write test completion notes with actual fields
    with open('Data/test_data/pending_completion_notes_test.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'completion_notes', 'wo_type', 'time_type',
                     'description', 'asset_description', 'asset_id', 'plant', 'created_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_completion_notes)
    
    print(f"Created test data files using only actual data:")
    print(f"  - Test work status logs: {len(test_work_status_logs)} entries")
    print(f"  - Test completion notes: {len(test_completion_notes)} entries")
    print(f"  - All data sourced directly from Excel file")
    print(f"  - Logs sorted by work order, technician, and log time")

def update_work_status_logs(completed_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame):
    """Update work_status_logs.csv with completed work orders only using actual data"""
    print("Updating work_status_logs.csv with completed work orders...")
    
    # Get all completed work order IDs
    completed_wo_ids = []
    for orders in completed_orders.values():
        for order in orders:
            completed_wo_ids.append(order['Name'])
    
    # Filter operating logs for completed work orders only
    completed_logs = operating_logs_df[operating_logs_df['Work Order'].isin(completed_wo_ids)]
    
    # Sort logs by work order, technician, and log time
    completed_logs = completed_logs.sort_values(['Work Order', 'User FSM.Name', 'Log Time'])
    
    # Remove duplicates based on work_order_id + tech_name + work_date + notes
    completed_logs = completed_logs.drop_duplicates(subset=['Work Order', 'User FSM.Name', 'Log Time', 'Log Note'], keep='first')
    
    work_status_logs = []
    id_counter = 1
    
    for _, row in completed_logs.iterrows():
        tech_name = row.get('User FSM.Name', '')
        if pd.isna(tech_name) or tech_name == '':
            continue
        
        # Use actual log time
        log_time = row.get('Log Time', '')
        if pd.isna(log_time):
            continue
        
        work_date = str(log_time)[:10]  # Extract YYYY-MM-DD
        log_datetime = str(log_time)
        
        work_status_log = {
            'id': id_counter,
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('Status', ''),
            'time_spent': '',  # Not available in operating logs
            'notes': str(row.get('Log Note', '')) + " with details: " + str(row.get('Log Details', '')),
            'summary': "",
            'work_order_id': row.get('Work Order', ''),
            'email': row.get('Email', ''),
            'plant_description': row.get('Plant Description', ''),
            'day_name': row.get('Day Name', ''),
            'operating_log_id': row.get('Operating Log: Operating Log ID', ''),
            'car_flag': row.get('CAR_Flag', ''),
            'is_weekend': row.get('IsWeekend', ''),
            'wo_status': row.get('Work Order.pffsm__WO_Status__c', ''),
            'wo_type': row.get('Work Order.pffsm__WO_Type__c', ''),
            'user_resource': row.get('Task Labor.pffsm__User_Resource__c', ''),
            'user_fsm_email': row.get('User FSM.Email', ''),
            'created_at': log_datetime,
            'updated_at': log_datetime
        }
        
        work_status_logs.append(work_status_log)
        id_counter += 1
    
    # Write to CSV with all actual fields
    fieldnames = ['id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 'summary', 'work_order_id', 
                 'email', 'plant_description', 'day_name', 'operating_log_id', 
                 'car_flag', 'is_weekend', 'wo_status', 'wo_type',
                 'user_resource', 'user_fsm_email', 'created_at', 'updated_at']
    
    with open('Database/work_status_logs.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_status_logs)
    
    print(f"Updated work_status_logs.csv with {len(work_status_logs)} entries")
    return work_status_logs

def update_completion_notes(completed_orders: Dict[str, List[Dict]], work_orders_df: pd.DataFrame):
    """Update completion_notes.csv with completed work orders only using actual data"""
    print("Updating completion_notes.csv with completed work orders...")
    
    # Get all completed work order IDs
    completed_wo_ids = []
    for orders in completed_orders.values():
        for order in orders:
            completed_wo_ids.append(order['Name'])
    
    # Filter work orders for completed work orders only
    completed_wo_data = work_orders_df[work_orders_df['Name'].isin(completed_wo_ids)]
    
    # Remove duplicates based on work_order_id + tech_name + work_date + notes
    # For completion notes, we'll use work_order_id + work_date + completion_notes since tech_name is not available
    completed_wo_data = completed_wo_data.drop_duplicates(subset=['Name', 'pffsm__Completion_Date__c', 'pffsm__Completion_Notes__c'], keep='first')
    
    completion_notes = []
    id_counter = 1
    
    for _, row in completed_wo_data.iterrows():
        # Use actual completion date
        completion_date = row.get('pffsm__Completion_Date__c', '')
        if pd.isna(completion_date) or completion_date == '':
            work_date = ''
        else:
            work_date = str(completion_date)[:10]  # Extract YYYY-MM-DD
        
        # Use actual completion notes
        notes = row.get('pffsm__Completion_Notes__c', '')
        
        # Use actual technician name from the work order data (if available)
        tech_name = ''  # Not directly available in work orders sheet
        
        completion_note = {
            'id': id_counter,
            'completion_notes': notes,
            'wo_type': row.get('pffsm__WO_Type__c', ''),
            'time_type': 'Work',
            'work_order_id': row.get('Name', ''),
            'tech_name': tech_name,
            'work_date': work_date,
            'plant': row.get('pffsm__Plant__c', ''),
            'hours': row.get('pffsm__Total_Actual_Labor_Hours__c', ''),
            'status': row.get('pffsm__Status__c', ''),
            'car_flag': row.get('CAR_Flag', ''),
            'day_name': row.get('Day Name', ''),
            'is_weekend': row.get('IsWeekend', ''),
            'created_at': work_date + ' 08:00:00' if work_date else ''
        }
        
        completion_notes.append(completion_note)
        id_counter += 1
    
    # Write to CSV with all actual fields
    fieldnames = ['id', 'completion_notes', 'wo_type', 'time_type', 'work_order_id', 'tech_name', 'work_date', 
                 'plant', 'hours', 'status', 'car_flag', 'day_name', 'is_weekend', 'created_at']
    
    with open('Database/completion_notes.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(completion_notes)
    
    print(f"Updated completion_notes.csv with {len(completion_notes)} entries")
    return completion_notes

def check_and_remove_duplicates():
    """Check and remove duplicates from all database files"""
    print("Checking and removing duplicates from database files...")
    
    # Check work_orders.csv
    if os.path.exists('Database/work_orders.csv'):
        df_orders = pd.read_csv('Database/work_orders.csv')
        original_count = len(df_orders)
        df_orders = df_orders.drop_duplicates(subset=['work_order_id'], keep='first')
        df_orders = df_orders.drop_duplicates(subset=['id'], keep='first')
        if len(df_orders) < original_count:
            df_orders.to_csv('Database/work_orders.csv', index=False)
            print(f"  Removed {original_count - len(df_orders)} duplicates from work_orders.csv")
    
    # Check work_status_logs.csv
    if os.path.exists('Database/work_status_logs.csv'):
        df_logs = pd.read_csv('Database/work_status_logs.csv')
        original_count = len(df_logs)
        df_logs = df_logs.drop_duplicates(subset=['work_order_id', 'tech_name', 'work_date', 'notes'], keep='first')
        df_logs = df_logs.drop_duplicates(subset=['id'], keep='first')
        if len(df_logs) < original_count:
            df_logs.to_csv('Database/work_status_logs.csv', index=False)
            print(f"  Removed {original_count - len(df_logs)} duplicates from work_status_logs.csv")
    
    # Check completion_notes.csv
    if os.path.exists('Database/completion_notes.csv'):
        df_notes = pd.read_csv('Database/completion_notes.csv')
        original_count = len(df_notes)
        df_notes = df_notes.drop_duplicates(subset=['work_order_id', 'work_date', 'completion_notes'], keep='first')
        df_notes = df_notes.drop_duplicates(subset=['id'], keep='first')
        if len(df_notes) < original_count:
            df_notes.to_csv('Database/completion_notes.csv', index=False)
            print(f"  Removed {original_count - len(df_notes)} duplicates from completion_notes.csv")
    
    # Check technicians.csv
    if os.path.exists('Database/technicians.csv'):
        df_techs = pd.read_csv('Database/technicians.csv')
        original_count = len(df_techs)
        df_techs = df_techs.drop_duplicates(subset=['tech_name'], keep='first')
        df_techs = df_techs.drop_duplicates(subset=['id'], keep='first')
        if len(df_techs) < original_count:
            df_techs.to_csv('Database/technicians.csv', index=False)
            print(f"  Removed {original_count - len(df_techs)} duplicates from technicians.csv")
    
    print("  ✅ Duplicate removal completed")

def main():
    """Main function to update all database files with new logic"""
    print("Starting enhanced database update with Origis Data Excel file...")
    
    try:
        # Extract work orders by type from Excel file
        work_orders_df, operating_logs_df, top_technicians = extract_work_orders_by_type()
        
        if len(work_orders_df) == 0:
            print("No work orders found!")
            return
        
        # Select work orders per employee (3 from each type if available, otherwise keep available amount)
        employee_work_orders = select_work_orders_per_employee(work_orders_df, operating_logs_df, top_technicians)
        
        if not employee_work_orders:
            print("No work orders selected for any employee!")
            return
        
        # Split into completed (50%) and pending (50%)
        completed_orders, pending_orders = split_work_orders_by_status(employee_work_orders)
        
        # Update all database files
        work_orders = update_work_orders(completed_orders, pending_orders)
        technicians = update_technicians(completed_orders, pending_orders, operating_logs_df)
        work_status_logs = update_work_status_logs(completed_orders, operating_logs_df)
        completion_notes = update_completion_notes(completed_orders, work_orders_df)
        
        # Create test data files for pending work orders
        create_test_data_files(pending_orders, operating_logs_df)
        
        # Check and remove any remaining duplicates from all database files
        check_and_remove_duplicates()
        
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
        print(f"   - Top 3 Technicians: {list(top_technicians.index)}")
        print(f"   - Operating logs sorted by work order, technician, and log time")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
