# DataNexus - AI-Powered Data Extraction & Intelligence Platform

## Overview

DataNexus connects to Microsoft OneDrive, automatically processes uploaded documents (PDF, Excel, CSV, DOCX, PPTX, Images), extracts structured and unstructured data, and provides an AI-powered chat interface for querying your documents with semantic search. It can also generate PowerPoint presentations from your data.

## Architecture

```
backend/
├── app/
│   ├── api/v1/          # FastAPI route handlers
│   ├── core/            # Config, DB, security, Celery
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── services/        # Business logic + Celery tasks
│   ├── integrations/
│   │   └── onedrive/    # Microsoft Graph API integration
│   ├── ai/              # RAG pipeline, embeddings, LLM
│   ├── extraction/      # File processing (PDF, Excel, etc.)
│   ├── ppt/             # PowerPoint generation
│   └── utils/           # Shared utilities
├── alembic/             # Database migrations
└── tests/               # Test suite
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Celery
- **Database**: PostgreSQL + pgvector
- **AI**: OpenAI (GPT-4o + embeddings), LangChain
- **File Processing**: PyMuPDF, pdfplumber, openpyxl, python-docx, python-pptx, Tesseract OCR
- **Auth**: JWT (python-jose + passlib)
- **OneDrive**: Microsoft Graph API via MSAL

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- Redis
- Tesseract OCR (for image/scanned PDF processing)

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Docker (recommended)

```bash
docker compose up -d
```

This starts PostgreSQL (with pgvector), Redis, the FastAPI app, and Celery workers.

### 3. Manual setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 4. Database setup

```bash
# Ensure PostgreSQL is running with pgvector enabled
psql -U datanexus -d datanexus -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
cd backend
alembic upgrade head
```

### 5. Run the application

```bash
# Terminal 1: API server
make run
# or: cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery worker
make worker

# Terminal 3: Celery beat (optional, for scheduled tasks)
make beat
```

### 6. Access the API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login and get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |

### Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/files/upload` | Upload a file |
| GET | `/api/v1/files` | List user's files |
| GET | `/api/v1/files/{id}` | Get file details |
| GET | `/api/v1/files/{id}/status` | Get processing status |
| DELETE | `/api/v1/files/{id}` | Delete a file |

### OneDrive
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/onedrive/auth-url` | Get OAuth2 auth URL |
| GET | `/api/v1/onedrive/callback` | OAuth2 callback |
| GET | `/api/v1/onedrive/status` | Connection status |
| GET | `/api/v1/onedrive/files` | List OneDrive files |
| POST | `/api/v1/onedrive/select-folder` | Select sync folder |
| POST | `/api/v1/onedrive/sync` | Trigger sync |

### Chat (AI)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send a chat query |
| GET | `/api/v1/chat/sessions` | List chat sessions |
| GET | `/api/v1/chat/history/{id}` | Get session history |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/search/semantic` | Semantic vector search |
| POST | `/api/v1/search/structured` | Structured data search |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/reports/generate-ppt` | Generate a PPT report |
| GET | `/api/v1/reports` | List reports |
| GET | `/api/v1/reports/{id}` | Get report details |
| GET | `/api/v1/reports/{id}/download` | Download PPT file |

## Environment Variables

See `.env.example` for all required configuration variables.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key for embeddings and chat
- `MS_CLIENT_ID` / `MS_CLIENT_SECRET` - Microsoft Azure app registration
- `FERNET_KEY` - Encryption key for storing OAuth tokens
- `CELERY_BROKER_URL` - Redis URL for Celery

## Integrating Your Data Extraction Module

The extraction pipeline is pluggable. To integrate your existing module:

1. Create a new extractor in `backend/app/extraction/` implementing `BaseExtractor`
2. Register it in `backend/app/extraction/pipeline.py`
3. Or modify the `process_file` function in `pipeline.py` to call your module directly

## Running Tests

```bash
make test
# or: cd backend && python -m pytest -v
```

## Make Commands

```bash
make run        # Start API server
make worker     # Start Celery worker
make beat       # Start Celery beat
make migrate    # Run database migrations
make migration msg="description"  # Create new migration
make test       # Run tests
make lint       # Run linter
make format     # Format code
make docker-up  # Start Docker services
make docker-down # Stop Docker services
```
