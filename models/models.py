from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# ============================================================================
# AI Classifier Request Models
# ============================================================================

class TranscriptionRequest(BaseModel):
    """Request model for audio transcription"""
    audio_file: Any = Field(..., description="Audio file from st.audio_input (UploadedFile object)")


class WorkStatusValidationRequest(BaseModel):
    """Request model for work status log validation"""
    operational_log: str = Field(..., description="Operational log text to validate")
    work_status: str = Field(..., description="Work status type (Troubleshooting, Work, Warranty_Support, Delay, Training, Others)")
    work_order_description: str = Field(..., description="Work order description for context")
    follow_up_questions_answers_table: str = Field(..., description="Table of previous follow-up questions and answers")


class CARFormatConversionRequest(BaseModel):
    """Request model for CAR format conversion"""
    completion_notes: str = Field(..., description="Original completion notes from field tech")
    wo_status_and_notes_table: str = Field(..., description="Table of work status and notes for each task")
    work_order_description: str = Field(..., description="Work order description for context")


class ClientSummaryConversionRequest(BaseModel):
    """Request model for client summary conversion"""
    conversation_tech_ai_client_table: str = Field(..., description="Table of conversation between tech, AI, and client")


# ============================================================================
# AI Classifier Response Models
# ============================================================================

class WorkStatusValidationResponse(BaseModel):
    """Response model for work status log validation"""
    valid: bool = Field(description="Whether the operational log meets all requirements")
    missing: str = Field(description="Specific missing requirements if validation fails")
    follow_up_question: str = Field(description="A single specific follow-up question to gather missing information")


class HoldReasonValidationResponse(BaseModel):
    """Response model for hold reason validation"""
    valid: bool = Field(description="Whether the hold reason meets all requirements")
    missing: str = Field(description="Specific missing requirements if validation fails")
    follow_up_question: str = Field(description="A single specific follow-up question to gather missing information")
    hold_reason_analysis: str = Field(description="Analysis of the hold reason and its validity")
    recommended_actions: str = Field(description="Recommended actions to resolve the hold")


class TranscriptionResponse(BaseModel):
    """Response model for audio transcription"""
    transcript: str = Field(description="Transcribed text from audio file")
    success: bool = Field(description="Whether transcription was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if transcription failed")


class CARFormatResponse(BaseModel):
    """Response model for CAR format conversion"""
    cause: str = Field(description="What caused the need for this work")
    action: str = Field(description="What specific actions were taken")
    result: str = Field(description="What was the outcome of the work")
    success: bool = Field(description="Whether conversion was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if conversion failed")


class ClientSummaryResponse(BaseModel):
    """Response model for client summary conversion"""
    summary: str = Field(description="One-line summary in plain language under 10 words")
    notes: str = Field(description="Simplified notes for basic clients")
    success: bool = Field(description="Whether conversion was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if conversion failed")


# ============================================================================
# Work Order Management Models
# ============================================================================

class WorkOrderRequest(BaseModel):
    """Request model for work order queries"""
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date in YYYY-MM-DD format")


class WorkOrderResponse(BaseModel):
    """Response model for work order queries"""
    work_orders: List[Dict[str, Any]] = Field(..., description="List of work orders")
    total_pending: int = Field(..., description="Total pending work orders")
    total_completed: int = Field(..., description="Total completed work orders")


class WorkOrderUpdateResponse(BaseModel):
    """Response model for work order updates"""
    work_order_id: str = Field(..., description="Work order ID")
    status: str = Field(..., description="Updated status")
    message: str = Field(..., description="Update message")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")


# ============================================================================
# Work Status Management Models
# ============================================================================

class WorkStatusLogRequest(BaseModel):
    """Request model for work status log operations"""
    operational_log: str = Field(..., description="Operational log text")
    work_status: Optional[Union[str, dict]] = Field(
        None,
        description="Work status type (string) or type/percentage/hours mapping (dict)"
    )
    work_order_description: str = Field(..., description="Work order description")
    plant: str = Field(..., description="Plant description")
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date")
    wo_status_and_notes_with_hours_table: str = Field(..., description="Table of work status and notes with hours")
    follow_up_questions_answers_table: str = Field(..., description="Table of previous follow-up questions and answers")


class HoldReasonValidationRequest(BaseModel):
    """Request model for hold reason validation"""
    hold_reason: str = Field(..., description="The hold reason to validate")
    work_order_type: str = Field(..., description="Work order type")
    work_order_description: str = Field(..., description="Work order description")
    plant: str = Field(..., description="Plant description")
    wo_status_and_notes_with_hours_table: str = Field(..., description="Table of work status and notes with hours")
    follow_up_questions_answers_table: str = Field(..., description="Previous follow-up questions and answers")


class WorkStatusSubmissionRequest(BaseModel):
    """Request model for work status submissions"""
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date")
    work_status: dict = Field(..., description="Work status type and assigned percentage")
    plant: str = Field(..., description="Plant description")
    start_time: str = Field(..., description="Timestamp work started")
    end_time: str = Field(..., description="Timestamp work ended")
    time_spent: float = Field(..., description="Time spent in hours")
    notes: str = Field(..., description="Work notes")
    summary: str = Field(..., description="Work summary")
    work_order_id: Optional[str] = Field(default=None, description="Work order ID")
    complete_flag: Optional[bool] = Field(default=None, description="Whether work is complete")


class WorkStatusLogs(BaseModel):
    """Response model for work status logs queries"""
    work_status_logs: List[Dict[str, Any]] = Field(..., description="List of work status logs")


# ============================================================================
# Chat and Conversation Models
# ============================================================================

class ChatSubmissionRequest(BaseModel):
    """Request model for chat submissions"""
    work_order_id: Optional[str] = Field(default=None, description="Work order ID")
    conversation_tech_ai_client_table: Optional[str] = Field(default=None, description="Conversation table")
    work_status: Optional[str] = Field(default=None, description="Work status")


# ============================================================================
# Legacy/Compatibility Models
# ============================================================================

class CompletionNotesRequest(BaseModel):
    """Legacy request model for completion notes (kept for compatibility)"""
    completion_notes: str = Field(..., description="Completion notes text")
    work_order_description: str = Field(..., description="Work order description")
    wo_status_and_notes_table: str = Field(..., description="Table of work status and notes for each task")


class ClientSummaryRequest(BaseModel):
    """Legacy request model for client summary (kept for compatibility)"""
    conversation_tech_ai_client_table: str = Field(..., description="Table of conversation between tech, AI, and client")
