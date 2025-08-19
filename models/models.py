from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class WorkStatusValidationResponse(BaseModel):
    """Schema for work status log validation response"""
    valid: bool = Field(description="Whether the operational log meets all requirements")
    missing: str = Field(description="List of specific missing requirements if validation fails")
    follow_up_questions: List[str] = Field(description="List of 1-2 specific follow-up questions to gather missing information")


class TranscriptionResponse(BaseModel):
    """Schema for audio transcription response"""
    transcript: str = Field(description="Transcribed text from audio file")
    success: bool = Field(description="Whether transcription was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if transcription failed")


class CARFormatResponse(BaseModel):
    """Schema for CAR format conversion response"""
    cause: str = Field(description="What caused the need for this work")
    action: str = Field(description="What specific actions were taken")
    result: str = Field(description="What was the outcome of the work")
    success: bool = Field(description="Whether conversion was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if conversion failed")


class ClientSummaryResponse(BaseModel):
    """Schema for client summary conversion response"""
    summary: str = Field(description="Two-line summary in plain language")
    notes: str = Field(description="Simplified notes for basic clients")
    success: bool = Field(description="Whether conversion was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if conversion failed")
    

# Pydantic models for API requests/responses
class WorkOrderRequest(BaseModel):
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date in YYYY-MM-DD format")

class WorkOrderResponse(BaseModel):
    work_orders: List[Dict[str, Any]] = Field(..., description="List of work orders")
    total_pending: int = Field(..., description="Total pending work orders")
    total_completed: int = Field(..., description="Total completed work orders")

class WorkStatusLogRequest(BaseModel):
    operational_log: str = Field(..., description="Operational log text")
    work_status: str = Field(..., description="Work status type")
    work_order_description: str = Field(..., description="Work order description")
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date")
    follow_up_questions_answers_table: str = Field(..., description="Table of previous follow-up questions and answers")

class WorkStatusSubmissionRequest(BaseModel):
    tech_name: str = Field(..., description="Technician name")
    work_date: str = Field(..., description="Work date")
    work_status: str = Field(..., description="Work status type")
    time_spent: float = Field(..., description="Time spent in hours")
    notes: str = Field(..., description="Work notes")
    summary: str = Field(..., description="Work summary")
    work_order_id: Optional[str] = Field(None, description="Work order ID")

class CompletionNotesRequest(BaseModel):
    completion_notes: str = Field(..., description="Completion notes text")
    work_order_description: str = Field(..., description="Work order description")
    wo_status_and_notes_table: str = Field(..., description="Table of work status and notes for each task")

class ClientSummaryRequest(BaseModel):
    conversation_tech_ai_client_table: str = Field(..., description="Table of conversation between tech, AI, and client")
