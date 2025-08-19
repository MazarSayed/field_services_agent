from pydantic import BaseModel, Field
from typing import List, Optional

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
