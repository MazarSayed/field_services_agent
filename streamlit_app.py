"""
Work Order Logging App
Streamlit application for field technicians to log work activities
"""

import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Optional
import json

# Import API client
from src.api_client import get_api_client

# Page configuration
st.set_page_config(
    page_title="Work Order Logging App", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client
@st.cache_resource
def get_api():
    return get_api_client()

api_client = get_api()

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'current_tech' not in st.session_state:
        st.session_state.current_tech = None
    if 'current_date' not in st.session_state:
        st.session_state.current_date = datetime.now().date()
    if 'work_orders' not in st.session_state:
        st.session_state.work_orders = []
    if 'selected_work_order' not in st.session_state:
        st.session_state.selected_work_order = None
    if 'work_entries' not in st.session_state:
        st.session_state.work_entries = []
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'notes_validated' not in st.session_state:
        st.session_state.notes_validated = False

init_session_state()

# ========================================
# SIDEBAR - CONFIGURATION
# ========================================

st.sidebar.header("🔧 Configuration")

# API Health Check
with st.sidebar:
    if api_client.health_check():
        st.success("✅ API Connected")
    else:
        st.error("❌ API Disconnected")
        st.info("Start API: `python main.py`")

# Step 1: Select Technician
    st.sidebar.subheader("👷 Select Technician")
    technicians_data = api_client.get_technicians()
    
    if technicians_data:
        # Create more informative technician options
        tech_options = ["-- Select Technician --"]
        tech_mapping = {"-- Select Technician --": None}
        
        for tech in technicians_data:
            tech_name = tech.get('tech_name', '')
            specialization = tech.get('specialization', '')
            display_name = f"{tech_name} - {specialization}"
            tech_options.append(display_name)
            tech_mapping[display_name] = tech_name
    
    selected_tech_display = st.sidebar.selectbox(
            "Technician",
            tech_options,
            key="tech_selector"
        )

    if selected_tech_display != "-- Select Technician --":
        st.session_state.current_tech = tech_mapping[selected_tech_display]
        
        # Show selected technician info
        selected_tech_data = next((tech for tech in technicians_data if tech.get('tech_name') == st.session_state.current_tech), None)
        if selected_tech_data:
            st.sidebar.success(f"✅ Selected: {selected_tech_data.get('tech_name')}")
            st.sidebar.caption(f"📧 {selected_tech_data.get('email', 'N/A')}")
            st.sidebar.caption(f"🔧 {selected_tech_data.get('specialization', 'N/A')}")
    else:
        st.sidebar.error("Could not load technicians")
        st.stop()

# Step 2: Select Date
st.sidebar.subheader("📅 Work Date")
work_date = st.sidebar.date_input(
    "Date",
    value=st.session_state.current_date,
            key="date_selector"
        )
st.session_state.current_date = work_date

# Step 3: Fetch Work Orders
if st.session_state.current_tech:
    st.sidebar.subheader("📋 Work Orders")
    
    if st.sidebar.button("🔄 Load All Work Orders"):
        work_orders_response = api_client.get_all_work_orders(st.session_state.current_tech)
        
        if work_orders_response and work_orders_response.get('work_orders'):
            st.session_state.work_orders = work_orders_response['work_orders']
            st.sidebar.success(f"✅ Found {len(st.session_state.work_orders)} work orders")
        else:
            st.session_state.work_orders = []
            st.sidebar.warning("No work orders found for this technician")
    
    # Display work order stats
    if st.session_state.work_orders:
        pending = len([wo for wo in st.session_state.work_orders if wo.get('status', '').lower() in ['pending', 'open', 'assigned']])
        completed = len([wo for wo in st.session_state.work_orders if wo.get('status', '').lower() in ['completed', 'closed', 'finished']])
        
        col1, col2, col3 = st.sidebar.columns(3)
        col1.metric("Total", len(st.session_state.work_orders))
        col2.metric("Pending", pending)
        col3.metric("Completed", completed)

# ========================================
# MAIN APPLICATION
# ========================================

st.title("📋 Work Order Logging App")
st.markdown(f"**Technician:** {st.session_state.current_tech or 'Not Selected'} | **Date:** {work_date.strftime('%Y-%m-%d')}")

# Check if configuration is complete
if not st.session_state.current_tech:
    st.info("👈 Please select a technician from the sidebar to begin")
    st.stop()

if not st.session_state.work_orders:
    st.info("👈 Please load all work orders from the sidebar")
    st.stop()

# Work Order Selection
st.header("1️⃣ Select Work Order")

wo_options = ["-- Select Work Order --"]
wo_mapping = {}

for wo in st.session_state.work_orders:
    wo_id = wo.get('work_order_id', '')
    description = wo.get('description', '')
    status = wo.get('status', '')
    wo_type = wo.get('wo_type', '')
    work_date = wo.get('work_date', '')
    
    display_text = f"{wo_id} - {description[:45]}{'...' if len(description) > 45 else ''} | {work_date} | [{status}] ({wo_type})"
    wo_options.append(display_text)
    wo_mapping[display_text] = wo

selected_wo_display = st.selectbox(
    "Choose work order to log activities for:",
    wo_options,
    key="wo_selector"
)
            
if selected_wo_display != "-- Select Work Order --":
    st.session_state.selected_work_order = wo_mapping[selected_wo_display]
    selected_wo = st.session_state.selected_work_order
    
    # Display work order details
    with st.expander("📄 Work Order Details", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Work Order ID", selected_wo.get('work_order_id', 'N/A'))
            st.metric("Type", selected_wo.get('wo_type', 'N/A'))
        with col2:
            st.metric("Status", selected_wo.get('status', 'N/A'))
            st.metric("Time Type", selected_wo.get('time_type', 'N/A'))
        with col3:
            st.metric("Technician", selected_wo.get('tech_name', 'N/A'))
            st.metric("Date", selected_wo.get('work_date', 'N/A'))
        
        if selected_wo.get('description'):
            st.markdown("**Description:**")
            st.info(selected_wo.get('description'))

# ========================================
# TABBED INTERFACE
# ========================================

if st.session_state.selected_work_order:
    tab1, tab2, tab3 = st.tabs(["🆕 New Entry", "📚 History", "✅ Complete Work Order"])
    
    # ========================================
    # TAB 1: NEW ENTRY
    # ========================================
    with tab1:
        st.header("Add New Work Entry")
        
        # Entry Form
        col1, col2 = st.columns(2)
        
        with col1:
            entry_date = st.date_input(
                "📅 Date of Work",
                value=work_date,
                key="entry_date"
            )
            
            start_time = st.time_input(
                "🕐 Start Time",
                value=time(9, 0),
                key="start_time"
            )
            
        with col2:
            end_time = st.time_input(
                "🕐 End Time",
                value=time(17, 0),
                key="end_time"
            )
            
            # Calculate total hours
            start_datetime = datetime.combine(entry_date, start_time)
            end_datetime = datetime.combine(entry_date, end_time)
            
            if end_datetime > start_datetime:
                total_hours = (end_datetime - start_datetime).total_seconds() / 3600
                st.metric("⏱️ Total Hours", f"{total_hours:.2f}")
            else:
                st.error("End time must be after start time")
                total_hours = 0
    
    # Work Status Selection
    st.subheader("📊 Work Status")
        work_status_types = api_client.get_work_status_types()
        
        if work_status_types:
            status_options = [status.get('status_type', '') for status in work_status_types]
            # Show descriptions on hover
            status_descriptions = {status.get('status_type', ''): status.get('description', '') for status in work_status_types}
        else:
            status_options = ["Troubleshooting", "Warranty_Support", "Work", "Delay", "Training"]
            status_descriptions = {}
        
        selected_status = st.selectbox(
            "Select work status:",
            status_options,
            key="work_status"
        )
        
        # Show status description
        if selected_status and selected_status in status_descriptions:
            st.caption(f"📝 {status_descriptions[selected_status]}")
        
        # Notes Entry - Chat Interface
        st.subheader("💬 Notes Entry")
        
        # Chat history display
        if st.session_state.chat_history:
            st.markdown("**Conversation:**")
            for i, message in enumerate(st.session_state.chat_history):
                if message['role'] == 'user':
                    st.markdown(f"**You:** {message['content']}")
                else:
                    st.markdown(f"**AI:** {message['content']}")
        
        # Notes input
        user_input = st.text_area(
            "Enter your notes:",
            height=150,
            placeholder="Describe the work performed, issues encountered, actions taken...",
            key="notes_input"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💬 Send Notes", type="primary"):
                if user_input.strip():
                    # Add user message to chat history
                    st.session_state.chat_history.append({
                        'role': 'user',
                        'content': user_input
                    })
                    
                    # Validate notes with AI
                    with st.spinner("🤖 AI is reviewing your notes..."):
                    validation_result = api_client.validate_work_status(
                                operational_log=user_input,
                                work_status=selected_status,
                                work_order_description=st.session_state.selected_work_order.get('description', ''),
                                tech_name=st.session_state.current_tech,
                                work_date=entry_date.strftime("%Y-%m-%d"),
                        follow_up_questions_answers=""
                    )
                    
                    if validation_result:
                        if validation_result.get('valid', False):
                            st.session_state.chat_history.append({
                                'role': 'ai',
                                'content': "✅ Your notes are complete and contain all required information!"
                            })
                            st.session_state.notes_validated = True
                    else:
                            # AI asks follow-up questions
                            missing_info = validation_result.get('missing', '')
                            follow_up_questions = validation_result.get('follow_up_questions', [])
                            
                            ai_response = f"I need more information. Missing: {missing_info}\n\n"
                            if follow_up_questions:
                                ai_response += "Please answer these questions:\n"
                                for i, question in enumerate(follow_up_questions[:2], 1):
                                    ai_response += f"{i}. {question}\n"
                            
                            st.session_state.chat_history.append({
                                'role': 'ai',
                                'content': ai_response
                            })
                    
                    # Clear input and rerun
                    st.session_state.notes_input = ""
                    st.rerun()
        
        with col2:
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.session_state.notes_validated = False
                st.rerun()
        
        # Save Entry Button
        if st.session_state.notes_validated and total_hours > 0:
            st.success("✅ Notes validated! Ready to save entry.")
            
            if st.button("💾 Save Entry", type="primary"):
                # Compile all notes from chat history
                compiled_notes = "\n".join([
                    msg['content'] for msg in st.session_state.chat_history 
                    if msg['role'] == 'user'
                ])
                
                # Create entry
                new_entry = {
                    'id': len(st.session_state.work_entries) + 1,
                    'date': entry_date.strftime("%Y-%m-%d"),
                    'start_time': start_time.strftime("%H:%M"),
                    'end_time': end_time.strftime("%H:%M"),
                    'total_hours': total_hours,
                    'work_status': selected_status,
                    'notes': compiled_notes,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Submit to API
                summary = f"Work performed on {st.session_state.selected_work_order.get('work_order_id', '')}: {compiled_notes[:100]}..."
                
                submission_result = api_client.submit_work_status(
                    tech_name=st.session_state.current_tech,
                    work_date=entry_date.strftime("%Y-%m-%d"),
                    work_status=selected_status,
                    time_spent=total_hours,
                    notes=compiled_notes,
                    summary=summary,
                    work_order_id=st.session_state.selected_work_order.get('work_order_id')
                )
                
                if submission_result:
                    new_entry['log_id'] = submission_result.get('log_id')
                    st.session_state.work_entries.append(new_entry)
                    
                    # Clear form
                    st.session_state.chat_history = []
                    st.session_state.notes_validated = False
                    
                    st.success(f"✅ Entry saved! Log ID: {submission_result.get('log_id', 'N/A')}")
                    st.rerun()
                else:
                    st.error("❌ Failed to save entry")
        elif not st.session_state.notes_validated:
            st.info("💬 Please complete the notes validation process above")
        elif total_hours <= 0:
            st.warning("⏰ Please set valid start and end times")
    
    # ========================================
    # TAB 2: HISTORY
    # ========================================
    with tab2:
        st.header("Work Entry History")
        
        if st.session_state.work_entries:
            # Display entries in a table
            df = pd.DataFrame(st.session_state.work_entries)
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Entries", len(df))
            with col2:
                st.metric("Total Hours", f"{df['total_hours'].sum():.2f}")
            with col3:
                most_common_status = df['work_status'].mode().iloc[0] if not df.empty else "N/A"
                st.metric("Most Common Status", most_common_status)
            
            st.subheader("📊 Entry Details")
            
            # Display each entry
            for i, entry in enumerate(reversed(st.session_state.work_entries)):
                with st.expander(f"Entry #{entry['id']} - {entry['date']} ({entry['total_hours']:.2f}h)", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Date:** {entry['date']}")
                        st.write(f"**Time:** {entry['start_time']} - {entry['end_time']}")
                        st.write(f"**Hours:** {entry['total_hours']:.2f}")
                        st.write(f"**Status:** {entry['work_status']}")
                        if entry.get('log_id'):
                            st.write(f"**Log ID:** {entry['log_id']}")
                    
                    with col2:
                        st.markdown("**Notes:**")
                        st.text_area(
                            "Notes",
                            value=entry['notes'],
                            height=100,
                            disabled=True,
                            key=f"history_notes_{entry['id']}"
                        )
        else:
            st.info("No work entries recorded yet. Use the 'New Entry' tab to add entries.")
    
    # ========================================
    # TAB 3: COMPLETE WORK ORDER
    # ========================================
    with tab3:
        st.header("Complete Work Order")
        
        if not st.session_state.work_entries:
            st.warning("⚠️ No work entries found. Please add some entries first.")
        else:
            # Summary of work entries
            st.subheader("📊 Work Summary")
            
            total_hours = sum(entry['total_hours'] for entry in st.session_state.work_entries)
            total_entries = len(st.session_state.work_entries)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Entries", total_entries)
            with col2:
                st.metric("Total Hours", f"{total_hours:.2f}")
            with col3:
                st.metric("Work Order", st.session_state.selected_work_order.get('work_order_id', 'N/A'))
            
            # Generate work logs table for CAR format
            work_logs_table = []
            for entry in st.session_state.work_entries:
                work_logs_table.append(f"{entry['work_status']} | {entry['notes']}")
            
            wo_status_and_notes_table = "\n".join(work_logs_table)
            
            # Completion notes input
            st.subheader("📝 Completion Notes")
            completion_notes = st.text_area(
                "Enter final completion notes:",
                height=200,
                placeholder="Summarize the overall work completed, final results, and any recommendations...",
                key="completion_notes"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Generate CAR Format", type="primary"):
                    if completion_notes.strip():
                        with st.spinner("🤖 Generating CAR format..."):
                            car_result = api_client.convert_to_car(
                                completion_notes=completion_notes,
                                work_order_description=st.session_state.selected_work_order.get('description', ''),
                                wo_status_and_notes_table=wo_status_and_notes_table
                            )
                            
                            if car_result:
                                st.session_state.car_formatted_notes = car_result.get('car_formatted_notes', '')
                                st.success("✅ CAR format generated!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to generate CAR format")
                    else:
                        st.error("Please enter completion notes first")
            
            with col2:
                if st.button("📋 Generate Client Summary"):
        if completion_notes.strip():
            with st.spinner("📋 Generating client summary..."):
                            # Create conversation table
                conversation_table = f"Tech | {completion_notes}\nAI | Work completed successfully on {st.session_state.selected_work_order.get('work_order_id', '')}."
                
                client_summary_result = api_client.convert_to_client_summary(conversation_table)
                
                if client_summary_result:
                    st.session_state.client_summary = client_summary_result.get('client_summary', '')
                    st.success("✅ Client summary generated!")
                    st.rerun()
                else:
                    st.error("❌ Failed to generate client summary")
        else:
                        st.error("Please enter completion notes first")
            
            # Display CAR format if generated
            if 'car_formatted_notes' in st.session_state:
                st.subheader("📋 CAR Format (Cause-Action-Result)")
                
                car_notes = st.text_area(
                    "Review and edit CAR format notes:",
                    value=st.session_state.car_formatted_notes,
                    height=300,
                    key="car_notes_editable"
                )
                
                # Final submission
                if st.button("✅ Complete Work Order", type="primary"):
                    st.success("🎉 Work order completed successfully!")
                    st.balloons()
                    
                    # Here you would typically update the work order status via API
                    st.info("Work order has been marked as completed in the system.")
            
            # Display client summary if generated
            if 'client_summary' in st.session_state:
                st.subheader("🎯 Client Summary")
                st.text_area(
                    "Client-friendly summary:",
                    value=st.session_state.client_summary,
                    height=150,
                    disabled=True,
                    key="client_summary_display"
                )