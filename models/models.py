from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# ============================================================================
# AI Classifier Request Models
# ============================================================================

class TranscriptionRequest(BaseModel):
    """Request model for audio transcription"""
    audio_file: Any = Field(..., description="Audio file from audio input (UploadedFile object)")


class WorkStatusValidationRequest(BaseModel):
    """Request model for work status log validation"""
    operational_log: str = Field(..., description="Operational log text to validate")
    work_status: Union[str, dict] = Field(..., description="Work status type (string) or type/percentage/hours mapping (dict)")
    work_order_id: str = Field(..., description="Work order ID to fetch tech name and plant info")
    follow_up_questions_answers_table: list[dict] = Field(..., description="List of conversation messages with role and content")


class CARFormatConversionRequest(BaseModel):
    """Request model for CAR format conversion"""
    completion_notes: str = Field(..., description="Original completion notes from field tech")
    wo_status_and_notes_table: str = Field(..., description="Table of work status and notes for each task")
    work_order_description: str = Field(..., description="Work order description for context")


class ClientSummaryConversionRequest(BaseModel):
    """Request model for client summary conversion"""
    conversation_tech_ai_client_table: list[dict] = Field(..., description="List of conversation messages with role and content")


# ============================================================================
# AI Classifier Response Models
# ============================================================================

class WorkStatusValidationResponse(BaseModel):
    """Response model for work status log validation"""
    valid: bool = Field(description="Whether the operational log meets all guidlines provided")
    follow_up_question: str = Field(description="A single specific follow-up question to gather information based on user log notes provided")


class HoldReasonValidationResponse(BaseModel):
    """Response model for hold reason validation"""
    valid: bool = Field(description="Whether the hold reason meets all requirements")
    follow_up_question: str = Field(description="A single specific follow-up question to gather information based on user hold reason provided")


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
    notes: str = Field(description="Simplified notes for basic clients between 60 to 70 words")
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
    wo_status_and_notes_with_time_allocation_table: str = Field(..., description="Table of work status and notes with time allocation")
    follow_up_questions_answers_table: list[dict] = Field(..., description="List of conversation messages with role and content")


class HoldReasonValidationRequest(BaseModel):
    """Request model for hold reason validation"""
    hold_reason: str = Field(..., description="The hold reason to validate")
    work_order_type: str = Field(..., description="Work order type")
    work_order_description: str = Field(..., description="Work order description")
    plant: str = Field(..., description="Plant description")
    wo_status_and_notes_with_time_allocation_table: str = Field(..., description="Table of work status and notes with time allocation")
    follow_up_questions_answers_table: list[dict] = Field(..., description="List of conversation messages with role and content")


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



class HoldNotesSubmissionRequest(BaseModel):
    """Request model for hold notes submissions"""
    hold_reason: str = Field(..., description="Reason for hold")
    hold_date: str = Field(..., description="Hold date")
    notes: str = Field(..., description="Hold notes")
    summary: str = Field(..., description="PHold summary")
    work_order_id: str = Field(default=None, description="Work order ID")

class WorkStatusLogs(BaseModel):
    """Response model for work status logs queries"""
    work_status_logs: List[Dict[str, Any]] = Field(..., description="List of work status logs")

class HoldNotes(BaseModel):
    """Response model for hold notes queries"""
    hold_notes: List[Dict[str, Any]] = Field(..., description="List of hold_notes")

# ============================================================================
# Chat and Conversation Models
# ============================================================================

class ChatSubmissionRequest(BaseModel):
    """Request model for chat submissions"""
    work_order_id: Optional[str] = Field(default=None, description="Work order ID")
    conversation_tech_ai_client_table: Optional[list[dict]] = Field(default=None, description="List of conversation messages with role and content")
    work_status: Optional[str] = Field(default=None, description="Work status")


# ============================================================================
# Legacy/Compatibility Models
# ============================================================================

class CompletionNotesRequest(BaseModel):
    """Legacy request model for completion notes (kept for compatibility)"""
    completion_notes: str = Field(..., description="Completion notes text")
    work_order_description: str = Field(..., description="Work order description")
    wo_status_and_notes_table: Optional[str] = Field(default=None, description="Table of work status and notes for each task (optional if work_order_id provided)")
    work_order_id: str = Field(..., description="Work order ID to fetch work status logs with dates")
    work_order_type: Optional[str] = Field(default=None, description="Work order type for validation")


class ClientSummaryRequest(BaseModel):
    """Request model for client summary conversion"""
    conversation_tech_ai_client_table: list[dict] = Field(..., description="List of conversation messages with role and content")
    work_order_description: str = Field(..., description="Description of the work order for context")
    work_status: dict = Field(..., description="Work status types and their percentage allocation")
    plant: str = Field(..., description="Plant location for context")
    work_order_type: str = Field(..., description="Type of work order (Project, OEM, Preventive, etc.)")
