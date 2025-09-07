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

def format_conversation_history(messages: list[dict]) -> str:
    """Convert conversation messages list to string format for prompt."""
    if not messages:
        return ""
    
    formatted_lines = []
    for message in messages:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        formatted_lines.append(f"{role} | {content}")
    
    return "\n".join(formatted_lines)

def validate_work_status_log(operational_log: str, work_order_type: str, work_status: Union[str, dict], work_order_description: str, plant: str, wo_status_and_notes_with_time_allocation_table: str, follow_up_questions_answers_table: list[dict]) -> WorkStatusValidationResponse:
    """
    Validate operational log against work status requirements and generate follow-up questions if needed
    
    Args:
        openai_client: OpenAI client instance
        operational_log: The operational log to validate
        work_order_type: The work order type
        work_status: The work status types and along with their percentage of occurance
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_time_allocation_table: Table of work status and notes with time allocation
        follow_up_questions_answers_table: Previous follow-up questions and answers
        
    Returns:
        WorkStatusValidationResponse object with validation result and follow-up questions
    """

    try:
        if isinstance(work_status, str):
            work_status = {work_status: 100}  

        status_requirements = ""
        work_contribtion = ""
        for work_status_type, values in work_status.items():
            pct = values["percentage"] if isinstance(values, dict) else values
            if pct > 10:
                work_contribtion += f"{work_status_type} - {pct}%\n"
                status_requirements += (
                get_prompt(f"work_status.{work_status_type}")
                + f" Percentage of allocated time for the work type: {pct}%\n"
                )
            
        # Get validation instructions and system prompt
        work_status_system_prompt = get_prompt("system_prompts.work_status_system_prompt")
        validation_guidelines=get_prompt("validation_instructions")
        work_order_type_guidelines=get_prompt(f"work_order_type_guidelines.{work_order_type}")
        
        prompt = f"""
        You are validating an operational log for Work Contribution: {work_contribtion}.
        The work order description is: "{work_order_description}".
        The plant is: "{plant}".

        Previous work logs and their respective time allocation, just for extra context,
        PREVIOUS WORK LOGS:
        {wo_status_and_notes_with_time_allocation_table}

        WORK ORDER TYPE GUIDELINES:
        {work_order_type_guidelines}
        Follow the work order type guidelines above to get better notes for the work order type.
        
        
         WORK CONTRIBUTION BASED GUIDELINES:
        {status_requirements}
        Prioritize the work that has higher percentage of allocated time and make the notes meet all the requirements for the works types above.
        Follow the  WORK CONTRIBUTION BASED GUIDELINES above to get better notes for the work order type.

        Orignal Log Notes from Tech:
        {operational_log}

        Follow-up questions and answers from you (AI) to get more information:
        Person | Follow-up questions from you (AI)and answers from tech
        {format_conversation_history(follow_up_questions_answers_table)}

        Make sure to consider both Orignal Log Notes from Tech and Follow-up questions and answers from you (AI) to get more information on the work done.
        Validate the work done based on the  WORK CONTRIBUTION BASED GUIDELINES and WORK ORDER TYPE GUIDELINES for each work type.
        Follow up with the tech if you need more information to validate the work done only if you need to.
        Avoid repeating the same follow up questions, if the question already listed in the Follow-up questions and answers from you (AI) section.
        IMPORTANT: Make sure we meet the  WORK CONTRIBUTION BASED GUIDELINES and WORK ORDER TYPE GUIDELINES for each work type.
        """
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        print("prompt: ", prompt)
        print("work status system prompt: ", work_status_system_prompt)

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


def validate_reason_for_hold(hold_reason: str, work_order_type: str, work_order_description: str, plant: str, wo_status_and_notes_with_time_allocation_table: str, follow_up_questions_answers_table: str) -> HoldReasonValidationResponse:
    """
    Validate hold reason against work order requirements and generate follow-up questions if needed
    
    Args:
        hold_reason: The hold reason to validate
        work_order_type: Work order type
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_time_allocation_table: Table of work status and notes with hours
        follow_up_questions_answers_table: Previous follow-up questions and answers
        
    Returns:
        HoldReasonValidationResponse object with validation result and follow-up questions
    """

    try:
        # Get hold reason type requirements
        print("hold_reason: ", hold_reason)
        hold_reason_requirements = ""
        hold_reason_requirements += get_prompt(f"hold_reason_types.{hold_reason}") + "\n"
        

        # Get validation instructions and system prompt
        hold_reason_validation_instructions = get_prompt("hold_reason_validation_instructions")
        hold_reason_system_prompt = get_prompt("system_prompts.hold_reason_system_prompt")
        
        prompt = f"""
        Work Order Type: "{work_order_type}".
        The work order description is: "{work_order_description}".
        The plant is: "{plant}".

        User's Previous work status and notes with hours for extra context: 
        {wo_status_and_notes_with_time_allocation_table}

        SPECIFIC HOLD REASON REQUIREMENTS (use these to guide your validation):
        {hold_reason_requirements}

        GENERAL VALIDATION GUIDELINES:
        {hold_reason_validation_instructions}

        ANALYZE the hold reason content to identify what hold type was performed:
        "{hold_reason}"

        Conversation between Tech and You, starting with his hold reason:
        Person | chat message
        {follow_up_questions_answers_table}

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

        return response

    except Exception as e:
        st.error(f"Error converting to CAR format: {e}")
        return CARFormatResponse(
            cause="",
            action="",
            result="",
            success=False,
            error_message=str(e)
        )


def convert_to_client_summary(conversation_table: list[dict]) -> ClientSummaryResponse:
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
        {format_conversation_history(conversation_table)}

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


