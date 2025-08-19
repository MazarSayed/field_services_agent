# Database Schema Documentation

This folder contains CSV files that serve as the database for the Field Services Agent API.

## File Structure

```
Database/
├── work_orders.csv         # Main work orders data
├── work_status_logs.csv    # User-submitted work status logs (initially empty)
├── completion_notes.csv    # Completion notes for work orders (initially empty)
├── technicians.csv         # Technician information
├── work_status_types.csv   # Valid work status types and requirements
└── README.md              # This documentation file
```

## CSV File Schemas

### work_orders.csv
Contains work orders assigned to technicians with mock data for 5 technicians (5 work orders each).

**Columns:**
- `id`: Unique identifier (integer)
- `work_order_id`: Work order ID (e.g., WO-001)
- `tech_name`: Technician full name
- `work_date`: Date in YYYY-MM-DD format
- `status`: Work order status (Pending, Completed, Assigned)
- `description`: Work order description
- `wo_type`: Work order type (Corrective, Preventive, Project, Ad Hoc)
- `time_type`: Time type (Work, Training, etc.)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

**Data Distribution:**
- 5 technicians: John Smith, Sarah Johnson, Michael Chen, Emily Davis, David Wilson
- 25 total work orders (5 per technician)
- Status: 15 Pending, 5 Completed, 5 Assigned
- Types: 10 Preventive, 5 Corrective, 5 Project, 5 Ad Hoc

### work_status_logs.csv
Initially empty - populated by users through the API when submitting work status updates.

**Columns:**
- `id`: Unique identifier (auto-generated)
- `tech_name`: Technician name
- `work_date`: Work date
- `work_status`: Status type (from work_status_types.csv)
- `time_spent`: Time spent in hours (float)
- `notes`: Work notes
- `summary`: Work summary
- `work_order_id`: Associated work order ID (optional)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### completion_notes.csv
Initially empty - can be populated with completion notes from completed work orders.

**Columns:**
- `id`: Unique identifier
- `completion_notes`: Detailed completion notes
- `wo_type`: Work order type
- `time_type`: Time type
- `work_order_id`: Associated work order ID
- `tech_name`: Technician name
- `work_date`: Work date
- `created_at`: Creation timestamp

### technicians.csv
Contains information about the 5 technicians.

**Columns:**
- `id`: Unique identifier
- `tech_name`: Full name
- `email`: Email address
- `phone`: Phone number
- `specialization`: Area of expertise
- `hire_date`: Date hired
- `status`: Employment status (Active)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

**Technician List:**
1. John Smith - Solar Inverter Specialist
2. Sarah Johnson - Panel Installation Expert
3. Michael Chen - Electrical Systems Engineer
4. Emily Davis - Monitoring Systems Specialist
5. David Wilson - Preventive Maintenance Expert

### work_status_types.csv
Defines valid work status types and their requirements.

**Columns:**
- `id`: Unique identifier
- `status_type`: Status type name
- `description`: Description of the status type
- `requirements`: Required information for this status
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

**Status Types:**
1. Troubleshooting - Initial problem diagnosis
2. Work - Active work being performed
3. Warranty_Support - Warranty-related work
4. Delay - Work delayed for various reasons
5. Training - Training and development activities
6. Others - Miscellaneous activities

## API Usage

The CSV files are accessed through the Field Services Agent API endpoints:

- **GET** `/work-orders/{tech_name}/{work_date}` - Reads from work_orders.csv
- **POST** `/submit-work-status` - Writes to work_status_logs.csv
- **GET** `/technicians` - Reads from technicians.csv
- **GET** `/work-status-types` - Reads from work_status_types.csv

## Data Management

### Adding New Data
- Work orders: Add rows to work_orders.csv
- Technicians: Add rows to technicians.csv
- Status types: Add rows to work_status_types.csv

### User-Generated Data
- work_status_logs.csv is populated through API submissions
- completion_notes.csv can be populated as work orders are completed

### Data Integrity
- Ensure unique IDs across all records
- Use consistent date formats (YYYY-MM-DD)
- Maintain referential integrity between work_order_id fields

## Testing

Run the test script to verify CSV file integrity:

```bash
python test_csv_api.py
```

This will validate:
- File existence and readability
- Data structure and distribution
- Schema compliance
