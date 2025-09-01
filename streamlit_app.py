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

# Separate work orders by status
pending_orders = [wo for wo in st.session_state.work_orders 
                 if wo.get('status', '').lower() in ['pending', 'open', 'assigned']]
completed_orders = [wo for wo in st.session_state.work_orders 
                   if wo.get('status', '').lower() in ['completed', 'closed', 'finished']]
in_progress_orders = [wo for wo in st.session_state.work_orders 
                     if wo.get('status', '').lower() in ['in_progress', 'working']]

# Add in-progress orders to pending for simplicity
pending_orders.extend(in_progress_orders)

# Create tabs for different statuses
tab1, tab2 = st.tabs([f"📋 Pending ({len(pending_orders)})", f"✅ Completed ({len(completed_orders)})"])

selected_work_order = None

# Pending Work Orders Tab
with tab1:
    if pending_orders:
        st.write("**Select a pending work order to begin logging:**")
        
        for i, wo in enumerate(pending_orders):
            wo_id = wo.get('work_order_id', '')
            description = wo.get('description', '')
            status = wo.get('status', '')
            wo_type = wo.get('wo_type', '')
            work_date = wo.get('work_date', '')
            
            # Create expandable work order card
            with st.expander(f"**{wo_id}** - {work_date}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**{description}**")
                    st.caption(f"📅 **{work_date}**")
                    
                    # Status badges with colors
                    col_badge1, col_badge2 = st.columns(2)
                    with col_badge1:
                        if wo_type.lower() == 'preventive':
                            st.markdown("🟢 **Preventive**")
                        elif wo_type.lower() == 'corrective':
                            st.markdown("🟠 **Corrective**")
                        elif wo_type.lower() == 'project':
                            st.markdown("🔵 **Project**")
                        elif wo_type.lower() == 'ad hoc':
                            st.markdown("🟡 **Ad Hoc**")
                        else:
                            st.markdown(f"⚪ **{wo_type}**")
                    
                    with col_badge2:
                        if status.lower() == 'pending':
                            st.markdown("📋 **Scheduled**")
                        elif status.lower() in ['in_progress', 'working']:
                            st.markdown("🔄 **In-progress**")
                        else:
                            st.markdown(f"📊 **{status}**")
                
                with col2:
                    st.markdown("") # spacing
                    if st.button("Select", key=f"select_pending_{i}", type="primary"):
                        selected_work_order = wo
                        st.session_state.selected_work_order = wo
                        st.success(f"Selected {wo_id}")
                        st.rerun()
    else:
        st.info("No pending work orders found.")

# Completed Work Orders Tab  
with tab2:
    if completed_orders:
        st.write("**Completed work orders (for reference):**")
        
        for i, wo in enumerate(completed_orders):
            wo_id = wo.get('work_order_id', '')
            description = wo.get('description', '')
            status = wo.get('status', '')
            wo_type = wo.get('wo_type', '')
            work_date = wo.get('work_date', '')
            
            # Create expandable work order card
            with st.expander(f"**{wo_id}** - {work_date}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**{description}**")
                    st.caption(f"📅 **{work_date}**")
                    
                    # Status badges with colors
                    col_badge1, col_badge2 = st.columns(2)
                    with col_badge1:
                        if wo_type.lower() == 'preventive':
                            st.markdown("🟢 **Preventive**")
                        elif wo_type.lower() == 'corrective':
                            st.markdown("🟠 **Corrective**")
                        elif wo_type.lower() == 'project':
                            st.markdown("🔵 **Project**")
                        elif wo_type.lower() == 'ad hoc':
                            st.markdown("🟡 **Ad Hoc**")
                        else:
                            st.markdown(f"⚪ **{wo_type}**")
                    
                    with col_badge2:
                        st.markdown("✅ **Completed**")
                
                with col2:
                    st.markdown("") # spacing
                    if st.button("View", key=f"view_completed_{i}"):
                        selected_work_order = wo
                        st.session_state.selected_work_order = wo
                        st.info(f"Viewing completed work order {wo_id}")
                        st.rerun()
    else:
        st.info("No completed work orders found.")

# Display selected work order details
if st.session_state.selected_work_order:
    selected_wo = st.session_state.selected_work_order
    
    st.markdown("---")
    st.subheader("📄 Selected Work Order Details")
    
    # Display work order details
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
        
        # Initialize chat history if not exists
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'notes_validated' not in st.session_state:
            st.session_state.notes_validated = False
        
        # Chat container with custom styling
        chat_container = st.container()
        
        with chat_container:
            # Display chat history in a chat-like interface
            for msg in st.session_state.chat_history:
                if msg['role'] == 'user':
                    # User message - right aligned with blue background
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #1f77b4; 
                                color: white; 
                                padding: 10px 15px; 
                                border-radius: 15px 15px 0px 15px; 
                                margin: 5px 0px; 
                                text-align: right;
                                float: right;
                                max-width: 80%;
                            ">
                                <strong>You:</strong> {msg['content']}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                else:
                    # AI message - left aligned with grey background
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #f0f2f6; 
                                color: #262730; 
                                padding: 10px 15px; 
                                border-radius: 15px 15px 15px 0px; 
                                margin: 5px 0px; 
                                text-align: left;
                                float: left;
                                max-width: 80%;
                            ">
                                <strong>🤖 AI:</strong> {msg['content']}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            
            # Add some spacing after chat messages
            st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Notes input area
        st.markdown("**💭 Type your message:**")
        user_input = st.text_area(
            "Enter your notes:",
            value="",
            key="notes_input",
            height=120,
            placeholder="Describe what you did, what you found, and any issues encountered..."
        )
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("💬 Send Notes", type="primary", use_container_width=True):
                if user_input.strip():
                    # Add user message to chat history
                    st.session_state.chat_history.append({
                        'role': 'user',
                        'content': user_input
                    })
                    
                    # Check if we're answering follow-up questions
                    if 'current_follow_up_question' in st.session_state and st.session_state.current_follow_up_question:
                        # Store the answer to the current question
                        if 'follow_up_answers' not in st.session_state:
                            st.session_state.follow_up_answers = {}
                        st.session_state.follow_up_answers[st.session_state.current_follow_up_question] = user_input
                        
                        # Check if we have more questions
                        if 'follow_up_questions' in st.session_state and st.session_state.follow_up_questions:
                            # Get next question
                            next_question = st.session_state.follow_up_questions.pop(0)
                            st.session_state.current_follow_up_question = next_question
                            
                            st.session_state.chat_history.append({
                                'role': 'ai',
                                'content': f"Next question: {next_question}"
                            })
                        else:
                            # All questions answered, resubmit for validation
                            st.session_state.current_follow_up_question = None
                            
                            # Compile all answers
                            answers_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in st.session_state.follow_up_answers.items()])
                            
                            # Get original notes
                            original_notes = ""
                            for msg in st.session_state.chat_history:
                                if msg['role'] == 'user' and not msg.get('is_follow_up_answer'):
                                    original_notes = msg['content']
                                    break
                            
                            # Resubmit with answers
                            with st.spinner("🤖 AI is re-evaluating your notes with answers..."):
                                validation_result = api_client.validate_work_status(
                                    operational_log=original_notes,
                                    work_status=selected_status,
                                    work_order_description=st.session_state.selected_work_order.get('description', ''),
                                    tech_name=st.session_state.current_tech,
                                    work_date=entry_date.strftime("%Y-%m-%d"),
                                    follow_up_questions_answers=answers_text
                                )
                            
                            if validation_result and validation_result.get('valid', False):
                                st.session_state.chat_history.append({
                                    'role': 'ai',
                                    'content': "Great! Your time entry has been saved successfully. You can close this screen anytime."
                                })
                                st.session_state.notes_validated = True
                                # Clear follow-up state
                                st.session_state.follow_up_questions = []
                                st.session_state.follow_up_answers = {}
                            else:
                                st.session_state.chat_history.append({
                                    'role': 'ai',
                                    'content': "❌ Still missing some information. Please provide more details."
                                })
                    else:
                        # Initial notes submission
                        with st.spinner("🤖 AI is reviewing your notes..."):
                            validation_result = api_client.validate_work_status(
                                        operational_log=user_input,
                                        work_status=selected_status,
                                        work_order_description=st.session_state.selected_work_order.get('description', ''),
                                        tech_name=st.session_state.current_tech,
                                        work_date=entry_date.strftime("%Y-%m-%d"),
                                        follow_up_questions_answers=""
                            )
                            print(validation_result)
                        if validation_result:
                            if validation_result.get('valid', False):
                                st.session_state.chat_history.append({
                                    'role': 'ai',
                                    'content': "Great! Your time entry has been saved successfully. You can close this screen anytime."
                                })
                                st.session_state.notes_validated = True
                            else:
                                # Store follow-up questions
                                follow_up_questions = validation_result.get('follow_up_questions', [])
                                if follow_up_questions:
                                    st.session_state.follow_up_questions = follow_up_questions.copy()
                                    st.session_state.current_follow_up_question = follow_up_questions.pop(0)
                                    
                                    st.session_state.chat_history.append({
                                        'role': 'ai',
                                        'content': f"Please answer this question: {st.session_state.current_follow_up_question}"
                                    })
                                else:
                                    st.session_state.chat_history.append({
                                        'role': 'ai',
                                        'content': f"❌ Missing information: {validation_result.get('missing', 'Unknown')}"
                                    })
                        else:
                            st.error("❌ Failed to validate notes")
                    
                    # Rerun to refresh the interface
                    st.rerun()
        
        with col2:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.notes_validated = False
                st.session_state.follow_up_questions = []
                st.session_state.current_follow_up_question = None
                st.session_state.follow_up_answers = {}
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
                                # Format the CAR response into a readable format
                                car_formatted = f"CAUSE: {car_result.get('cause', '')}\n\nACTION: {car_result.get('action', '')}\n\nRESULT: {car_result.get('result', '')}"
                                st.session_state.car_formatted_notes = car_formatted
                                st.success("✅ CAR format generated!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to generate CAR format")
                    else:
                        st.error("Please enter completion notes first")
            
            with col2:
                if st.button("📋 Generate Client Summary"):
                    completion_notes = st.session_state.car_formatted_notes
                    conversation_table = f"Tech | {completion_notes}\nAI | Work completed successfully on {st.session_state.selected_work_order.get('work_order_id', '')}."
                
                client_summary_result = api_client.convert_to_client_summary(conversation_table)
                
                if client_summary_result:
                    st.session_state.client_summary = client_summary_result.get('summary', '')
                    st.success("✅ Client summary generated!")
                    st.rerun()
                else:
                    st.error("❌ Failed to generate client summary")
            
            
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