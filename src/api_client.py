"""
API Client Module
Handles HTTP requests to the Field Services Agent FastAPI backend
"""

import requests
import yaml
import streamlit as st
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd

class FieldServicesAPIClient:
    """Client for interacting with Field Services Agent API"""
    
    def __init__(self, base_url: str = None):
        """
        Initialize API client
        
        Args:
            base_url: Base URL of the API (e.g., "http://localhost:8000")
        """
        if base_url is None:
            # Load from config
            try:
                with open("config.yaml", 'r') as file:
                    config = yaml.safe_load(file)
                    host = config['api']['host']
                    port = config['api']['port']
                    # Handle localhost specifically
                    if host == "0.0.0.0":
                        host = "localhost"
                    self.base_url = f"http://{host}:{port}"
            except Exception as e:
                st.warning(f"Could not load config: {e}. Using default API URL.")
                self.base_url = "http://localhost:8000"
        else:
            self.base_url = base_url
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """
        Make HTTP request to API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data for POST requests
            params: URL parameters for GET requests
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Could not connect to API at {self.base_url}. Make sure the API server is running.")
            return None
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. The API server may be overloaded.")
            return None
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ API request failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            return None
    
    def health_check(self) -> bool:
        """
        Check if API is healthy
        
        Returns:
            True if API is responsive, False otherwise
        """
        result = self._make_request("GET", "/health")
        return result is not None and result.get("status") == "healthy"
    
    def get_work_orders(self, tech_name: str, work_date: str) -> Optional[Dict]:
        """
        Get work orders for a technician on a specific date
        
        Args:
            tech_name: Technician name
            work_date: Work date in YYYY-MM-DD format
            
        Returns:
            Work orders response or None if failed
        """
        # URL encode the tech name to handle spaces
        import urllib.parse
        encoded_tech_name = urllib.parse.quote(tech_name)
        endpoint = f"/work-orders/{encoded_tech_name}/{work_date}"
        return self._make_request("GET", endpoint)
    
    def get_all_work_orders(self, tech_name: str) -> Optional[Dict]:
        """
        Get all work orders for a technician regardless of date
        
        Args:
            tech_name: Technician name
            
        Returns:
            Work orders response or None if failed
        """
        # URL encode the tech name to handle spaces
        import urllib.parse
        encoded_tech_name = urllib.parse.quote(tech_name)
        endpoint = f"/work-orders/{encoded_tech_name}"
        return self._make_request("GET", endpoint)
    
    def validate_work_status(self, operational_log: str, work_status: str, 
                           work_order_description: str, tech_name: str, 
                           work_date: str, follow_up_questions_answers: str = "") -> Optional[Dict]:
        """
        Validate work status log
        
        Args:
            operational_log: Operational log text
            work_status: Work status type
            work_order_description: Work order description
            tech_name: Technician name
            work_date: Work date
            follow_up_questions_answers: Previous Q&A table
            
        Returns:
            Validation response or None if failed
        """
        data = {
            "operational_log": operational_log,
            "work_status": work_status,
            "work_order_description": work_order_description,
            "tech_name": tech_name,
            "work_date": work_date,
            "follow_up_questions_answers_table": follow_up_questions_answers
        }
        return self._make_request("POST", "/validate-work-status", data)
    
    def submit_work_status(self, tech_name: str, work_date: str, work_status: str,
                          time_spent: float, notes: str, summary: str, 
                          work_order_id: str = None) -> Optional[Dict]:
        """
        Submit work status details
        
        Args:
            tech_name: Technician name
            work_date: Work date
            work_status: Work status type
            time_spent: Time spent in hours
            notes: Work notes
            summary: Work summary
            work_order_id: Work order ID (optional)
            
        Returns:
            Submission response or None if failed
        """
        data = {
            "tech_name": tech_name,
            "work_date": work_date,
            "work_status": work_status,
            "time_spent": time_spent,
            "notes": notes,
            "summary": summary,
            "work_order_id": work_order_id
        }
        return self._make_request("POST", "/submit-work-status", data)
    
    def convert_to_car(self, completion_notes: str, work_order_description: str,
                      wo_status_and_notes_table: str) -> Optional[Dict]:
        """
        Convert completion notes to CAR format
        
        Args:
            completion_notes: Completion notes text
            work_order_description: Work order description
            wo_status_and_notes_table: Work status and notes table
            
        Returns:
            CAR format response or None if failed
        """
        data = {
            "completion_notes": completion_notes,
            "work_order_description": work_order_description,
            "wo_status_and_notes_table": wo_status_and_notes_table
        }
        return self._make_request("POST", "/convert-to-car", data)
    
    def convert_to_client_summary(self, conversation_table: str) -> Optional[Dict]:
        """
        Convert conversation to client summary
        
        Args:
            conversation_table: Conversation between tech, AI, and client
            
        Returns:
            Client summary response or None if failed
        """
        data = {
            "conversation_tech_ai_client_table": conversation_table
        }
        return self._make_request("POST", "/convert-to-client-summary", data)
    
    def get_technicians(self) -> Optional[List[Dict]]:
        """
        Get all technicians
        
        Returns:
            List of technicians or None if failed
        """
        result = self._make_request("GET", "/technicians")
        return result.get("technicians") if result else None
    
    def get_work_status_types(self) -> Optional[List[Dict]]:
        """
        Get all work status types
        
        Returns:
            List of work status types or None if failed
        """
        result = self._make_request("GET", "/work-status-types")
        return result.get("work_status_types") if result else None
    
    def get_config(self) -> Optional[Dict]:
        """
        Get API configuration
        
        Returns:
            Configuration dictionary or None if failed
        """
        return self._make_request("GET", "/config")

    def validate_reason_for_hold(self, hold_reason: str, work_order_type: str, 
                               work_order_description: str, wo_status_and_notes_with_hours_table: str, 
                               follow_up_questions_answers_table: str) -> Optional[Dict]:
        """
        Validate hold reason
        
        Args:
            hold_reason: The hold reason to validate
            work_order_type: Work order type
            work_order_description: Work order description
            wo_status_and_notes_with_hours_table: Table of work status and notes with hours
            follow_up_questions_answers_table: Previous follow-up questions and answers
            
        Returns:
            Validation response or None if failed
        """
        data = {
            "hold_reason": hold_reason,
            "work_order_type": work_order_type,
            "work_order_description": work_order_description,
            "wo_status_and_notes_with_hours_table": wo_status_and_notes_with_hours_table,
            "follow_up_questions_answers_table": follow_up_questions_answers_table
        }
        return self._make_request("POST", "/validate-reason-for-hold", data)

# Global API client instance
@st.cache_resource
def get_api_client() -> FieldServicesAPIClient:
    """
    Get cached API client instance
    
    Returns:
        FieldServicesAPIClient instance
    """
    return FieldServicesAPIClient()
