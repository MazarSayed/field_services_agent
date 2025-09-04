#!/usr/bin/env python3
"""
Enhanced Database Update Script
Extracts work orders from Origis Data 1 Excel file and updates the database files
with the following logic:
- Select top 3 technicians based on log activity
- For each technician, select work orders from 5 types: Preventive, Corrective, Ad Hoc, Project, OEM Repair Work
- Include work order description, plant, and hours information
- Split work orders 50/50 between completed and pending
- Move pending work order logs and completion notes to test data
- Keep completed work order logs in the main database
- Sort operating logs by date/time within each work order x technician combination
- Uses updated column structure from Origis Data 1.xlsx
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
    """Extract work orders of different types from Origis Data 1 Excel file"""
    print("Reading Origis Data 1 Excel file...")
    
    # Read the Excel file with both sheets
    work_orders_df = pd.read_excel("Data/Origis_Data 1.xlsx", sheet_name='Work Orders')
    operating_logs_df = pd.read_excel("Data/Origis_Data 1.xlsx", sheet_name='Operating logs')
    
    print(f"Work Orders sheet: {work_orders_df.shape}")
    print(f"Operating Logs sheet: {operating_logs_df.shape}")
    
    # Filter for main work order types
    main_types = ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']
    filtered_wo = work_orders_df[work_orders_df['pffsm__WO_Type__c'].isin(main_types)]
    
    print(f"Found {len(filtered_wo)} work orders of main types")
    print(f"Work order types: {filtered_wo['pffsm__WO_Type__c'].value_counts().to_dict()}")
    
    # Create OwnerId to technician name mapping
    owner_mapping = operating_logs_df[['OwnerId', 'Work Order.pffsm__Assigned_User_Name_Text__c']].dropna()
    owner_mapping = owner_mapping.drop_duplicates()
    owner_to_name = dict(zip(owner_mapping['OwnerId'], owner_mapping['Work Order.pffsm__Assigned_User_Name_Text__c']))
    
    print(f"Created OwnerId to name mapping for {len(owner_to_name)} technicians")
    
    # Get top 3 technicians by log activity using OwnerId
    top_owner_ids = operating_logs_df['OwnerId'].value_counts().head(3)
    print(f"Top 3 OwnerIds by activity: {top_owner_ids.to_dict()}")
    
    # Get technician names for top OwnerIds
    top_technician_names = {}
    for owner_id in top_owner_ids.index:
        if owner_id in owner_to_name:
            top_technician_names[owner_to_name[owner_id]] = owner_id
        else:
            # If no name mapping, use OwnerId as name
            top_technician_names[owner_id] = owner_id
    
    print(f"Top 3 technicians: {top_technician_names}")
    
    # Filter operating logs for top 3 OwnerIds
    filtered_logs = operating_logs_df[operating_logs_df['OwnerId'].isin(top_owner_ids.index)]
    
    # Get work orders that have logs from our top 3 technicians
    wo_with_logs = filtered_logs['Work Order.Name'].unique()
    final_work_orders = filtered_wo[filtered_wo['Name'].isin(wo_with_logs)]
    
    print(f"Work orders with logs from top 3 technicians: {len(final_work_orders)}")
    
    return final_work_orders, filtered_logs, top_owner_ids, owner_to_name

def select_work_orders_per_employee(work_orders_df: pd.DataFrame, operating_logs_df: pd.DataFrame, top_owner_ids: pd.Series, owner_to_name: dict) -> Dict[str, List[Dict]]:
    """Select work orders per employee based on their operating logs using OwnerId"""
    print("Selecting work orders per employee...")
    
    employee_work_orders = {}
    
    # For each top OwnerId, get their work orders from operating logs
    for owner_id in top_owner_ids.index:
        # Get technician name from OwnerId
        tech_name = owner_to_name.get(owner_id, owner_id)
        print(f"\nProcessing employee: {tech_name} (OwnerId: {owner_id})")
        
        # Get work orders this technician has logs for using OwnerId
        tech_logs = operating_logs_df[operating_logs_df['OwnerId'] == owner_id]
        tech_work_orders = tech_logs['Work Order.Name'].unique()
        
        print(f"  Found {len(tech_work_orders)} work orders with logs")
        
        # Get work order details for these work orders
        tech_wo_details = work_orders_df[work_orders_df['Name'].isin(tech_work_orders)]
        
        # Group by work order type and select up to 3 from each type
        selected_orders = []
        
        for wo_type in ['Preventive', 'Corrective', 'Ad Hoc', 'Project', 'OEM Repair Work']:
            type_orders = tech_wo_details[tech_wo_details['pffsm__WO_Type__c'] == wo_type]
            
            if len(type_orders) >= 5:
                # Randomly select 5
                selected = type_orders.sample(n=5, random_state=42)
                selected_orders.extend(selected.to_dict('records'))
                print(f"    Selected 5 {wo_type} work orders")
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
            completion_date = order.get('CreatedDate', '')
            if pd.isna(completion_date) or completion_date == '':
                work_date = ''
            else:
                work_date = str(completion_date)[:10]  # Extract YYYY-MM-DD
            
            work_order = {
                'id': id_counter,
                'work_order_id': order['Name'],
                'tech_name': tech_name,
                'status': 'Completed',  # Default status for completed orders
                'work_date': work_date,
                'description': order.get('pffsm__Description__c', ''),
                'wo_type': order.get('pffsm__WO_Type__c', ''),
                'time_type': 'Work',
                'asset_description': order.get('pffsm__Equip_Description__c', ''),
                'asset_id': order.get('pffsm__Asset_ID_Text__c', ''),
                'plant': order.get('pffsm__Plant__c', ''),
                'hours': order.get('pffsm__Total_Actual_Labor_Hours__c', ''),
                'created_at': work_date + ' 08:00:00' if work_date else '',
                'updated_at': work_date + ' 08:00:00' if work_date else ''
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Process pending orders
    for tech_name, orders in pending_orders.items():
        for order in orders:
            # Use actual data from work order
            completion_date = order.get('CreatedDate', '')
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
                'description': order.get('pffsm__Description__c', ''),
                'wo_type': order.get('pffsm__WO_Type__c', ''),
                'time_type': 'Work',
                'asset_description': order.get('pffsm__Equip_Description__c', ''),
                'asset_id': order.get('pffsm__Asset_ID_Text__c', ''),
                'plant': order.get('pffsm__Plant__c', ''),
                'hours': order.get('pffsm__Total_Actual_Labor_Hours__c', ''),
                'created_at': work_date + ' 08:00:00' if work_date else '',
                'updated_at': work_date + ' 08:00:00' if work_date else ''
            }
            
            work_orders.append(work_order)
            id_counter += 1
    
    # Write to CSV
    fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'status', 'description', 
                  'wo_type', 'time_type', 'asset_description', 'asset_id', 'plant', 'hours',
                  'created_at', 'updated_at']
    
    with open('Database/work_orders.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_orders)
    
    print(f"Updated work_orders.csv with {len(work_orders)} entries")
    return work_orders

def update_technicians(completed_orders: Dict[str, List[Dict]], pending_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame, owner_to_name: dict):
    """Update technicians.csv with technician data using OwnerId mapping"""
    print("Updating technicians.csv...")
    
    # Get all unique technicians
    all_techs = set(list(completed_orders.keys()) + list(pending_orders.keys()))
    
    technicians = []
    id_counter = 1
    
    for tech_name in all_techs:
        # Find OwnerId for this technician name
        owner_id = None
        for oid, name in owner_to_name.items():
            if name == tech_name:
                owner_id = oid
                break
        
        if owner_id:
            # Get actual data for this technician from operating logs using OwnerId
            tech_logs = operating_logs_df[operating_logs_df['OwnerId'] == owner_id]
            
            if len(tech_logs) > 0:
                # Get actual email from the data (not available in new structure, so leave empty)
                email = ''
                
                technician = {
                    'id': id_counter,
                    'tech_name': tech_name,
                    'owner_id': owner_id,  # Add OwnerId for reference
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
    fieldnames = ['id', 'tech_name', 'owner_id', 'email', 'phone', 'specialization', 'hire_date', 'status', 'created_at', 'updated_at']
    
    with open('Database/technicians.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(technicians)
    
    print(f"Updated technicians.csv with {len(technicians)} entries")
    return technicians

def create_test_data_files(pending_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame, work_orders_df: pd.DataFrame, owner_to_name: dict):
    """Create test data files for pending work orders using only actual data"""
    print("Creating test data files for pending work orders...")
    
    # Get all pending work order IDs
    pending_wo_ids = []
    for orders in pending_orders.values():
        for order in orders:
            pending_wo_ids.append(order['Name'])
    
    print(f"Pending work order IDs: {pending_wo_ids}")
    
    # Filter operating logs for pending work orders using correct column name
    pending_logs = operating_logs_df[operating_logs_df['Work Order.Name'].isin(pending_wo_ids)]
    
    # Sort logs by work order, OwnerId, and log time using correct column names
    pending_logs = pending_logs.sort_values(['Work Order.Name', 'OwnerId', 'pffsm__Log_Time__c'])

    print(f"Pending logs: {pending_logs.shape}")
    # Remove duplicates based on work_order_id + owner_id + work_date + notes using correct column names
    pending_logs = pending_logs.drop_duplicates(subset=['Work Order.Name', 'OwnerId', 'pffsm__Log_Time__c', 'pffsm__Log_Note__c'], keep='first')
    
    print(f"Pending logs after duplicates: {pending_logs.shape}")
    
    # Create test work status logs using only actual data
    test_work_status_logs = []
    id_counter = 1
    
    for _, row in pending_logs.iterrows():
        owner_id = row.get('OwnerId', '')
        tech_name = owner_to_name.get(owner_id, owner_id)  # Get name from OwnerId mapping
        if pd.isna(owner_id) or owner_id == '':
            continue
        
        # Use actual log time
        log_time = row.get('pffsm__Log_Time__c', '')
        if pd.isna(log_time):
            continue
        
        work_date = str(log_time)[:10]  # Extract YYYY-MM-DD
        log_datetime = str(log_time)
        
        # Use only actual data from operating logs with new column names
        work_status_log = {
            'id': id_counter,
            'work_order_id': row.get('Work Order.Name', ''),
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('pffsm__Status__c', ''),
            'time_spent': '',  # Not available in operating logs
            'notes': str(row.get('pffsm__Log_Note__c', '')) + " with details: " + str(row.get('Log_Details__c', '')),
            'summary': "",
            'description': row.get('pffsm__Log_Note__c', ''),
            'wo_type': row.get('Work Order.pffsm__WO_Type__c', ''),
            'asset_description': row.get('pffsm__Plant_Description__c', ''),
            'asset_id': row.get('Work Order.Name', ''),
            'plant': row.get('Work Order.pffsm__Plant__c', ''),
            'email': '',  # Not available in new structure
            'is_weekend': '',  # Not available in new structure
            'wo_status': row.get('Work Order.pffsm__Status__c', ''),
            'user_resource': '',  # Not available in new structure
            'user_fsm_email': '',  # Not available in new structure
            'created_at': log_datetime,
            'updated_at': log_datetime
        }
        
        test_work_status_logs.append(work_status_log)
        id_counter += 1
    
    # Write test work status logs with all actual fields
    with open('Data/test_data/pending_work_status_logs_test.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'work_order_id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 
                     'summary', 'description', 'wo_type', 'asset_description', 'asset_id', 'plant', 'email',
                     'is_weekend', 'wo_status', 'user_resource', 'user_fsm_email',
                     'created_at', 'updated_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_work_status_logs)
    
    # Create test completion notes using work order data for completion comments
    test_completion_notes = []
    id_counter = 1
    
    # Get work order data for pending work orders
    pending_wo_data = work_orders_df[work_orders_df['Name'].isin(pending_wo_ids)]
    
    for _, wo_row in pending_wo_data.iterrows():
        work_order_id = wo_row.get('Name', '')
        
        # Get technician name from the first log entry for this work order
        wo_logs = pending_logs[pending_logs['Work Order.Name'] == work_order_id]
        if len(wo_logs) > 0:
            first_log = wo_logs.iloc[0]
            owner_id = first_log.get('OwnerId', '')
            tech_name = owner_to_name.get(owner_id, owner_id)
        else:
            # If no logs, try to get from work order assigned user
            tech_name = wo_row.get('pffsm__Assigned_User_Name_Text__c', '')
            if pd.isna(tech_name) or tech_name == '':
                continue
        
        # Use completion notes from work order table
        completion_notes = wo_row.get('pffsm__Completion_Notes__c', '')
        
        # Use creation date from work order
        creation_date = wo_row.get('CreatedDate', '')
        if pd.isna(creation_date) or creation_date == '':
            work_date = ''
        else:
            work_date = str(creation_date)[:10]  # Extract YYYY-MM-DD
        
        completion_note = {
            'id': id_counter,
            'work_order_id': work_order_id,
            'tech_name': tech_name,
            'work_date': work_date,
            'completion_notes': completion_notes,
            'wo_type': wo_row.get('pffsm__WO_Type__c', ''),  # Use correct WO type from work orders
            'time_type': 'Work',
            'description': "",
            'asset_description': wo_row.get('pffsm__Equip_Description__c', ''),
            'asset_id': work_order_id,
            'plant': wo_row.get('pffsm__Plant__c', ''),
            'created_at': work_date + ' 08:00:00' if work_date else ''
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

def update_work_status_logs(completed_orders: Dict[str, List[Dict]], operating_logs_df: pd.DataFrame, owner_to_name: dict):
    """Update work_status_logs.csv with completed work orders only using actual data"""
    print("Updating work_status_logs.csv with completed work orders...")
    
    # Get all completed work order IDs
    completed_wo_ids = []
    for orders in completed_orders.values():
        for order in orders:
            completed_wo_ids.append(order['Name'])
    
    # Filter operating logs for completed work orders only using correct column name
    completed_logs = operating_logs_df[operating_logs_df['Work Order.Name'].isin(completed_wo_ids)]
    
    # Sort logs by work order, OwnerId, and log time using correct column names
    completed_logs = completed_logs.sort_values(['Work Order.Name', 'OwnerId', 'pffsm__Log_Time__c'])
    
    # Remove duplicates based on work_order_id + owner_id + work_date + notes using correct column names
    completed_logs = completed_logs.drop_duplicates(subset=['Work Order.Name', 'OwnerId', 'pffsm__Log_Time__c', 'pffsm__Log_Note__c'], keep='first')
    
    work_status_logs = []
    id_counter = 1
    
    for _, row in completed_logs.iterrows():
        owner_id = row.get('OwnerId', '')
        tech_name = owner_to_name.get(owner_id, owner_id)  # Get name from OwnerId mapping
        if pd.isna(owner_id) or owner_id == '':
            continue
        
        # Use actual log time
        log_time = row.get('pffsm__Log_Time__c', '')
        if pd.isna(log_time):
            continue
        
        work_date = str(log_time)[:10]  # Extract YYYY-MM-DD
        log_datetime = str(log_time)
        
        work_status_log = {
            'id': id_counter,
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': row.get('pffsm__Status__c', ''),
            'time_spent': '',  # Not available in operating logs
            'notes': str(row.get('pffsm__Log_Note__c', '')) + " with details: " + str(row.get('Log_Details__c', '')),
            'summary': "",
            'work_order_id': row.get('Work Order.Name', ''),
            'email': '',  # Not available in new structure
            'plant_description': row.get('pffsm__Plant_Description__c', ''),
            'day_name': '',  # Not available in new structure
            'operating_log_id': row.get('Id', ''),
            'car_flag': '',  # Not available in new structure
            'is_weekend': '',  # Not available in new structure
            'wo_status': row.get('Work Order.pffsm__Status__c', ''),
            'wo_type': row.get('Work Order.pffsm__WO_Type__c', ''),
            'user_resource': '',  # Not available in new structure
            'user_fsm_email': '',  # Not available in new structure
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
    
    # Remove duplicates based on work_order_id + work_date + completion_notes using new column names
    completed_wo_data = completed_wo_data.drop_duplicates(subset=['Name', 'CreatedDate', 'pffsm__Completion_Comments__c'], keep='first')
    
    completion_notes = []
    id_counter = 1
    
    for _, row in completed_wo_data.iterrows():
        # Use actual creation date
        creation_date = row.get('CreatedDate', '')
        if pd.isna(creation_date) or creation_date == '':
            work_date = ''
        else:
            work_date = str(creation_date)[:10]  # Extract YYYY-MM-DD
        
        # Use actual completion notes
        notes = row.get('pffsm__Completion_Notes__c', '')
        
        # Use actual technician name from the work order data
        tech_name = row.get('pffsm__Assigned_User_Name_Text__c', '')
        
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
            'status': 'Completed',  # Default status for completed orders
            'car_flag': '',  # Not available in new structure
            'day_name': '',  # Not available in new structure
            'is_weekend': '',  # Not available in new structure
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
    print("Starting enhanced database update with Origis Data 1 Excel file...")
    
    try:
        # Extract work orders by type from Excel file
        work_orders_df, operating_logs_df, top_owner_ids, owner_to_name = extract_work_orders_by_type()
        
        if len(work_orders_df) == 0:
            print("No work orders found!")
            return
        
        # Select work orders per employee (5 from each type if available, otherwise keep available amount)
        employee_work_orders = select_work_orders_per_employee(work_orders_df, operating_logs_df, top_owner_ids, owner_to_name)
        
        if not employee_work_orders:
            print("No work orders selected for any employee!")
            return
        
        # Split into completed (50%) and pending (50%)
        completed_orders, pending_orders = split_work_orders_by_status(employee_work_orders)
        
        # Update all database files
        work_orders = update_work_orders(completed_orders, pending_orders)
        technicians = update_technicians(completed_orders, pending_orders, operating_logs_df, owner_to_name)
        work_status_logs = update_work_status_logs(completed_orders, operating_logs_df, owner_to_name)
        completion_notes = update_completion_notes(completed_orders, work_orders_df)
        
        # Create test data files for pending work orders
        create_test_data_files(pending_orders, operating_logs_df, work_orders_df, owner_to_name)
        
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
        print(f"   - Top 3 OwnerIds: {list(top_owner_ids.index)}")
        print(f"   - Operating logs sorted by work order, OwnerId, and log time")
        print(f"   - Using Origis Data 1.xlsx with OwnerId-based technician identification")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
