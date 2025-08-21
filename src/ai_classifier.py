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

load_dotenv()
 
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
        status_requirements = get_prompt(f"work_status.{work_status.title()}")
        
        if not status_requirements:
            return WorkStatusValidationResponse(valid=False, missing=f"Unknown work status: {work_status}",  follow_up_question="")
        
        prompt = f"""
        You are validating an operational log for work status: {work_status}.
        The work order description is: "{work_order_description}".

        USER'S OPERATIONAL LOG:
        "{operational_log}"

        Previous Follow-up Question and Answers:
        {follow_up_questions_answers_table}

        REQUIREMENTS (guidelines, not strict rules):
        {status_requirements}
        
        INSTRUCTIONS:
            1. Check if the OPERATIONAL LOG covers the majority of the REQUIREMENTS. These are the critical elements. If they are present or reasonably implied, validation should PASS.
            2. Do not require every single detail (like tools, exact wording, or formal structure).
            **IMPORTANT: Treat the combination of the USER'S OPERATIONAL LOG and the previous follow-up Q&A as the complete context. Do not require the final line alone to restate all details.**
            3. Only mark invalid if important details are clearly missing.
            4. If invalid, generate ONE concise follow-up question that:
                - Asks for the missing information in a natural, conversational way
                - Avoids repeating the same phrasing as before
                - Is tailored to what’s missing

            Return the result strictly as JSON with fields:
            - valid (boolean)
            - missing (string with explanation of what’s missing, or "" if nothing)
            - follow_up_question (string with 1 specific follow-up question to gather missing information)
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
                        "follow_up_question": {
                            "type": "string",
                            "description": "1 specific follow-up question to gather missing information"
                        }
                    },
                    "required": ["valid", "missing", "follow_up_question"]
                }
            }],
            function_call={"name": "validate_work_status"}
        )

        print(response)
        
        message = response.choices[0].message
        if message.function_call and message.function_call.arguments:
            response_content = message.function_call.arguments
        else:
            response_content = message.content  # fallback if no function call

        try:
            args = json.loads(response_content)
            return WorkStatusValidationResponse(**args)
        except Exception as e:
            return WorkStatusValidationResponse(
                valid=False,
                missing=f"Invalid JSON response format: {e}",
                follow_up_question="Follow-up question could not be generated."
            )
            
    except Exception as e:
        st.error(f"Error validating work status log: {e}")
        return WorkStatusValidationResponse(
            valid=False, 
            missing=f"Error: {str(e)}", 
            follow_up_question="Follow-up question could not be generated.")


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

        Work Status | Work Status Notes
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
        msg = response.choices[0].message

        if hasattr(msg, "parsed") and msg.parsed is not None:
            # Newer SDK
            response_json = msg.parsed
        elif msg.function_call and msg.function_call.arguments:
            # Older SDK using function calling
            response_json = json.loads(msg.function_call.arguments)
        elif msg.content:
            # Raw JSON in content (fallback)
            response_json = json.loads(msg.content)
        else:
            raise ValueError(f"No JSON returned by model: {msg}")
        
        return CARFormatResponse(
            cause=response_json.get("cause", "") if response_json else "",
            action=response_json.get("action", "") if response_json else "",
            result=response_json.get("result", "") if response_json else "",
            success=True
        )

                
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

        IMPORTANT: Return the answer strictly as a **JSON object**.
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


