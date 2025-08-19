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
from utils import get_prompt
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
        For the given word order descibtions: {work_order_description}

        OPERATIONAL LOG:
        "{operational_log}"

        Any Previous Follow up questions and answers:
        Questions | Answers
        {follow_up_questions_answers_table}
        
        REQUIREMENTS FOR {work_status.upper()}:
        {status_requirements}
        
        Please analyze if the operational log meets ALL the requirements. If it fails validation, generate 1-2 specific follow-up questions to gather the missing information.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
            response_format={"type": "json_object"},
            functions=[{
                "name": "validate_work_status",
                "description": "Validate operational log against work status requirements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "valid": {
                            "type": "boolean",
                            "description": "Whether the operational log meets all requirements"
                        },
                        "missing": {
                            "type": "string",
                            "description": "List of specific missing requirements if validation fails"
                        },
                        "follow_up_questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of 1-2 specific follow-up questions to gather missing information"
                        }
                    },
                    "required": ["valid", "missing", "follow_up_questions"]
                }
            }],
            function_call={"name": "validate_work_status"}
        )
        
        # Extract function call response
        function_call = response.choices[0].message.function_call
        if function_call and function_call.name == "validate_work_status":
            args = json.loads(function_call.arguments)
            # Use Pydantic model for validation and type safety
            return WorkStatusValidationResponse(**args)
        else:
            return WorkStatusValidationResponse(valid=False, missing="Invalid response format", follow_up_questions=[])
        
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
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"},
            functions=[{
                "name": "convert_to_car_format",
                "description": "Convert completion notes to CAR format",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cause": {
                            "type": "string",
                            "description": "What caused the need for this work"
                        },
                        "action": {
                            "type": "string",
                            "description": "What specific actions were taken"
                        },
                        "result": {
                            "type": "string",
                            "description": "What was the outcome of the work"
                        },
                    },
                    "required": ["cause", "action", "result"]
                }
            }],
        )
        return CARFormatResponse(**response.choices[0].message.content) 
        
    except Exception as e:
        st.error(f"Error converting to CAR format: {e}")
        return CARFormatResponse(**response.choices[0].message.content)


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
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
            response_format={"type": "json_object"},
            functions=[{
                "name": "convert_to_client_summary",
                "description": "Convert technical conversation to client-friendly summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Two-line summary in plain language explaining what happened"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Simplified notes for basic clients in plain english language"
                        }
                    },
                    "required": ["summary", "notes"]
                }
            }],
            function_call={"name": "convert_to_client_summary"}
        )
        
        # Extract function call response
        function_call = response.choices[0].message.function_call
        if function_call and function_call.name == "convert_to_client_summary":
            args = json.loads(function_call.arguments)
            return ClientSummaryResponse(
                summary=args.get("summary", ""),
                notes=args.get("notes", ""),
                success=True
            )
        else:
            return ClientSummaryResponse(
                summary="",
                notes="",
                success=False,
                error_message="Invalid response format"
            )
        
    except Exception as e:
        st.error(f"Error converting to client summary: {e}")
        return ClientSummaryResponse(
            summary="Unable to process request",
            notes="There was an error processing your request. Please try again or contact support.",
            success=False,
            error_message=str(e)
        )


