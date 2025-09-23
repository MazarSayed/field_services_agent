"""
AI Classifier Module
Handles OpenAI integration and work type classification
"""

import os
import openai
from dotenv import load_dotenv
from typing import Optional, Union
import tempfile
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
        
    Args:
        openai_client: OpenAI client instance
        audio_file: Audio file from audio input (UploadedFile object)
        
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
        print(f"Error transcribing audio: {e}")
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

def validate_work_status_log(operational_log: str, work_order_type: str, work_status: Union[str, dict], work_order_description: str, plant: str, wo_status_and_notes_with_time_allocation_table: str, messages: list[dict]) -> WorkStatusValidationResponse:
    """
    Validate operational log against work status requirements and generate follow-up questions if needed
    
    Args:
        operational_log: The operational log to validate
        work_order_type: The work order type
        work_status: The work status types and along with their percentage of occurance
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_time_allocation_table: Table of work status and notes with time allocation
        messages: List of conversation messages to pass directly to OpenAI API
        
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
        
        # Format conversation history for inclusion in prompt
        conversation_context = ""
        if messages and len(messages) > 1:
            conversation_context = "\n\n## CONVERSATION HISTORY:\n"
            for i, msg in enumerate(messages[1:], 1):
                role = "Assistant" if msg["role"] == "assistant" else "Technician"
                conversation_context += f"Turn {i} - {role}: {msg['content']}\n"

        # Combine everything into a comprehensive system prompt
        prompt = f"""
        ## WORK ORDER CONTEXT:
        Work Order Type: "{work_order_type}".\n
        You are validating an operational log for Work Contribution: {work_contribtion}.\n
        The cause of work: "{work_order_description}".\n
        The plant is: "{plant}".\n

        ## PREVIOUS LOGS FOR THE SAME WORK ORDER FOR EXTRA CONTEXT:
        {wo_status_and_notes_with_time_allocation_table}\n

        ## WORK ORDER TYPE GUIDELINES:
        {work_order_type_guidelines}\n

        ## WORK BASED GUIDELINES:
        {status_requirements}\n

        ## VALIDATION INSTRUCTIONS:
        {validation_guidelines}\n

        If the log is invalid, return the follow-up question based on "Intial User Log Notes" and follow up answers from the conversation history.\n
        ## Intial User Log Notes:\n
        {operational_log}\n
        
        Your Previous Follow Up Questions and Answers:\n
        {conversation_context}
        """
        
        # Prepare messages for OpenAI API
        messages_list = [
            {"role": "system", "content": work_status_system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Use instructor patched client for Pydanticresponse model
        patched_client = get_patched_client()
        print("user_prompt: ", prompt)
        print("work status system prompt: ", work_status_system_prompt)

        response = patched_client.chat.completions.create(
            model="gpt-4o",
            response_model=WorkStatusValidationResponse,
            messages=messages_list,
            max_tokens=300,
            temperature=0.1
        )
        print("messages_list: ", messages_list)
        # Return the validated Pydantic model directly
        return response

            
    except Exception as e:
        print(f"Error validating work status log: {e}")
        return WorkStatusValidationResponse(
            valid=False, 
            missing=f"Error: {str(e)}", 
            follow_up_question="Follow-up question could not be generated."
        )


def validate_reason_for_hold(hold_reason: str, work_order_type: str, work_order_description: str, plant: str, wo_status_and_notes_with_time_allocation_table: str, messages: list[dict]) -> HoldReasonValidationResponse:
    """
    Validate hold reason against work order requirements and generate follow-up questions if needed
    
    Args:
        hold_reason: The hold reason to validate
        work_order_type: Work order type
        work_order_description: Description of the work order for context
        wo_status_and_notes_with_time_allocation_table: Table of work status and notes with time allocation
        messages: List of conversation messages to pass directly to OpenAI API
        
    Returns:
        HoldReasonValidationResponse object with validation result and follow-up questions
    """

    try:
        # Get hold reason type requirements
        hold_reason_requirements = ""
        hold_reason_requirements += get_prompt(f"hold_reason_types.{hold_reason}") + "\n"
        hold_reason = hold_reason+"-"+messages[0]["content"]

        # Get validation instructions and system prompt
        hold_reason_validation_instructions = get_prompt("hold_reason_validation_instructions")
        hold_reason_system_prompt = get_prompt("system_prompts.hold_reason_system_prompt")
        
        # Format conversation history for inclusion in prompt
        conversation_context = ""
        if messages and len(messages) > 1:
            conversation_context = "\n\n## CONVERSATION HISTORY:\n"
            for i, msg in enumerate(messages[1:], 1):
                role = "Assistant" if msg["role"] == "assistant" else "Technician"
                conversation_context += f"Turn {i} - {role}: {msg['content']}\n"

        # Combine everything into a comprehensive system prompt
        prompt = f"""

        ## WORK ORDER CONTEXT:
        Work Order Type: "{work_order_type}".
        The cause of work: "{work_order_description}".
        The plant is: "{plant}".

        ## PREVIOUS WORK LOGS FOR THE SAME WORK ORDER FOR EXTRA CONTEXT:
        {wo_status_and_notes_with_time_allocation_table}

        ## HOLD REASON REQUIREMENTS:
        {hold_reason_requirements}

        ## VALIDATION INSTRUCTIONS:
        {hold_reason_validation_instructions}

        If the hold reason is invalid, return the follow-up question based on "Reason for Hold" and follow up answers from the conversation history.
        ## Reason for Hold:
        {hold_reason}
        
        Your Previous Follow Up Questions and Answers:\n
        {conversation_context}

        """
        
        # Prepare messages for OpenAI API
        messages_list = [
            {"role": "system", "content": hold_reason_system_prompt},
            {"role": "user", "content": prompt}
        ]
        print("user_prompt: ", prompt)
        print("hold reason system prompt: ", hold_reason_system_prompt)
        
        # Use instructor patched client for Pydantic response model
        patched_client = get_patched_client()
        
        response = patched_client.chat.completions.create(
            model="gpt-4o",
            response_model=HoldReasonValidationResponse,
            messages=messages_list,
            max_tokens=300,
            temperature=0.1
        )
        print("messages_list: ", messages_list)
        # Return the validated Pydantic model directly
        return response
            
    except Exception as e:
        print(f"Error validating work status log: {e}")
        return HoldReasonValidationResponse(
            valid=False,
            missing=f"Error: {str(e)}",
            follow_up_question="Follow-up question could not be generated.",
            hold_reason_analysis="Analysis could not be generated due to error.",
            recommended_actions="Please review the hold reason manually."
        )


def convert_to_car_format(work_order_type: str, final_completion_notes: str, wo_status_and_notes_with_time_allocation_table: str, work_order_description: str) -> CARFormatResponse:
    """
    Convert completion notes to CAR (Cause, Action, Result) format using gpt-4o-mini
    
    Args:
        work_order_type: Work order type
        final_completion_notes: Original completion notes from field tech
        wo_status_and_notes_with_time_allocation_table: Table of work status and notes for each task with time allocation
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
        The cause of work: {work_order_description}

        ## WORK STATUS | WORK STATUS NOTES WITH TIME ALLOCATION (includes dates):
        {wo_status_and_notes_with_time_allocation_table}

        ## INSTRUCTIONS:
        {car_prompt}

        ## FINAL COMPLETION NOTES FROM FIELD TECH:
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
        print(f"Error converting to CAR format: {e}")
        return CARFormatResponse(
            cause="",
            action="",
            result="",
            success=False,
            error_message=str(e)
        )


def convert_to_client_summary(conversation_table: list[dict], work_order_description: str, work_status: dict, plant: str, work_order_type: str) -> ClientSummaryResponse:
    """
    Convert AI and human messages into a client-friendly summary and notes
    
    Args:
        conversation_table: Conversation between Tech and AI
        work_order_description: Description of the work order for context
        work_status: Work status types and their percentage allocation
        plant: Plant location for context
        work_order_type: Type of work order (Project, OEM, Preventive, etc.)
        
    Returns:
        ClientSummaryResponse object with summary and notes
    """

    try:
        status_requirements = ""
        work_contribtion = ""
        for work_status_type, values in work_status.items():
            pct = values["percentage"] if isinstance(values, dict) else values
            if pct > 10:
                work_contribtion += f"{work_status_type} - {pct}%\n"
                
        # Get client summary conversion prompt and system prompt
        user_prompt = get_prompt("client_summary_conversion")
        client_summary_system_prompt = get_prompt("system_prompts.client_summary_system_prompt")
        
        prompt = f"""
        ## WORK ORDER CONTEXT:
        Work Order Type: "{work_order_type}".
        You are summarizing a conversation between a field technician and a client for Work Contribution: {work_contribtion}.
        The cause of work: "{work_order_description}".
        The plant is: "{plant}".

        ## INSTRUCTIONS ON SUMMARIZING THE CONVERSATION:
        {user_prompt}

        ## CONVERSATION BETWEEN TECH AND YOU (ASSISTANT):
        Person | chat message
        {format_conversation_history(conversation_table)}

        Focus mainly on CONVERSATION BETWEEN TECH AND YOU (ASSISTANT) section for the summary and notes.
        Do not use Markdown formatting in the summary and notes..
        Use simple and clear language.
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
            temperature=0.1
        )
        
        # Return the validated Pydantic model directly
        return response
        
    except Exception as e:
        print(f"Error converting to client summary: {e}")
        return ClientSummaryResponse(
            summary="Unable to process request",
            notes="There was an error processing your request. Please try again or contact support.",
            success=False,
            error_message=str(e)
        )


