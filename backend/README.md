# AI Trace Explorer - Backend

Real-time LLM request tracing and monitoring backend API built with FastAPI.

## 📋 Quick Start

### 1. Setup Environment

```bash
# Clone/navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run Server

```bash
uvicorn main:app --reload
```

Server will start at: `http://localhost:8000`

Access API documentation at: `http://localhost:8000/docs`

### 3. Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py              # Environment configuration
│   ├── database.py            # SQLAlchemy setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py         # Request model
│   │   ├── trace.py           # Trace model
│   │   ├── evaluation.py      # Evaluation model
│   │   └── supported_model.py # Model registry
│   ├── stages/                # Will add pipeline stages here
│   │   └── __init__.py
│   └── api/                   # Will add API endpoints here
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_models.py         # Model tests
├── main.py                    # FastAPI app entry point
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

## 🗄️ Database

### Initialize Database

```bash
python -c "from app.database import init_db; init_db()"
```

This creates SQLite database at `./ai_trace.db` with all tables.

### Database Tables

- **requests** - Complete LLM requests
- **traces** - Individual pipeline stages
- **evaluations** - Quality metrics
- **supported_models** - Available LLM models

## 🔧 Configuration

Edit `.env` file to configure:

```
DATABASE_URL=sqlite:///./ai_trace.db
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
DEBUG=True
```

## 📡 API Endpoints

Will add endpoints like:

- `POST /api/v1/llm/request` - Send LLM request and trace
- `GET /api/v1/traces` - List all traces
- `GET /api/v1/traces/{trace_id}` - Get specific trace
- `GET /api/v1/llm/models` - List supported models
- `GET /api/v1/analytics/latency` - Get latency analytics

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html
```

## 📚 Development

### Add New Model

1. Create model file in `app/models/`
2. Import in `app/models/__init__.py`
3. Run `python -c "from app.database import init_db; init_db()"` to create table

### Add New API Endpoint

1. Create router file in `app/api/`
2. Define FastAPI router
3. Include in `main.py`:
   ```python
   from app.api import my_router
   app.include_router(my_router.router, prefix="/api/v1")
   ```

## 🚀 Deployment

See `DEPLOYMENT.md` for Render deployment instructions.

## 🐛 Troubleshooting

### Database locked error
Delete `ai_trace.db` and restart server to reinitialize.

### Import errors
Make sure you're in the backend directory and virtual environment is activated.

### API keys not working
Check that API keys are set in `.env` file and database is initialized.

## 📖 Documentation

- **Architecture**: See `ARCHITECTURE.md`
- **API Reference**: See `API.md`
- **Deployment**: See `DEPLOYMENT.md`

## ✅ What's Implemented

- ✅ FastAPI app setup
- ✅ Database models (Request, Trace, Evaluation, SupportedModel)
- ✅ SQLAlchemy configuration
- ✅ Environment configuration
- ✅ Health check endpoint
- ✅ CORS middleware
- ⏳ Pipeline stages (coming next)
- ⏳ LLM integrations (coming next)
- ⏳ API endpoints (coming next)
- ⏳ Evaluation engine (coming next)

## 🎯 Next Steps

1. Create pipeline stage executors
2. Implement LLM integrations
3. Create API endpoints
4. Add evaluation metrics
5. Deploy to Render

---

Made with ❤️ for FYP
