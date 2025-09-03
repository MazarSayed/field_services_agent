"""
AI Classifier Module
Handles OpenAI integration and work type classification
"""

import os
import openai
import streamlit as st
from dotenv import load_dotenv
from typing import Optional, Union
import io
import tempfile
import json
import instructor
from src.utils import get_prompt
from models.models import (
    WorkStatusValidationResponse, 
    TranscriptionResponse, 
    CARFormatResponse, 
    ClientSummaryResponse,
    HoldReasonValidationResponse
)

load_dotenv()

# Patch the OpenAI client to enable Pydantic response models
def get_patched_client():
    """Get OpenAI client patched with instructor for Pydantic response models"""
    client = openai.OpenAI()
    return instructor.patch(client)
 
def transcribe_audio(openai_client, audio_file) -> TranscriptionResponse:
    """
    Transcribe audio file using OpenAI Whisper (Speech-to-Text)
    
    Note: Uses Whisper-1 model for audio transcription (STT)
    This is different from TTS (Text-to-Speech) - we need STT to convert voice to text
    
    Args:
        openai_client: OpenAI client instance
        audio_file: Audio file from st.audio_input (UploadedFile object)
        
    Returns:
        TranscriptionResponse object with transcript and status
    """
    
    try:
        # Reset file pointer to beginning
        audio_file.seek(0)
        
        # Create a temporary file to save the audio (required by OpenAI API)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Transcribe using OpenAI Whisper
        with open(tmp_file_path, "rb") as audio:
            transcript = openai_client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=audio,
                response_format="text"
            )
        
        # Clean up temporary file
        os.unlink(tmp_file_path)
        
        return TranscriptionResponse(
            transcript=transcript,
            success=True
        )
        
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return TranscriptionResponse(
            transcript="",
            success=False,
            error_message=str(e)
        )

def validate_work_status_log(operational_log: str, work_status: Union[str, dict], work_order_description: str, plant: str, wo_status_and_notes_with_hours_table: str, follow_up_questions_answers_table: str) -> WorkStatusValidationResponse:
    """
    Validate operational log against work status requirements and generate follow-up questions if needed
    
    Args:
        openai_client: OpenAI client instance
        operational_log: The operational log to validate
        work_status: The work status types and along with their percentage of occurance
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_hours_table: Table of work status and notes with hours
        follow_up_questions_answers_table: Previous follow-up questions and answers
        
    Returns:
        WorkStatusValidationResponse object with validation result and follow-up questions
    """

    try:
        if isinstance(work_status, str):
            work_status = {work_status: 100}  

        status_requirements = ""
        for work_status_type, percentage in work_status.items():
            status_requirements += get_prompt(f"work_status.{work_status_type}") + f"Percentage of allocated time for the work status: {percentage}"
            
        # Get validation instructions and system prompt
        validation_instructions = get_prompt("validation_instructions")
        work_status_system_prompt = get_prompt("system_prompts.work_status_system_prompt")
        
        prompt = f"""
        You are validating an operational log for work status: {work_status}.
        The work order description is: "{work_order_description}".
        The plant is: "{plant}".
        User's Previous work status and notes with hours for extra context: 
        {wo_status_and_notes_with_hours_table}


        Mainly rely on the current USER'S OPERATIONAL LOG:
        "{operational_log}"

        Previous Follow-up Question and Answers:
        {follow_up_questions_answers_table}

        REQUIREMENTS (guidelines, not strict rules):
        {status_requirements}
        
        {validation_instructions}
        """
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        
        response = patched_client.chat.completions.create(
            model="gpt-4o",
            response_model=WorkStatusValidationResponse,
            messages=[
                {"role": "system", "content": work_status_system_prompt}, 
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.1
        )
        
        # Return the validated Pydantic model directly
        return response
            
    except Exception as e:
        st.error(f"Error validating work status log: {e}")
        return WorkStatusValidationResponse(
            valid=False, 
            missing=f"Error: {str(e)}", 
            follow_up_question="Follow-up question could not be generated."
        )


def validate_reason_for_hold(hold_reason: str, work_order_type: str, work_order_description: str, plant: str, wo_status_and_notes_with_hours_table: str, follow_up_questions_answers_table: str) -> HoldReasonValidationResponse:
    """
    Validate hold reason against work order requirements and generate follow-up questions if needed
    
    Args:
        hold_reason: The hold reason to validate
        work_order_type: Work order type
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_hours_table: Table of work status and notes with hours
        follow_up_questions_answers_table: Previous follow-up questions and answers
        
    Returns:
        HoldReasonValidationResponse object with validation result and follow-up questions
    """

    try:

        # Get validation instructions and system prompt
        hold_reason_validation_instructions = get_prompt("hold_reason_validation_instructions")
        hold_reason_system_prompt = get_prompt("system_prompts.hold_reason_system_prompt")
        
        prompt = f"""
        Work Order Type: "{work_order_type}".
        The work order description is: "{work_order_description}".
        The plant is: "{plant}".

        User's Previous work status and notes with hours for extra context: 
        {wo_status_and_notes_with_hours_table}

        Mainly rely on the hold reason from User's HOLD REASON: "{hold_reason}".
        The previous follow-up questions and answers are: "{follow_up_questions_answers_table}".

        Validation Guidelines:
        {hold_reason_validation_instructions}
        """
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        
        response = patched_client.chat.completions.create(
            model="gpt-4o",
            response_model=HoldReasonValidationResponse,
            messages=[
                {"role": "system", "content": hold_reason_system_prompt}, 
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.1
        )
        
        # Return the validated Pydantic model directly
        return response
            
    except Exception as e:
        st.error(f"Error validating work status log: {e}")
        return HoldReasonValidationResponse(
            valid=False,
            missing=f"Error: {str(e)}",
            follow_up_question="Follow-up question could not be generated.",
            hold_reason_analysis="Analysis could not be generated due to error.",
            recommended_actions="Please review the hold reason manually."
        )


def convert_to_car_format(work_order_type: str, final_completion_notes: str, wo_status_and_notes_with_hours_table: str, work_order_description: str) -> CARFormatResponse:
    """
    Convert completion notes to CAR (Cause, Action, Result) format using gpt-4o-mini
    
    Args:
        work_order_type: Work order type
        final_completion_notes: Original completion notes from field tech
        wo_status_and_notes_with_hours_table: Table of work status and notes for each task with hours
        work_order_description: Work order description for context
        
    Returns:
        CARFormatResponse object with structured CAR format data
    """

    try:
        # Get CAR format conversion prompt and system prompt
        car_prompt = get_prompt("car_format_conversion")
        car_system_prompt = get_prompt("system_prompts.car_system_prompt")
        
        prompt = f"""
       
        Work Order Type: {work_order_type}
        Work Order Description: {work_order_description}

        Work Status | Work Status Notes with hours
        {wo_status_and_notes_with_hours_table}

        {car_prompt}

        Final Completion Notes from Field Tech:
        {final_completion_notes}
        """
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        
        response = patched_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=CARFormatResponse,
            messages=[
                {"role": "system", "content": car_system_prompt}, 
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.3
        )
        response_obj = CARFormatResponse(
            cause=response.cause or "",
            action=response.action or "",
            result=response.result or "",
            success=True,  
            error_message=None
        )

        return response_obj

                
    except Exception as e:
        st.error(f"Error converting to CAR format: {e}")
        return CARFormatResponse(
            cause="",
            action="",
            result="",
            success=False,
            error_message=str(e)
        )


def convert_to_client_summary(conversation_table: str) -> ClientSummaryResponse:
    """
    Convert AI and human messages into a client-friendly summary and notes
    
    Args:
        conversation_table: Conversation between Tech and AI
        
    Returns:
        ClientSummaryResponse object with summary and notes
    """

    try:
        # Get client summary conversion prompt and system prompt
        user_prompt = get_prompt("client_summary_conversion")
        client_summary_system_prompt = get_prompt("system_prompts.client_summary_system_prompt")
        
        prompt = f"""
        
        {user_prompt}

        Conversation between Tech and AI:
        Person | chat message
        {conversation_table}

        """
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        
        response = patched_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=ClientSummaryResponse,
            messages=[
                {"role": "system", "content": client_summary_system_prompt}, 
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.3
        )
        
        # Return the validated Pydantic model directly
        return response
        
    except Exception as e:
        st.error(f"Error converting to client summary: {e}")
        return ClientSummaryResponse(
            summary="Unable to process request",
            notes="There was an error processing your request. Please try again or contact support.",
            success=False,
            error_message=str(e)
        )


