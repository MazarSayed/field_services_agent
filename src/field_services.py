"""
Field Services Business Logic
Simplified service layer for handling field services operations
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from src.data_access import get_data_access
from src.ai_classifier import validate_work_status_log, convert_to_car_format, convert_to_client_summary
import json


class FieldServicesService:
    """Service layer for field services operations"""
    
    def __init__(self):
        self.data_access = get_data_access()
    
    def get_work_orders_for_tech(self, tech_name: str, work_date: str) -> Dict[str, Any]:
        """Get work orders for a technician on a specific date"""
        # Parse date to validate format
        try:
            datetime.strptime(work_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        
        # Load work orders
        work_orders_data = self.data_access.load_work_orders()
        
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
    
    def get_all_work_orders_for_tech(self, tech_name: str) -> Dict[str, Any]:
        """Get all work orders for a technician regardless of date"""
        # Load work orders
        work_orders_data = self.data_access.load_work_orders()
        
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
    
    def update_work_order_status(self, work_order_id: str, new_status: str) -> bool:
        """
        Update the status of a work order in CSV.
        Returns True if updated, False if work order not found.
        """
        work_order = self.data_access.get_work_order_by_id(work_order_id)
        if not work_order:
            return False
        
        # Update the dictionary keys
        work_order['status'] = new_status
        work_order['updated_at'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save back to CSV
        self.data_access.update_work_order(work_order)
        return True

    def validate_work_status(self, operational_log: str, work_status: dict, 
                           work_order_description: str, tech_name: str, 
                           work_date: str, follow_up_questions_answers: str = "") -> Dict[str, Any]:
        """Validate work status log using AI"""
        openai_client = self.data_access.get_openai_client()
        
        return validate_work_status_log(
            operational_log=operational_log,
            work_status=work_status,
            work_order_description=work_order_description,
            follow_up_questions_answers_table=follow_up_questions_answers
        )
    
    def submit_work_status(self, tech_name: str, work_date: str, work_status: dict, start_time: str, end_time: str,
                          time_spent: float, notes: str, summary: str, 
                          work_order_id: str = None, complete_flag: bool = False) -> Dict[str, Any]:
        """Submit work status to database"""
        # Validate date format
        try:
            datetime.strptime(work_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        
        # Get next ID
        next_id = self.data_access.get_next_id(self.data_access.csv_files['work_status_logs'])
        
        # Prepare data
        work_status_data = {
            'id': next_id,
            'tech_name': tech_name,
            'work_date': work_date,
            'work_status': work_status,
            'start_time': start_time,
            'end_time': end_time,
            'time_spent': time_spent,
            'notes': notes,
            'summary': summary,
            'work_order_id': work_order_id or '',
            'complete_flag': complete_flag,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Define fieldnames
        fieldnames = [
            'id', 'tech_name', 'work_date', 'work_status', 'start_time', 'end_time', 'time_spent',
            'notes', 'summary', 'work_order_id', 'complete_flag', 'created_at', 'updated_at'
        ]
        
        # Save to database
        success = self.data_access.append_to_csv_file(
            self.data_access.csv_files['work_status_logs'], 
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
    
    def convert_to_car_format(self, completion_notes: str, work_order_description: str,
                            wo_status_and_notes_table: str) -> Dict[str, Any]:
        """Convert completion notes to CAR format"""
        openai_client = self.data_access.get_openai_client()
        
        return convert_to_car_format(
            openai_client=openai_client,
            completion_notes=completion_notes,
            wo_status_and_notes_table=wo_status_and_notes_table,
            work_order_description=work_order_description
        )
    
    def convert_to_client_summary(self, conversation_table: str) -> Dict[str, Any]:
        """Convert conversation to client summary"""
        
        return convert_to_client_summary(
            conversation_tech_ai_client_table=conversation_table
        )
    
    def get_work_status_logs(self, work_order_id: str) -> Dict[str, Any]:
        """Get work status logs for a specific work order"""
        work_status_logs = self.data_access.load_work_status_logs()
        
        if not work_status_logs:
            return {"work_status_logs": []}
        
        # Filter by technician and date
        filtered_status_logs = [
            log for log in work_status_logs
            if log.get('work_order_id') == work_order_id
        ]
        
        if not filtered_status_logs:
            return {"work_status_logs": []}
        
        return {
            "work_status_logs": filtered_status_logs
        }
    
    def get_technicians(self) -> List[Dict[str, Any]]:
        """Get all technicians"""
        return self.data_access.load_technicians()
    
    def get_work_status_types(self) -> List[Dict[str, Any]]:
        """Get all work status types"""
        return self.data_access.load_work_status_types()
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration"""
        return {
            "defaults": self.data_access.config.get("defaults", {}),
            "api": self.data_access.config.get("api", {}),
            "database": {"type": "csv"},
            "openai": {"model": self.data_access.config.get("openai", {}).get("model")}
        }


    def parse_conversation_table(self, conversation_str: str) -> dict:
        """Parse pipe-separated conversation string into dict, ignoring header row."""
        conversation_dict = {}
        lines = conversation_str.strip().split("\n")
        
        for i, line in enumerate(lines):
            if "|" in line:
                speaker, message = line.split("|", 1)
                speaker = speaker.strip()
                message = message.strip()
                
                # Skip the first line if it looks like a header (e.g., contains speaker names)
                if i == 0 and message.lower() in ["ai", "tech"]:
                    continue
                
                conversation_dict.setdefault(speaker, []).append(message)
        
        return conversation_dict

    
    def save_conversation(self, conversation_table: str, work_order_id: str, work_status: str) -> bool:
        conversation_dict = self.parse_conversation_table(conversation_table)

        chat_data = {
            "work_order_id": work_order_id,
            "conversation": json.dumps(conversation_dict), 
            "work_status": work_status,
        }
        
        fieldnames = ["work_order_id", "work_status", "conversation"]

        return self.data_access.append_to_csv_file(
            self.data_access.csv_files["status_log_chat"], 
            chat_data, 
            fieldnames
        )


# Global service instance
_service_instance = None

def get_field_services() -> FieldServicesService:
    """Get global field services instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = FieldServicesService()
    return _service_instance
