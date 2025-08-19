# Field Services Agent API

A FastAPI-based REST API for managing solar work orders and field services operations.

## Features

- 🔍 **Work Order Management**: Extract work orders assigned to technicians on specific dates
- ✅ **Work Status Validation**: Validate operational logs against work status requirements
- 💾 **CSV Database Storage**: Store work status details in CSV files
- 📝 **CAR Format Conversion**: Convert completion notes to Cause-Action-Result format
- 📋 **Client Summary**: Generate client-friendly summaries from technical conversations
- 👷 **Technician Management**: Manage 5 technicians with specialized skills
- 📊 **Work Status Types**: 6 predefined work status types with requirements

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

### 3. Run the API

```bash
python main.py
```

The API will start on `http://localhost:8000`

### 4. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Get Work Orders
**GET** `/work-orders/{tech_name}/{work_date}`

Extract work orders assigned to a technician on a specific date.

**Parameters:**
- `tech_name`: Technician name (e.g., "John Smith", "Sarah Johnson")
- `work_date`: Date in YYYY-MM-DD format

**Example:**
```bash
curl "http://localhost:8000/work-orders/John%20Smith/2024-01-15"
```

**Response:**
```json
{
  "work_orders": [
    {
      "id": "1",
      "work_order_id": "WO-001",
      "description": "Inverter replacement at Solar Site A",
      "wo_type": "Corrective",
      "time_type": "Work",
      "status": "Pending",
      "work_date": "2024-01-15",
      "tech_name": "John Smith"
    }
  ],
  "total_pending": 1,
  "total_completed": 0
}
```

### 2. Validate Work Status Log
**POST** `/validate-work-status`

Validate operational log against work status requirements.

**Request Body:**
```json
{
  "operational_log": "Replaced faulty inverter module and tested system functionality",
  "work_status": "Work",
  "work_order_description": "Inverter replacement at solar site",
  "tech_name": "John Smith",
  "work_date": "2024-01-15",
  "follow_up_questions_answers_table": "Q: What was the fault code? | A: E001\nQ: Was the system tested? | A: Yes, fully operational"
}
```

**Response:**
```json
{
  "valid": true,
  "missing": "",
  "follow_up_questions": []
}
```

### 3. Submit Work Status
**POST** `/submit-work-status`

Submit work status details to CSV database.

**Request Body:**
```json
{
  "tech_name": "John Smith",
  "work_date": "2024-01-15",
  "work_status": "Work",
  "time_spent": 4.5,
  "notes": "Completed inverter replacement and system testing",
  "summary": "Successfully replaced faulty inverter module",
  "work_order_id": "WO-001"
}
```

**Response:**
```json
{
  "message": "Work status submitted successfully",
  "log_id": 1,
  "tech_name": "John Smith",
  "work_date": "2024-01-15"
}
```

### 4. Convert to CAR Format
**POST** `/convert-to-car`

Convert completion notes to CAR (Cause, Action, Result) format.

**Request Body:**
```json
{
  "completion_notes": "Inverter was showing fault code E001. Replaced the faulty module and tested system. All systems now operational.",
  "work_order_description": "Inverter replacement at solar site",
  "wo_status_and_notes_table": "Work | Initial inspection and fault diagnosis\nWork | Module replacement\nWork | System testing and verification"
}
```

**Response:**
```json
{
  "cause": "Inverter was showing fault code E001",
  "action": "Replaced the faulty module and tested system",
  "result": "All systems now operational",
  "success": true,
  "error_message": null
}
```

### 5. Convert to Client Summary
**POST** `/convert-to-client-summary`

Convert technical conversation to client-friendly summary.

**Request Body:**
```json
{
  "conversation_tech_ai_client_table": "Tech | The inverter was showing a fault code. I've replaced the faulty module and tested the system. Everything is working now.\nClient | Great, thank you for the quick fix.\nAI | System status confirmed operational, all tests passed."
}
```

**Response:**
```json
{
  "summary": "Technician identified and resolved an inverter fault.\nSystem is now fully operational and tested.",
  "notes": "The field technician successfully diagnosed a technical issue with your solar system's inverter and completed the necessary repairs. All systems have been tested and are functioning properly. No further action is required from your end.",
  "success": true,
  "error_message": null
}
```

### 6. Get All Technicians
**GET** `/technicians`

Get list of all available technicians.

**Response:**
```json
{
  "technicians": [
    {
      "id": "1",
      "tech_name": "John Smith",
      "email": "john.smith@solartech.com",
      "phone": "+1-555-0101",
      "specialization": "Solar Inverter Specialist",
      "hire_date": "2023-01-15",
      "status": "Active"
    }
  ]
}
```

### 7. Get Work Status Types
**GET** `/work-status-types`

Get all available work status types and their requirements.

**Response:**
```json
{
  "work_status_types": [
    {
      "id": "1",
      "status_type": "Troubleshooting",
      "description": "Initial problem diagnosis and investigation",
      "requirements": "Problem identification, Initial assessment, Safety check"
    }
  ]
}
```

### 8. Health Check
**GET** `/health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

### 9. Get Configuration
**GET** `/config`

Get current API configuration (excluding sensitive data).

**Response:**
```json
{
  "defaults": {
    "tech_name": "John Smith",
    "date": "2024-01-15"
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": true
  },
  "database": {
    "type": "csv"
  },
  "openai": {
    "model": "gpt-4o"
  }
}
```

## Configuration

The API configuration is stored in `config.yaml`:

```yaml
# Default settings
defaults:
  tech_name: "John Smith"
  date: "2024-01-15"

# API settings
api:
  host: "0.0.0.0"
  port: 8000
  debug: true

# Database settings (using CSV files)
database:
  type: "csv"
  files:
    work_orders: "Database/work_orders.csv"
    work_status_logs: "Database/work_status_logs.csv"
    completion_notes: "Database/completion_notes.csv"
    technicians: "Database/technicians.csv"
    work_status_types: "Database/work_status_types.csv"

# OpenAI settings
openai:
  model: "gpt-4o"
  max_tokens: 600
  temperature: 0.3
```

## Database Schema

### CSV File Structure

The API uses CSV files stored in the `Database/` folder:

#### work_orders.csv
Contains 25 work orders distributed across 5 technicians.

**Columns:**
- `id`: Unique identifier
- `work_order_id`: Work order ID (e.g., WO-001)
- `tech_name`: Technician full name
- `work_date`: Date in YYYY-MM-DD format
- `status`: Work order status (Pending, Completed, Assigned)
- `description`: Work order description
- `wo_type`: Work order type (Corrective, Preventive, Project, Ad Hoc)
- `time_type`: Time type (Work, Training, etc.)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

#### work_status_logs.csv
Initially empty - populated by users through API submissions.

**Columns:**
- `id`: Unique identifier (auto-generated)
- `tech_name`: Technician name
- `work_date`: Work date
- `work_status`: Status type
- `time_spent`: Time spent in hours
- `notes`: Work notes
- `summary`: Work summary
- `work_order_id`: Associated work order ID (optional)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

#### technicians.csv
Contains 5 technicians with specializations.

**Columns:**
- `id`: Unique identifier
- `tech_name`: Full name
- `email`: Email address
- `phone`: Phone number
- `specialization`: Area of expertise
- `hire_date`: Date hired
- `status`: Employment status
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

#### work_status_types.csv
Defines 6 valid work status types and requirements.

**Columns:**
- `id`: Unique identifier
- `status_type`: Status type name
- `description`: Description of the status type
- `requirements`: Required information for this status
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Data Overview

### Technicians (5 total)
1. **John Smith** - Solar Inverter Specialist
2. **Sarah Johnson** - Panel Installation Expert
3. **Michael Chen** - Electrical Systems Engineer
4. **Emily Davis** - Monitoring Systems Specialist
5. **David Wilson** - Preventive Maintenance Expert

### Work Orders (25 total)
- **5 work orders per technician**
- **Status Distribution**: 15 Pending, 5 Completed, 5 Assigned
- **Type Distribution**: 10 Preventive, 5 Corrective, 5 Project, 5 Ad Hoc

### Work Status Types (6 total)
1. **Troubleshooting** - Initial problem diagnosis
2. **Work** - Active work being performed
3. **Warranty_Support** - Warranty-related work
4. **Delay** - Work delayed for various reasons
5. **Training** - Training and development activities
6. **Others** - Miscellaneous activities

## Testing

### Test CSV Database
```bash
python test_csv_api.py
```

This validates:
- CSV file existence and structure
- Data integrity and distribution
- Schema compliance

### Test API Endpoints
```bash
# Install dependencies first
pip install -r requirements.txt

# Start API and test endpoints
python main.py
```

## Error Handling

The API includes comprehensive error handling:

- **400 Bad Request**: Invalid input data (e.g., wrong date format)
- **500 Internal Server Error**: Server-side errors (e.g., CSV file issues, OpenAI API errors)

All errors return detailed error messages to help with debugging.

## Dependencies

- **FastAPI**: Modern, fast web framework for building APIs
- **Uvicorn**: ASGI server for running FastAPI applications
- **Pandas**: Data manipulation and analysis
- **OpenAI**: AI-powered text processing
- **PyYAML**: Configuration file parsing
- **CSV**: Built-in CSV handling

## Development

### Adding New Endpoints

1. Define Pydantic models for request/response
2. Create the endpoint function with proper error handling
3. Add to the FastAPI app
4. Update tests and documentation

### Database Changes

1. Modify CSV files in `Database/` folder
2. Update CSV utility functions in `main.py`
3. Update related endpoints

### Adding New Data

1. **Work Orders**: Add rows to `Database/work_orders.csv`
2. **Technicians**: Add rows to `Database/technicians.csv`
3. **Status Types**: Add rows to `Database/work_status_types.csv`

## Support

For issues or questions:
1. Check the API logs for error details
2. Verify configuration in `config.yaml`
3. Ensure all dependencies are installed
4. Check OpenAI API key configuration
5. Verify CSV files exist in `Database/` folder

## License

This project is part of the Field Services Agent application.
