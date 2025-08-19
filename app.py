"""
Solar Work Order Field Services App 
Streamlit UI Application
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# Import modular components
from data_manager import (
    load_data, get_technician_options, get_work_order_options,
    get_work_order_details, get_suggested_labor_hours, 
    get_technician_month_year_options, get_work_order_completion_notes,
    get_work_date_options, get_time_type
)
from ai_classifier import (
    init_openai, classify_work_type, is_openai_available, 
    transcribe_audio, convert_to_car_format
)

# Page configuration
st.set_page_config(page_title="Solar Work Order App", layout="wide")

# Initialize OpenAI client
openai_client = init_openai()

# Load data
cutlass_df, completion_notes_df, _ = load_data()

if cutlass_df is None:
    st.error("Could not load data. Please check if Cutlass_time_entry.xlsx exists.")
    st.stop()

# Main app header
st.title("🌞 Cutlass Field Services Time Entry App")
st.markdown("---")

# ========================================
# 1. WORK ORDER ASSIGNMENT UI
# ========================================

st.header("📋 1. Work Order Assignment")

# Create four columns for the assignment UI
col1, col1_5, col2, col3 = st.columns([1, 1, 1, 1])

with col1:
    st.subheader("👷 Select Technician")
    # Get technician options
    tech_options, tech_mapping = get_technician_options(cutlass_df)
    
    selected_tech_display = st.selectbox(
        "Technician",
        tech_options,
        key="tech_selector"
    )

with col1_5:
    st.subheader("📅 Select Month/Year")
    
    if selected_tech_display == "-- Select Technician --":
        st.selectbox("Month/Year", ["-- Select Technician First --"], disabled=True)
        selected_month_year = None
    else:
        selected_tech = tech_mapping[selected_tech_display]
        # Get month/year options for the selected technician
        month_year_options, month_year_mapping = get_technician_month_year_options(cutlass_df, selected_tech)
        
        selected_month_year_display = st.selectbox(
            "Month/Year",
            month_year_options,
            key="month_year_selector"
        )
        
        selected_month_year = month_year_mapping[selected_month_year_display]

with col2:
    st.subheader("📋 Select Work Order")
    
    if selected_tech_display == "-- Select Technician --":
        st.selectbox("Work Order", ["-- Select Technician First --"], disabled=True)
        selected_work_order = None
    else:
        # Use the already assigned selected_tech from the month/year section
        wo_options, wo_mapping = get_work_order_options(selected_tech, cutlass_df, selected_month_year)
        
        selected_wo_display = st.selectbox(
            "Work Order",
            wo_options,
            key="wo_selector"
        )
        
        selected_work_order = wo_mapping.get(selected_wo_display)
with col3:
    st.subheader("📅 Select Work Date")
    
    if selected_tech_display == "-- Select Technician --" or not selected_work_order:
        st.selectbox("Work Date", ["-- Select Work Order First --"], disabled=True)
        selected_work_date = None
    else:
        # Get work date options for the selected technician, month, and work order
        date_options, date_mapping = get_work_date_options(selected_tech, cutlass_df, selected_month_year, selected_work_order)
        
        selected_date_display = st.selectbox(
            "Work Date",
            date_options,
            key="date_selector"
        )
        
        selected_work_date = date_mapping.get(selected_date_display)        

st.subheader("ℹ️ Auto-Fetched Information")
    
if selected_work_date:
        # Get work order and asset details
        wo_details, asset_details = get_work_order_details(selected_work_order, cutlass_df, selected_tech, selected_month_year,selected_work_date)
        
        if wo_details is not None and asset_details is not None:
            # Display auto-fetched info in a clean format
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                st.metric("🏢 Site", wo_details.get("Site ", "N/A"))
                st.metric("🔧 Asset Type", asset_details["AssetType"])
                st.metric("🆔 Asset Description", wo_details.get("Asset Description", "N/A"))
            
            with info_col2:
                st.metric("🏭 Plant", asset_details["Plant"])
                st.metric("📋 WO Type", wo_details.get("WO Type", "N/A"))
                st.metric("📅 Work Date", str(wo_details.get("Work Date", "N/A")))
            
            # Show work order description
            if wo_details.get("Description"):
                st.markdown("**📝 Work Order Description:**")
                st.info(wo_details.get("Description", "N/A"))
        else:
            st.error(f"Asset details not found for work order: {selected_work_order}")
else:
    st.info("👆 Select a technician, Month-Year, work order and work date to view details")

st.markdown("---")

# ========================================
# 2. WORK EXECUTION ENTRY
# ========================================

if selected_work_date:
    st.header("⚡ 2. Work Execution Entry")
    
    st.subheader("⏰ Labor Hours Entry")
    # Get suggested labor hours based on similar work
    if wo_details is not None:
            wo_type = wo_details.get("WO Type", "")
            description = wo_details.get("Description", "")
            suggested_hours = get_suggested_labor_hours(cutlass_df, wo_type, description)
            
            st.info(f"💡 **Suggested Hours:** {suggested_hours} hours (based on similar {wo_type} work)")
    else:
        suggested_hours = "N/A"
        
        # Total Labor Hours input
    total_hours = st.number_input(
            "⏱️ Total Labor Hours",
            min_value=0.1,
            max_value=24.0,
            value=suggested_hours,
            step=0.1,
            help="Enter the total number of hours worked on this task",
            key=f"total_hours_{selected_work_order}"
        )
        
    st.success(f"⏱️ **Total Labor Hours:** {total_hours} hours")
    

    st.subheader("📝 Completion Details")
        
        # Show actual completion notes for this work order
    if selected_work_order:
            display_notes = get_work_order_completion_notes(cutlass_df, selected_work_order, selected_tech, selected_month_year, selected_work_date)
            
            if display_notes and "No completion notes" not in display_notes:
                # Clean the completion note (replace Excel line breaks)
                cleaned_note = str(display_notes).replace("_x000D_", "").strip()
                time_type = get_time_type(cutlass_df, selected_work_order, selected_tech, selected_month_year, selected_work_date)
                st.markdown(f"**💡 Existing completion notes for this work order in {wo_type}**")
                st.markdown(f"**💡 User selected time type:** {time_type}")
                st.text(cleaned_note)
                
                if st.button("📋 Use Existing Notes", key=f"use_existing_{selected_work_order}"):
                    st.session_state[f"completion_notes_{selected_work_order}"] = cleaned_note
                    st.rerun()
        
        # Single completion notes text area
    st.write("**Enter completion notes:**")
        
        # Voice input and text area
    audio_value = st.audio_input(
            "🎤 Record voice message",
            key=f"audio_input_{selected_work_order}",
            help="Click to record audio for completion notes"
        )
        
        # Auto-transcribe when audio is recorded
    if audio_value is not None and is_openai_available():
            audio_key = f"transcribed_audio_{selected_work_order}"
            current_audio_id = f"audio_{hash(audio_value.getvalue())}"
            
            if (audio_key not in st.session_state or 
                st.session_state.get(f"audio_id_{selected_work_order}") != current_audio_id):
                
                with st.spinner("🎤 Transcribing..."):
                    transcribed_text = transcribe_audio(audio_value, openai_client)
                    st.session_state[f"completion_notes_{selected_work_order}"] = transcribed_text
                    st.session_state[audio_key] = transcribed_text
                    st.session_state[f"audio_id_{selected_work_order}"] = current_audio_id
                    st.success("🎤 Audio transcribed!")
            else:
                st.success("🎤 Audio already transcribed!")
        
        # Completion notes input
    completion_notes = st.text_area(
            "📝 Completion Notes",
            height=200,
            placeholder="CAUSE: Describe what caused the need for this work...\n\nACTION: Describe the actions taken...\n\nRESULT: Describe the outcome...",
            key=f"completion_notes_{selected_work_order}",
            help="Enter completion notes or use voice input above"
        )
        
        # Submit completion notes and convert to CAR format
    if st.button("✅ Submit Completion Notes", type="primary", key=f"submit_completion_{selected_work_order}"):
            if completion_notes.strip():
                if is_openai_available():
                    with st.spinner("Processing completion notes and converting to CAR format..."):
                        # Get work order description for context
                        work_order_description = wo_details.get("Description", "") if wo_details is not None else ""
                        
                        # Get WO Type and Time Type for specific requirements
                        wo_type = wo_details.get("WO Type", "") if wo_details is not None else ""
                        time_type = wo_details.get("Time Type", "") if wo_details is not None else ""
                        
                        # Convert to CAR format
                        car_formatted = convert_to_car_format(
                            completion_notes, 
                            work_order_description, 
                            openai_client,
                            wo_type,
                            time_type
                        )
                        
                        # Store in session state for display
                        st.session_state[f"car_format_{selected_work_order}"] = car_formatted
                        
                        st.success("✅ Completion notes submitted and processed!")
                        st.rerun()
                else:
                    st.error("OpenAI API not available for CAR format conversion")
            else:
                st.error("⚠️ Please enter completion notes before submitting.")
        
        # Display CAR format if available
    if f"car_format_{selected_work_order}" in st.session_state:
            st.markdown("---")
            st.subheader("📋 CAR Format (Cause-Action-Result)")
            car_content = st.session_state[f"car_format_{selected_work_order}"]
            st.text_area(
                "CAR Formatted Completion Notes:",
                value=car_content,
                height=300,
                disabled=True,
                key=f"car_display_{selected_work_order}"
            )
            
            # Summary information  
            uploaded_files = st.session_state.get(f"images_{selected_work_order}", [])
            st.info(f"""
            **📋 Work Order:** {selected_work_order}
            **👷 Technician:** {selected_tech_display}
            **⏱️ Total Hours:** {total_hours} hours
            **📝 Status:** Completion notes submitted and processed in CAR format
            **📸 Images:** {len(uploaded_files) if uploaded_files else 0} files
            """)
        
        # Optional image upload
    uploaded_files = st.file_uploader(
            "📸 Upload Images (Optional)",
            accept_multiple_files=True,
            type=['png', 'jpg', 'jpeg'],
            key=f"images_{selected_work_order}"
        )
        
    if uploaded_files:
            st.success(f"📸 {len(uploaded_files)} image(s) uploaded")






