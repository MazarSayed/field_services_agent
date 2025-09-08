"""
Field Services Agent API
FastAPI application for managing solar work orders and field services
"""

from datetime import datetime, date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json

# Import models and AI functions directly
from models.models import (
    WorkOrderResponse, WorkStatusValidationRequest, WorkStatusValidationResponse, CARFormatResponse, 
    ClientSummaryResponse, WorkStatusLogRequest, WorkStatusSubmissionRequest,
    CompletionNotesRequest, ClientSummaryRequest, WorkStatusLogs, WorkOrderUpdateResponse, 
    ChatSubmissionRequest, HoldReasonValidationRequest, HoldReasonValidationResponse, HoldNotesSubmissionRequest, HoldNotes
)
from src.ai_classifier import validate_work_status_log, validate_reason_for_hold, convert_to_car_format, convert_to_client_summary
from src.data_access import get_data_access

# Initialize data access layer
data_access = get_data_access()
config = data_access.config

# Helper functions for data access
def get_work_orders_for_tech(tech_name: str, work_date: str):
    """Get work orders for a technician on a specific date"""
    work_orders_data = data_access.load_work_orders()
    
    if not work_orders_data:
        return {"work_orders": [], "total_pending": 0, "total_completed": 0}
    
    # Filter by technician and date
    filtered_orders = [
        order for order in work_orders_data
        if order.get('tech_name') == tech_name and order.get('work_date') == work_date
    ]
    
    if not filtered_orders:
        return {"work_orders": [], "total_pending": 0, "total_completed": 0}
    
    # Count pending and completed
    pending_statuses = ['pending', 'open', 'assigned']
    completed_statuses = ['completed', 'closed', 'finished']
    
    total_pending = len([wo for wo in filtered_orders 
                       if wo.get('status', '').lower() in pending_statuses])
    total_completed = len([wo for wo in filtered_orders 
                          if wo.get('status', '').lower() in completed_statuses])
    
    return {
        "work_orders": filtered_orders,
        "total_pending": total_pending,
        "total_completed": total_completed
    }

def get_all_work_orders_for_tech(tech_name: str):
    """Get all work orders for a technician regardless of date"""
    work_orders_data = data_access.load_work_orders()
    
    if not work_orders_data:
        return {"work_orders": [], "total_pending": 0, "total_completed": 0}
    
    # Filter by technician only (no date filter)
    filtered_orders = [
        order for order in work_orders_data
        if order.get('tech_name') == tech_name
    ]
    
    if not filtered_orders:
        return {"work_orders": [], "total_pending": 0, "total_completed": 0}
    
    # Count pending and completed
    pending_statuses = ['pending', 'open', 'assigned']
    completed_statuses = ['completed', 'closed', 'finished']
    
    total_pending = len([wo for wo in filtered_orders 
                       if wo.get('status', '').lower() in pending_statuses])
    total_completed = len([wo for wo in filtered_orders 
                          if wo.get('status', '').lower() in completed_statuses])
    
    return {
        "work_orders": filtered_orders,
        "total_pending": total_pending,
        "total_completed": total_completed
    }

def update_work_order_status(work_order_id: str, new_status: str):
    """Update the status of a work order in CSV"""
    work_order = data_access.get_work_order_by_id(work_order_id)
    if not work_order:
        return False
    
    # Update the dictionary keys
    work_order['status'] = new_status
    work_order['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save back to CSV
    data_access.update_work_order(work_order)
    return True

def get_existing_work_logs(work_order_id: str) -> str:
    """Get existing work status logs for a work order"""
    try:
        work_logs = data_access.load_work_status_logs()
        filtered_logs = [log for log in work_logs if log.get('work_order_id') == work_order_id]
        
        if not filtered_logs:
            return "No previous work logs found for this work order."
        
        # Format the logs as a table with correct column names
        log_table = "Tech Name | Time allocation | Notes | Summary\n"
        for log in filtered_logs:
            tech_name = log.get('tech_name', '')
            time_allocation = log.get('work_status', '')
            notes = log.get('notes', '')
            summary = log.get('summary', '')
            log_table += f"{tech_name} | {time_allocation} | {notes} | {summary}\n"
        
        return log_table
    except Exception as e:
        print(f"Error fetching work logs: {e}")
        return "Error fetching previous work logs."

def get_first_user_input(messages: list[dict]) -> str:
    """Get the first user message from the conversation."""
    for message in messages:
        if message.get("role") == "user":
            return message.get("content", "")
    return ""

def get_conversation_history(messages: list[dict]) -> list[dict]:
    """Get all messages except the first user input."""
    if not messages or len(messages) <= 1:
        return []
    return messages[1:]  # Skip first message

def submit_work_status(tech_name: str, work_date: str, work_status: dict, plant: str, start_time: str, end_time: str,
                      time_spent: float, notes: str, summary: str, 
                      work_order_id: str = None, complete_flag: bool = False):
    """Submit work status to database"""
    # Validate date format
    try:
        datetime.strptime(work_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")
    
    # Get next ID
    next_id = data_access.get_next_id(data_access.csv_files['work_status_logs'])
    
    # Prepare data - match current database schema
    work_status_data = {
        'id': next_id,
        'tech_name': tech_name,
        'work_date': work_date,
        'work_status': work_status,
        'time_spent': time_spent,
        'notes': notes,
        'summary': summary,
        'work_order_id': work_order_id or '',
        'email': '',  # Not provided in API request
        'plant_description': plant,
        'day_name': '',  # Not provided in API request
        'operating_log_id': '',  # Not provided in API request
        'car_flag': '',  # Not provided in API request
        'is_weekend': '',  # Not provided in API request
        'wo_status': '',  # Not provided in API request
        'wo_type': '',  # Not provided in API request
        'user_resource': '',  # Not provided in API request
        'user_fsm_email': '',  # Not provided in API request
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    # Define fieldnames to match current database schema
    fieldnames = [
        'id', 'tech_name', 'work_date', 'work_status', 'time_spent', 'notes', 'summary', 
        'work_order_id', 'email', 'plant_description', 'day_name', 'operating_log_id', 
        'car_flag', 'is_weekend', 'wo_status', 'wo_type', 'user_resource', 'user_fsm_email', 
        'created_at', 'updated_at'
    ]
    
    # Save to database
    success = data_access.append_to_csv_file(
        data_access.csv_files['work_status_logs'], 
        work_status_data, 
        fieldnames
    )
    
    if not success:
        raise RuntimeError("Failed to save work status to database")
    
    return {
        "message": "Work status submitted successfully",
        "log_id": next_id,
        "tech_name": tech_name,
        "work_date": work_date
    }

def get_work_status_logs(work_order_id: str):
    """Get work status logs for a specific work order"""
    work_status_logs = data_access.load_work_status_logs()
    
    if not work_status_logs:
        return {"work_status_logs": []}
    
    # Filter by work order ID
    filtered_status_logs = [
        log for log in work_status_logs
        if log.get('work_order_id') == work_order_id
    ]
    
    if not filtered_status_logs:
        return {"work_status_logs": []}
    
    return {
        "work_status_logs": filtered_status_logs
    }

def get_all_work_status_logs(tech_name):
    work_status_logs = data_access.load_work_status_logs()
    
    if not work_status_logs:
        return {"work_status_logs": []}
    
    today = date.today()
    print("Today:", today)
    print("Looking for tech:", tech_name)

    filtered_status_logs = []
    for log in work_status_logs:
        print("Raw log:", log)  # always print to see what’s happening

        if log.get("tech_name") != tech_name:
            continue

        log_date_str = log.get("work_date")
        print("Found log date:", log_date_str)

        try:
            # support both YYYY-MM-DD and MM/DD/YYYY
            try:
                log_date = datetime.strptime(log_date_str, "%m/%d/%Y").date()
            except ValueError:
                log_date = datetime.strptime(log_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            print("Skipping invalid date:", log_date_str)
            continue 

        if log_date == today:
            filtered_status_logs.append(log)
            print("✅ Matched log:", log)
    
    return {"work_status_logs": filtered_status_logs}

def submit_hold_notes(hold_reason:str,hold_date:str,notes:str,summary:str,work_order_id:str):
    """Submit hold notes to database"""
    # Validate date format
    try:
        datetime.strptime(hold_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")
    
    # Get next ID
    next_id = data_access.get_next_id(data_access.csv_files['hold_notes'])
    
    # Prepare data - match current database schema
    hold_notes_data = {
        'id': next_id,
        'hold_reason':hold_reason,
        'hold_date':hold_date,
        'notes':notes,
        'summary':summary,
        'work_order_id':work_order_id,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    # Define fieldnames to match current database schema
    fieldnames = [
        'id', 'hold_reason', 'hold_date', 'notes', 'summary', 'work_order_id',
        'created_at', 'updated_at'
    ]
    
    # Save to database
    success = data_access.append_to_csv_file(
        data_access.csv_files['hold_notes'], 
        hold_notes_data, 
        fieldnames
    )
    
    if not success:
        raise RuntimeError("Failed to save hold notes to database")
    
    return {
        "message": "Hold notes submitted successfully",
        "log_id": next_id,
        "hold_date": hold_date
    }

def get_hold_notes(work_order_id: str):
    """Get hold notes for a specific work order"""
    hold_notes = data_access.load_hold_notes()
    
    if not hold_notes:
        return {"hold_notes": []}
    
    # Filter by work order ID
    filtered_hold_notes = [
        log for log in hold_notes
        if log.get('work_order_id') == work_order_id
    ]
    
    if not filtered_hold_notes:
        return {"hold_notes": []}
    
    return {
        "hold_notes": filtered_hold_notes
    }

def save_conversation(conversation_table: list[dict], work_order_id: str, work_status: str):
    """Save conversation to CSV database"""
    print(f"DEBUG: conversation_table: {conversation_table}")
    print(f"DEBUG: work_order_id: {work_order_id}")
    print(f"DEBUG: work_status: {work_status}")
    
    conversation_dict = parse_conversation_messages(conversation_table)
    print(f"DEBUG: conversation_dict: {conversation_dict}")
    
    chat_data = {
        "work_order_id": work_order_id,
        "conversation": json.dumps(conversation_dict), 
        "work_status": work_status,
    }
    
    print(f"DEBUG: chat_data: {chat_data}")
    
    fieldnames = ["work_order_id", "work_status", "conversation"]
    
    return data_access.append_to_csv_file(
        data_access.csv_files["status_log_chat"], 
        chat_data, 
        fieldnames
    )

def parse_conversation_messages(messages: list[dict]) -> dict:
    """Parse conversation messages list into dict"""
    conversation_dict = {}
    
    print(f"DEBUG: Parsing conversation with {len(messages)} messages")
    
    for i, message in enumerate(messages):
        role = message.get("role", "unknown")
        content = message.get("content", "")
        
        print(f"DEBUG: Message {i}: role={repr(role)}, content={repr(content)}")
        
        conversation_dict.setdefault(role, []).append(content)
    
    print(f"DEBUG: Final conversation_dict: {conversation_dict}")
    return conversation_dict

def parse_conversation_table(conversation_str: str) -> dict:
    """Parse pipe-separated conversation string into dict, ignoring header row"""
    conversation_dict = {}
    lines = conversation_str.strip().split("\n")
    
    print(f"DEBUG: Parsing conversation with {len(lines)} lines")
    
    for i, line in enumerate(lines):
        print(f"DEBUG: Line {i}: {repr(line)}")
        if "|" in line:
            speaker, message = line.split("|", 1)
            speaker = speaker.strip()
            message = message.strip()
            
            print(f"DEBUG: Speaker: {repr(speaker)}, Message: {repr(message)}")
            
            # Skip the first line if it looks like a header (e.g., contains speaker names)
            if i == 0 and message.lower() in ["ai", "tech"]:
                print("DEBUG: Skipping header line")
                continue
            
            conversation_dict.setdefault(speaker, []).append(message)
        else:
            print(f"DEBUG: Skipping line without pipe separator: {repr(line)}")
    
    print(f"DEBUG: Final conversation_dict: {conversation_dict}")
    return conversation_dict

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

# Endpoint 1: Extract work orders for a tech on a specific date
@app.get("/work-orders/{config[defaults][tech_name]}/{work_date}", response_model=WorkOrderResponse)
async def get_work_orders(tech_name: str, work_date: str):
    """Extract work orders assigned to a technician on a specific date"""
    try:
        result = get_work_orders_for_tech(tech_name, work_date)
        return WorkOrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work orders: {str(e)}")

# Endpoint 1b: Get all work orders for a technician (no date filter)
@app.get("/work-orders", response_model=WorkOrderResponse)
async def get_all_work_orders_tech():
    """Extract all work orders assigned to a technician regardless of date"""
    try:
        tech_name = config['defaults']['tech_name']
        # print(tech_name)
        result = get_all_work_orders_for_tech(tech_name)
        return WorkOrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work orders: {str(e)}")

@app.put("/work-orders/{work_order_id}/complete", response_model=WorkOrderUpdateResponse)
async def complete_work_order(work_order_id: str):
    """Update a work order's status to Completed"""
    try:
        updated = update_work_order_status(work_order_id, "Completed")
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
async def validate_work_status(request: WorkStatusValidationRequest):
    """Validate operational log against work status requirements"""
    try:
        # Fetch work order details from database
        work_order = data_access.get_work_order_by_id(request.work_order_id)
        if not work_order:
            raise HTTPException(status_code=404, detail=f"Work order {request.work_order_id} not found")
        
        # Extract tech name and plant from work order
        tech_name = work_order.get('tech_name', '')
        plant = work_order.get('plant', '')
        work_order_description = work_order.get('description', '')
        work_order_type = work_order.get('wo_type', '')
        
        # Get existing work logs for context
        existing_logs = get_existing_work_logs(request.work_order_id)
        
        # Extract operational log and follow-up conversation
        if request.follow_up_questions_answers_table and len(request.follow_up_questions_answers_table) > 0:
            operational_log = request.follow_up_questions_answers_table[0].get('content', '')
        else:
            operational_log = request.operational_log
        follow_up_conversation = request.follow_up_questions_answers_table
        
        result = validate_work_status_log(
            operational_log=operational_log,
            work_order_type=work_order_type,
            work_status=request.work_status,
            work_order_description=work_order_description,
            plant=plant,
            wo_status_and_notes_with_time_allocation_table=existing_logs,
            follow_up_questions_answers_table=follow_up_conversation
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating work status: {str(e)}")
    

# Endpoint 2b: Validate reason for hold
@app.post("/validate-reason-for-hold", response_model=HoldReasonValidationResponse)
async def validate_reason_hold(request: HoldReasonValidationRequest):
    """Validate hold reason against work order requirements"""
    try:
        result = validate_reason_for_hold(
            hold_reason=request.hold_reason,
            work_order_type=request.work_order_type,
            work_order_description=request.work_order_description,
            plant=request.plant,
            wo_status_and_notes_with_time_allocation_table=request.wo_status_and_notes_with_time_allocation_table,
            follow_up_questions_answers_table=request.follow_up_questions_answers_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating hold reason: {str(e)}")
    

@app.put("/work-orders/{work_order_id}/hold", response_model=WorkOrderUpdateResponse)
async def hold_work_order(work_order_id: str):
    """Update a work order's status to Hold"""
    try:
        updated = update_work_order_status(work_order_id, "On Hold")
        if not updated:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")
        
        return WorkOrderUpdateResponse(
            work_order_id=work_order_id,
            status="On Hold",
            message="Work order marked as on hold successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating work order: {str(e)}")


# Endpoint 3: Submit work status details to CSV database
@app.post("/submit-work-status")
async def submit_work_status_endpoint(request: WorkStatusSubmissionRequest):
    """Submit work status details to CSV database"""
    try:
        result = submit_work_status(
            tech_name=request.tech_name,
            work_date=request.work_date,
            work_status=request.work_status,
            plant=request.plant,
            start_time=request.start_time,
            end_time=request.end_time,
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
async def get_work_status_logs_endpoint(work_order_id: str):
    try:
        result = get_work_status_logs(work_order_id)
        return WorkStatusLogs(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work status logs: {str(e)}")
    
@app.get("/all-status-logs", response_model=WorkStatusLogs)
async def get_work_status_logs_all():
    try:
        tech_name = config['defaults']['tech_name']
        result = get_all_work_status_logs(tech_name)
        return WorkStatusLogs(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting work status logs: {str(e)}")


# Endpoint: Submit conversation table to CSV database
@app.post("/submit-chat")
async def submit_chat(request: ChatSubmissionRequest):
    try:
        response = save_conversation(
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
        result = convert_to_car_format(
            work_order_type="",  # Default empty string since not provided in current interface
            final_completion_notes=request.completion_notes,
            wo_status_and_notes_with_hours_table=request.wo_status_and_notes_table,
            work_order_description=request.work_order_description
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
        result = convert_to_client_summary(
            conversation_table=request.conversation_tech_ai_client_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting to client summary: {str(e)}")
    
@app.post("/save-hold-notes")
async def save_hold_notes(request: HoldNotesSubmissionRequest):
    """Submit work status details to CSV database"""
    try:
        result = submit_hold_notes(
            hold_reason=request.hold_reason,
            hold_date=request.hold_date,
            notes=request.notes,
            summary=request.summary,
            work_order_id=request.work_order_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting work status: {str(e)}")

@app.get("/hold-notes/{work_order_id}", response_model=HoldNotes)
async def get_work_status_logs_endpoint(work_order_id: str):
    try:
        result = get_hold_notes(work_order_id)
        return HoldNotes(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting hold notes: {str(e)}")
    

# Endpoint 6: Get all technicians
@app.get("/technicians")
async def get_technicians():
    """Get all technicians"""
    try:
        technicians = data_access.load_technicians()
        return {"technicians": technicians}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading technicians: {str(e)}")

# Endpoint 7: Get work status types
@app.get("/work-status-types")
async def get_work_status_types():
    """Get all work status types"""
    try:
        status_types = data_access.load_work_status_types()
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
        return {
            "defaults": config.get("defaults", {}),
            "api": config.get("api", {}),
            "database": {"type": "csv"},
            "openai": {"model": config.get("openai", {}).get("model")}
        }
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
