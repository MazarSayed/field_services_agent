"""
AI Classifier Module
Handles OpenAI integration and work type classification
"""

import os
import openai
import streamlit as st
from dotenv import load_dotenv
from typing import Optional
import io
import tempfile
import json
from src.utils import get_prompt
from models.models import WorkStatusValidationResponse, TranscriptionResponse, CARFormatResponse, ClientSummaryResponse


 
def transcribe_audio(openai_client, audio_file) -> TranscriptionResponse:
    """
    Transcribe audio file using OpenAI Whisper (Speech-to-Text)
    
    Note: Uses Whisper-1 model for audio transcription (STT)
    This is different from TTS (Text-to-Speech) - we need STT to convert voice to text
    
    Args:
        audio_file: Audio file from st.audio_input (UploadedFile object)
        openai_client: OpenAI client instance
        
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

def validate_work_status_log(openai_client,operational_log: str, work_status: str, work_order_description: str, follow_up_questions_answers_table: str) -> WorkStatusValidationResponse:
    """
    Validate operational log against work status requirements and generate follow-up questions if needed
    
    Args:
        operational_log: The operational log to validate
        work_status: The work status type (Troubleshooting, Work, Warranty_Support, Delay, Training, Others)
        
    Returns:
        WorkStatusValidationResponse object with validation result and follow-up questions
    """

    try:
        # Get work status requirements
        status_requirements = get_prompt(f"work_status.{work_status}")
        
        if not status_requirements:
            return WorkStatusValidationResponse(valid=False, missing=f"Unknown work status: {work_status}", follow_up_questions=[])
        
        prompt = f"""
        Validate the following operational log against the specific requirements for {work_status} work status.
        For the given work order description: {work_order_description}

        OPERATIONAL LOG:
        "{operational_log}"

        Any Previous Follow up questions and answers:
        Questions | Answers
        {follow_up_questions_answers_table}
        
        REQUIREMENTS FOR {work_status.upper()}:
        {status_requirements}
        
        Please analyze if the operational log meets ALL the requirements. If it fails validation, generate 1-2 specific follow-up questions to gather the missing information.
        
        Respond with a JSON object in this exact format:
        {{
            "valid": true/false,
            "missing": "description of what is missing (if valid is false)",
            "follow_up_questions": ["question 1", "question 2"]
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        # Extract response content and parse JSON
        response_content = response.choices[0].message.content
        try:
            args = json.loads(response_content)
            # Use Pydantic model for validation and type safety
            return WorkStatusValidationResponse(**args)
        except json.JSONDecodeError:
            return WorkStatusValidationResponse(valid=False, missing="Invalid JSON response format", follow_up_questions=[])
        
    except Exception as e:
        st.error(f"Error validating work status log: {e}")
        return WorkStatusValidationResponse(valid=False, missing=f"Error: {str(e)}", follow_up_questions=[])


def convert_to_car_format(openai_client, completion_notes: str, wo_status_and_notes_table: str, work_order_description: str) -> CARFormatResponse:
    """
    Convert completion notes to CAR (Cause, Action, Result) format using gpt-4o-mini
    
    Args:
        completion_notes: Original completion notes
        wo_status_and_notes_table: Work order description for context
        
    Returns:
        CARFormatResponse object with structured CAR format data
    """

    
    try:
        prompt = f"""
        Convert the following completion notes into a structured CAR (Cause, Action, Result) format.
        Given below is each work status and notes from the field tech on each task.
        Work Order Description: {work_order_description}

        Work Status | Work Sttus Notes
        {wo_status_and_notes_table}

        Final Completion Notes from Field Tech:
        {completion_notes}
        
        GLOBAL CAR FORMAT REQUIREMENTS:
        {get_prompt("car_format_check")}
        
        Please analyze the notes and provide:
        
        CAUSE: [What caused the need for this work? What was the initial problem or situation?]
        
        ACTION: [What specific actions were taken? What work was performed?]
        
        RESULT: [What was the outcome? Was the issue resolved? Any recommendations or follow-up needed?]
        
        Ensure all requirements above are met. If any section cannot be adequately determined from the notes.
        
        Respond with a JSON object in this exact format:
        {{
            "cause": "description of what caused the need for this work",
            "action": "description of what specific actions were taken",
            "result": "description of what was the outcome of the work"
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # Extract response content and parse JSON
        response_content = response.choices[0].message.content
        try:
            args = json.loads(response_content)
            return CARFormatResponse(**args)
        except json.JSONDecodeError:
            return CARFormatResponse(cause="", action="", result="") 
        
    except Exception as e:
        st.error(f"Error converting to CAR format: {e}")
        return CARFormatResponse(cause="", action="", result="")


def convert_to_client_summary(openai_client, Conversation_tech_ai_client_table: str) -> ClientSummaryResponse:
    """
    Convert AI and human messages into a client-friendly summary and notes
    
    Args:
        ai_message: The AI's response or technical message
        human_message: The human's question or input
        
    Returns:
        ClientSummaryResponse object with summary and notes
    """

    
    try:
        prompt = f"""
        Convert the following technical conversation into a simple, client-friendly format.
        
        Conversation between Field Tech and Client:
        Tech | Client
        {Conversation_tech_ai_client_table}
        
        Please create:
        
        1. A TWO-LINE SUMMARY that explains what happened in simple terms
        2. SIMPLIFIED NOTES that a basic client can understand (avoid technical jargon)
        
        Requirements:
        - Use everyday language, not solar/technical terms
        - Make it sound like normal business communication
        - Focus on what was accomplished or what the client needs to know
        - Keep it professional but conversational
        - If technical terms are unavoidable, explain them simply
        
        Provide a clear summary and notes that any business client would understand.
        
        Respond with a JSON object in this exact format:
        {{
            "summary": "two-line summary in plain language explaining what happened",
            "notes": "simplified notes for basic clients in plain english language"
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # Extract response content and parse JSON
        response_content = response.choices[0].message.content
        try:
            args = json.loads(response_content)
            return ClientSummaryResponse(
                summary=args.get("summary", ""),
                notes=args.get("notes", ""),
                success=True
            )
        except json.JSONDecodeError:
            return ClientSummaryResponse(
                summary="",
                notes="",
                success=False,
                error_message="Invalid JSON response format"
            )
        
    except Exception as e:
        st.error(f"Error converting to client summary: {e}")
        return ClientSummaryResponse(
            summary="Unable to process request",
            notes="There was an error processing your request. Please try again or contact support.",
            success=False,
            error_message=str(e)
        )


