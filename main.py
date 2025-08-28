"""
Field Services Agent API
FastAPI application for managing solar work orders and field services
"""

from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import models and services
from models.models import (
    WorkOrderResponse, WorkStatusValidationResponse, CARFormatResponse, 
    ClientSummaryResponse, WorkStatusLogRequest, WorkStatusSubmissionRequest,
    CompletionNotesRequest, ClientSummaryRequest, WorkStatusLogs, WorkOrderUpdateResponse, 
    ChatSubmissionRequest
)
from src.field_services import get_field_services

# Initialize service layer
service = get_field_services()
config = service.data_access.config

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


# All business logic is now handled by the service layer

# Service dependency
def get_service():
    """Get field services instance"""
    return service

# Endpoint 1: Extract work orders for a tech on a specific date
@app.get("/work-orders/{config[defaults][tech_name]}/{work_date}", response_model=WorkOrderResponse)
async def get_work_orders(tech_name: str, work_date: str):
    """Extract work orders assigned to a technician on a specific date"""
    try:
        result = service.get_work_orders_for_tech(tech_name, work_date)
        return WorkOrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work orders: {str(e)}")

# Endpoint 1b: Get all work orders for a technician (no date filter)
@app.get("/work-orders", response_model=WorkOrderResponse)
async def get_all_work_orders_for_tech():
    """Extract all work orders assigned to a technician regardless of date"""
    try:
        tech_name = config['defaults']['tech_name']
        # print(tech_name)
        result = service.get_all_work_orders_for_tech(tech_name)
        return WorkOrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work orders: {str(e)}")

@app.put("/work-orders/{work_order_id}/complete", response_model=WorkOrderUpdateResponse)
async def complete_work_order(work_order_id: str):
    """Update a work order's status to Completed"""
    try:
        updated = service.update_work_order_status(work_order_id, "Completed")
        if not updated:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")
        
        return WorkOrderUpdateResponse(
            work_order_id=work_order_id,
            status="Completed",
            message="Work order marked as completed successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating work order: {str(e)}")



# Endpoint 2: Validate work status log
@app.post("/validate-work-status", response_model=WorkStatusValidationResponse)
async def validate_work_status(request: WorkStatusLogRequest):
    """Validate operational log against work status requirements"""
    try:
        result = service.validate_work_status(
            operational_log=request.operational_log,
            work_status=request.work_status,
            work_order_description=request.work_order_description,
            tech_name=request.tech_name,
            work_date=request.work_date,
            follow_up_questions_answers=request.follow_up_questions_answers_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating work status: {str(e)}")

# Endpoint 3: Submit work status details to CSV database
@app.post("/submit-work-status")
async def submit_work_status(request: WorkStatusSubmissionRequest):
    """Submit work status details to CSV database"""
    try:
        result = service.submit_work_status(
            tech_name=request.tech_name,
            work_date=request.work_date,
            work_status=request.work_status,
            time_spent=request.time_spent,
            notes=request.notes,
            summary=request.summary,
            work_order_id=request.work_order_id,
            complete_flag=request.complete_flag,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting work status: {str(e)}")

# Endpoint: Get work status logs
@app.get("/work-status-logs/{work_order_id}", response_model=WorkStatusLogs)
async def get_work_status_logs(work_order_id: str):
    try:
        result = service.get_work_status_logs(work_order_id)
        return WorkStatusLogs(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work status logs: {str(e)}")

# Endpoint: Submit conversation table to CSV database
@app.post("/submit-chat")
async def submit_chat(request: ChatSubmissionRequest):
    try:
        response = service.save_conversation(
            request.conversation_tech_ai_client_table,
            request.work_order_id,
            request.work_status,
        )
        if response:
            return {"success": True, "message": "Conversation saved successfully."}
        else:
            raise HTTPException(status_code=500, detail="Failed to save conversation.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint 4: Convert completion notes to CAR format
@app.post("/convert-to-car", response_model=CARFormatResponse)
async def convert_completion_notes_to_car(request: CompletionNotesRequest):
    """Convert completion notes to CAR format"""
    try:
        result = service.convert_to_car_format(
            completion_notes=request.completion_notes,
            work_order_description=request.work_order_description,
            wo_status_and_notes_table=request.wo_status_and_notes_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting to CAR format: {str(e)}")

# Endpoint 5: Convert conversation to client summary
@app.post("/convert-to-client-summary", response_model=ClientSummaryResponse)
async def convert_conversation_to_summary(request: ClientSummaryRequest):
    """Convert conversation to client-friendly summary"""
    try:
        result = service.convert_to_client_summary(
            conversation_table=request.conversation_tech_ai_client_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting to client summary: {str(e)}")

# Endpoint 6: Get all technicians
@app.get("/technicians")
async def get_technicians():
    """Get all technicians"""
    try:
        technicians = service.get_technicians()
        return {"technicians": technicians}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading technicians: {str(e)}")

# Endpoint 7: Get work status types
@app.get("/work-status-types")
async def get_work_status_types():
    """Get all work status types"""
    try:
        status_types = service.get_work_status_types()
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
    try:
        return service.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Get config values
    api_config = config['api']
    
    print(f"🚀 Starting Field Services Agent API on {api_config['host']}:{api_config['port']}")
    print(f"🔧 Debug mode: {api_config['debug']}")
    print(f"💾 Database: CSV files")
    
    uvicorn.run(
        "main:app",
        host=api_config['host'],
        port=api_config['port'],
        reload=api_config['debug'],
        log_level="info"
    )
