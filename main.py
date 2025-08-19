"""
Field Services Agent API
FastAPI application for managing solar work orders and field services
"""

import os
import yaml
import csv
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import openai

from src.ai_classifier import (
    validate_work_status_log, 
    convert_to_car_format, 
    convert_to_client_summary
)
from models.models import (
    WorkStatusValidationResponse, 
    CARFormatResponse, 
    ClientSummaryResponse
)

# Load configuration
def load_config():
    """Load configuration from config.yaml"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found")
    
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

config = load_config()

# Initialize FastAPI app
app = FastAPI(
    title="Field Services Agent API",
    description="API for managing solar work orders and field services",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# CSV file paths
CSV_FILES = {
    'work_orders': 'Database/work_orders.csv',
    'work_status_logs': 'Database/work_status_logs.csv',
    'completion_notes': 'Database/completion_notes.csv',
    'technicians': 'Database/technicians.csv',
    'work_status_types': 'Database/work_status_types.csv',
}

# CSV utility functions
def read_csv_file(filename: str) -> List[Dict[str, Any]]:
    """Read CSV file and return list of dictionaries"""
    try:
        if not os.path.exists(filename):
            return []
        
        with open(filename, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

def write_csv_file(filename: str, data: List[Dict[str, Any]], fieldnames: List[str]) -> bool:
    """Write data to CSV file"""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True
    except Exception as e:
        print(f"Error writing {filename}: {e}")
        return False

def append_to_csv_file(filename: str, data: Dict[str, Any], fieldnames: List[str]) -> bool:
    """Append single row to CSV file"""
    try:
        # Read existing data
        existing_data = read_csv_file(filename)
        
        # Add new row
        existing_data.append(data)
        
        # Write back to file
        return write_csv_file(filename, existing_data, fieldnames)
    except Exception as e:
        print(f"Error appending to {filename}: {e}")
        return False

def get_next_id(filename: str) -> int:
    """Get next available ID for CSV file"""
    try:
        data = read_csv_file(filename)
        if not data:
            return 1
        
        # Find the highest ID
        ids = [int(row.get('id', 0)) for row in data if row.get('id')]
        return max(ids) + 1 if ids else 1
    except Exception as e:
        print(f"Error getting next ID for {filename}: {e}")
        return 1

# Load data functions
def load_work_orders() -> List[Dict[str, Any]]:
    """Load work orders from CSV"""
    return read_csv_file(CSV_FILES['work_orders'])

def load_completion_notes() -> List[Dict[str, Any]]:
    """Load completion notes from CSV"""
    return read_csv_file(CSV_FILES['completion_notes'])

def load_technicians() -> List[Dict[str, Any]]:
    """Load technicians from CSV"""
    return read_csv_file(CSV_FILES['technicians'])

# OpenAI client dependency
def get_openai_client():
    """Get OpenAI client instance"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        return openai.OpenAI(api_key=api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing OpenAI client: {str(e)}")

# Endpoint 1: Extract work orders for a tech on a specific date
@app.get("/work-orders/{tech_name}/{work_date}", response_model=WorkOrderResponse)
async def get_work_orders(
    tech_name: str, 
    work_date: str,
    # openai_client: openai.OpenAI = Depends(get_openai_client)
):
    """
    Extract work orders assigned to a technician on a specific date
    """
    try:
        # Parse date
        try:
            parsed_date = datetime.strptime(work_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Load work orders from CSV
        work_orders_data = load_work_orders()
        
        if not work_orders_data:
            return WorkOrderResponse(
                work_orders=[],
                total_pending=0,
                total_completed=0
            )
        
        # Filter by technician and date
        filtered_orders = []
        for order in work_orders_data:
            if (order.get('tech_name') == tech_name and 
                order.get('work_date') == work_date):
                filtered_orders.append(order)
        
        if not filtered_orders:
            return WorkOrderResponse(
                work_orders=[],
                total_pending=0,
                total_completed=0
            )
        
        # Count pending and completed
        total_pending = len([wo for wo in filtered_orders if wo.get('status', '').lower() in ['pending', 'open', 'assigned']])
        total_completed = len([wo for wo in filtered_orders if wo.get('status', '').lower() in ['completed', 'closed', 'finished']])
        
        return WorkOrderResponse(
            work_orders=filtered_orders,
            total_pending=total_pending,
            total_completed=total_completed
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work orders: {str(e)}")

# Endpoint 2: Validate work status log
@app.post("/validate-work-status", response_model=WorkStatusValidationResponse)
async def validate_work_status(
    request: WorkStatusLogRequest,
    openai_client: openai.OpenAI = Depends(get_openai_client)
):
    """
    Validate operational log against work status requirements
    
    Example request body:
    {
        "operational_log": "Replaced faulty inverter module and tested system functionality",
        "work_status": "Work",
        "work_order_description": "Inverter replacement at solar site",
        "tech_name": "John Doe",
        "work_date": "2024-01-15",
        "follow_up_questions_answers_table": "Q: What was the fault code? | A: E001\nQ: Was the system tested? | A: Yes, fully operational"
    }
    """
    try:
        result = validate_work_status_log(
            openai_client=openai_client,
            operational_log=request.operational_log,
            work_status=request.work_status,
            work_order_description=request.work_order_description,
            follow_up_questions_answers_table=request.follow_up_questions_answers_table
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating work status: {str(e)}")

# Endpoint 3: Submit work status details to CSV database
@app.post("/submit-work-status")
async def submit_work_status(request: WorkStatusSubmissionRequest):
    """
    Submit work status details to CSV database
    """
    try:
        # Parse date
        try:
            parsed_date = datetime.strptime(request.work_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get next ID
        next_id = get_next_id(CSV_FILES['work_status_logs'])
        
        # Prepare data for CSV
        work_status_data = {
            'id': next_id,
            'tech_name': request.tech_name,
            'work_date': request.work_date,
            'work_status': request.work_status,
            'time_spent': request.time_spent,
            'notes': request.notes,
            'summary': request.summary,
            'work_order_id': request.work_order_id or '',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Define fieldnames for CSV
        fieldnames = [
            'id', 'tech_name', 'work_date', 'work_status', 'time_spent',
            'notes', 'summary', 'work_order_id', 'created_at', 'updated_at'
        ]
        
        # Append to CSV file
        if append_to_csv_file(CSV_FILES['work_status_logs'], work_status_data, fieldnames):
            return {
                "message": "Work status submitted successfully",
                "log_id": next_id,
                "tech_name": request.tech_name,
                "work_date": request.work_date
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save work status to database")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting work status: {str(e)}")

# Endpoint 4: Convert completion notes to CAR format
@app.post("/convert-to-car", response_model=CARFormatResponse)
async def convert_completion_notes_to_car(
    request: CompletionNotesRequest,
    openai_client: openai.OpenAI = Depends(get_openai_client)
):
    """
    Convert completion notes to CAR format
    
    Example request body:
    {
        "completion_notes": "Inverter was showing fault code E001. Replaced the faulty module and tested system. All systems now operational.",
        "work_order_description": "Inverter replacement at solar site",
        "wo_status_and_notes_table": "Work | Initial inspection and fault diagnosis\nWork | Module replacement\nWork | System testing and verification"
    }
    """
    try:
        result = convert_to_car_format(
            openai_client=openai_client,
            completion_notes=request.completion_notes,
            wo_status_and_notes_table=request.wo_status_and_notes_table,
            work_order_description=request.work_order_description
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting to CAR format: {str(e)}")

# Endpoint 5: Convert conversation to client summary
@app.post("/convert-to-client-summary", response_model=ClientSummaryResponse)
async def convert_conversation_to_summary(
    request: ClientSummaryRequest,
    openai_client: openai.OpenAI = Depends(get_openai_client)
):
    """
    Convert conversation to client-friendly summary
    
    Example request body:
    {
        "conversation_tech_ai_client_table": "Tech | The inverter was showing a fault code. I've replaced the faulty module and tested the system. Everything is working now.\nClient | Great, thank you for the quick fix.\nAI | System status confirmed operational, all tests passed."
    }
    """
    try:
        result = convert_to_client_summary(
            openai_client=openai_client,
            Conversation_tech_ai_client_table=request.conversation_tech_ai_client_table
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting to client summary: {str(e)}")

# Endpoint 6: Get all technicians
@app.get("/technicians")
async def get_technicians():
    """Get all technicians"""
    try:
        technicians = load_technicians()
        return {"technicians": technicians}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading technicians: {str(e)}")

# Endpoint 7: Get work status types
@app.get("/work-status-types")
async def get_work_status_types():
    """Get all work status types"""
    try:
        status_types = read_csv_file(CSV_FILES['work_status_types'])
        return {"work_status_types": status_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading work status types: {str(e)}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Get configuration endpoint
@app.get("/config")
async def get_config():
    """Get current configuration (excluding sensitive data)"""
    safe_config = {
        "defaults": config.get("defaults", {}),
        "api": config.get("api", {}),
        "database": {"type": "csv"},
        "openai": {"model": config.get("openai", {}).get("model")}
    }
    return safe_config

if __name__ == "__main__":
    import uvicorn
    
    # Get config values
    host = config['api']['host']
    port = config['api']['port']
    debug = config['api']['debug']
    
    print(f"Starting Field Services Agent API on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Using CSV files as database")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
