# Field Services Agent - Project Structure

## 📁 Directory Overview

```
field_services_agent/
├── 🗄️ Database/                    # CSV Database Files
│   ├── work_orders.csv             # 25 work orders (5 per technician)
│   ├── work_status_logs.csv        # User submissions (empty initially)
│   ├── completion_notes.csv        # Completion notes (empty initially)
│   ├── technicians.csv             # 5 technicians with specializations
│   ├── work_status_types.csv       # 6 valid status types
│   └── README.md                   # Database schema documentation
│
├── 🏗️ models/                      # Pydantic Models
│   └── models.py                   # API response models
│
├── 📝 prompts/                     # AI Prompts
│   └── prompts.yaml                # Prompt templates
│
├── 🌐 API Files
│   ├── main.py                     # FastAPI application with CSV integration
│   ├── ai_classifier.py            # AI processing functions
│   ├── config.yaml                 # Configuration settings
│   └── requirements.txt            # Python dependencies
│
├── 📚 Documentation
│   ├── API_README.md              # API documentation
│   ├── PROJECT_STRUCTURE.md       # This file
│   └── README.md                  # Main project README
│
├── 🛠️ Legacy/Support Files
│   ├── app.py                     # Original Streamlit app
│   ├── data_manager.py            # Data management utilities
│   ├── utils.py                   # Utility functions
│
└── 📊 Data Files
    ├── Cutlass_time_entry.xlsx    # Original Excel data
    ├── solar_work_orders_data.xlsx # Solar work orders
    └── time_entry_analysis.ipynb  # Jupyter analysis
```

## 🚀 Quick Start

### 1. Setup Environment
```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-key-here"
```

### 2. Test Database
```bash
python test_csv_api.py
```

### 3. Start API
```bash
python main.py
```

### 4. Access API
- **API Base**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## 🎯 Key Features

### 📋 Work Order Management
- 5 technicians with specialized skills
- 25 work orders across different types
- Real-time status tracking

### 🤖 AI-Powered Processing
- Work status validation
- **Hold reason validation with detailed analysis**
- CAR format conversion
- Client-friendly summaries
- Audio transcription support

### 💾 CSV Database
- Lightweight file-based storage
- Easy data management
- Full CRUD operations via API
- Structured schema with documentation

### 🔧 API Endpoints
- `GET /work-orders/{tech}/{date}` - Extract work orders
- `POST /validate-work-status` - Validate work logs
- `POST /submit-work-status` - Submit work status
- `POST /convert-to-car` - Convert to CAR format
- `POST /convert-to-client-summary` - Client summaries
- `GET /technicians` - List technicians
- `GET /work-status-types` - List status types

## 📊 Database Schema

### Technicians (5 records)
| Name | Specialization |
|------|---------------|
| John Smith | Solar Inverter Specialist |
| Sarah Johnson | Panel Installation Expert |
| Michael Chen | Electrical Systems Engineer |
| Emily Davis | Monitoring Systems Specialist |
| David Wilson | Preventive Maintenance Expert |

### Work Orders (25 records)
| Type | Count | Description |
|------|-------|-------------|
| Preventive | 10 | Routine maintenance |
| Corrective | 5 | Repair work |
| Project | 5 | New installations |
| Ad Hoc | 5 | Emergency responses |

### Status Types (6 types)
- Troubleshooting
- Work
- Warranty_Support
- Delay
- Training
- Others

## 🧪 Testing

### CSV Database Tests
```bash
python test_csv_api.py
```
Validates:
- ✅ File existence and structure
- ✅ Data integrity and distribution
- ✅ Schema compliance

### API Tests
```bash
# Install API dependencies first
pip install fastapi uvicorn[standard]

# Start API and test endpoints
python main.py
```

## 📝 Configuration

The `config.yaml` file contains:
- Default technician and date settings
- API host/port configuration
- Database file paths
- OpenAI model settings

## 🔄 Data Flow

1. **Work Orders** → Retrieved from `Database/work_orders.csv`
2. **Status Validation** → AI validates against requirements
3. **Status Submission** → Appended to `Database/work_status_logs.csv`
4. **CAR Conversion** → AI converts notes to structured format
5. **Client Summary** → AI generates client-friendly summaries

## 🚀 Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Set OpenAI API key: `export OPENAI_API_KEY="your-key"`
3. Test database: `python test_csv_api.py`
4. Start API: `python main.py`
5. Access docs: http://localhost:8000/docs

Happy coding! 🎉
