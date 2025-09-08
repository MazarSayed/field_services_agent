"""
Data Access Layer
Shared utilities for CSV file operations and data management
"""

import csv
import os
import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
import openai


class DataAccessLayer:
    """Centralized data access for CSV operations"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize with configuration"""
        # Load environment variables from .env file
        load_dotenv()
        
        self.config = self._load_config(config_path)
        self.csv_files = {
            'work_orders': 'Database/work_orders.csv',
            'work_status_logs': 'Database/work_status_logs.csv',
            'completion_notes': 'Database/completion_notes.csv',
            'technicians': 'Database/technicians.csv',
            'work_status_types': 'Database/work_status_types.csv',
            'status_log_chat': 'Database/status_log_chat.csv',
            'hold_notes': 'Database/hold_notes.csv'
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"{config_path} not found")
        
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)
    
    def read_csv_file(self, filename: str) -> List[Dict[str, Any]]:
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
    
    def write_csv_file(self, filename: str, data: List[Dict[str, Any]], fieldnames: List[str]) -> bool:
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
    
    def append_to_csv_file(self, filename: str, data: Dict[str, Any], fieldnames: List[str]) -> bool:
        """Append single row to CSV file"""
        try:
            # Read existing data
            existing_data = self.read_csv_file(filename)
            
            # Add new row
            existing_data.append(data)
            
            # Write back to file
            return self.write_csv_file(filename, existing_data, fieldnames)
        except Exception as e:
            print(f"Error appending to {filename}: {e}")
            return False
    
    def get_next_id(self, filename: str) -> int:
        """Get next available ID for CSV file"""
        try:
            data = self.read_csv_file(filename)
            if not data:
                return 1
            
            # Find the highest ID
            ids = [int(row.get('id', 0)) for row in data if row.get('id')]
            return max(ids) + 1 if ids else 1
        except Exception as e:
            print(f"Error getting next ID for {filename}: {e}")
            return 1
    
    # Specific data loading methods
    def load_work_orders(self) -> List[Dict[str, Any]]:
        """Load work orders from CSV"""
        return self.read_csv_file(self.csv_files['work_orders'])
    
    def load_completion_notes(self) -> List[Dict[str, Any]]:
        """Load completion notes from CSV"""
        return self.read_csv_file(self.csv_files['completion_notes'])
    
    def load_technicians(self) -> List[Dict[str, Any]]:
        """Load technicians from CSV"""
        return self.read_csv_file(self.csv_files['technicians'])
    
    def load_work_status_types(self) -> List[Dict[str, Any]]:
        """Load work status types from CSV"""
        return self.read_csv_file(self.csv_files['work_status_types'])
    
    def load_work_status_logs(self) -> List[Dict[str, Any]]:
        """Load work status logs from CSV"""
        return self.read_csv_file(self.csv_files['work_status_logs'])
    
    def load_hold_notes(self) -> List[Dict[str, Any]]:
        """Load hold notes from CSV"""
        return self.read_csv_file(self.csv_files['hold_notes'])
    
    def get_openai_client(self):
        """Get OpenAI client instance"""
        print("Getting OpenAI client")
        api_key = os.getenv("OPENAI_API_KEY")
        print(f"DEBUG: API key found: {'Yes' if api_key else 'No'}")
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        try:
            return openai.OpenAI(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Error initializing OpenAI client: {str(e)}")

    def get_work_order_by_id(self, work_order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single work order by its work_order_id."""
        work_orders = self.load_work_orders()
        for row in work_orders:
            if str(row.get("work_order_id")) == str(work_order_id):
                return row
        return None
    
    def update_work_order(self, updated_work_order: dict) -> bool:
        """Update an existing work order in the CSV by work_order_id"""
        filename = self.csv_files['work_orders']
        data = self.read_csv_file(filename)
        updated = False

        for i, row in enumerate(data):
            if row.get("work_order_id") == updated_work_order.get("work_order_id"):
                data[i] = updated_work_order
                updated = True
                break

        if updated:
            fieldnames = data[0].keys() if data else updated_work_order.keys()
            return self.write_csv_file(filename, data, fieldnames)
        return False


# Global instance
_data_access_instance = None

def get_data_access() -> DataAccessLayer:
    """Get global data access instance"""
    global _data_access_instance
    if _data_access_instance is None:
        _data_access_instance = DataAccessLayer()
    return _data_access_instance
