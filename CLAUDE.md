# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SendRice is a web tool for HR/Accounting to send salary notifications to employees via Zalo. It imports Excel files, generates salary slip images, uploads them to Google Drive, and sends notifications through n8n webhooks.

## Common Commands

```bash
# Development with Docker (recommended)
docker-compose up -d app db          # Start app + database
docker-compose exec app python scripts/init_db.py  # Initialize database

# Local development without Docker
python -m venv venv
venv\Scripts\activate                # Windows
source venv/bin/activate             # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Production (with nginx + SSL)
docker-compose up -d
```

## Architecture

**Tech Stack:** Python 3.11 + FastAPI, PostgreSQL 16, Jinja2 + HTMX + Alpine.js, LibreOffice + PyMuPDF

### Key Directories

- `app/main.py` - FastAPI entry point, lifespan management, router mounting
- `app/config.py` - Pydantic Settings for environment variables
- `app/database.py` - SQLAlchemy async setup with PostgreSQL (asyncpg)
- `app/models/` - SQLAlchemy ORM models (Employee, ImportSession, SendHistory, Settings)
- `app/schemas/` - Pydantic request/response schemas
- `app/services/` - Business logic layer:
  - `excel_parser.py` - openpyxl parsing with configurable column mapping
  - `salary_slip_service_optimized.py` - LibreOffice + PyMuPDF salary slip image generation
  - `background_image_service.py` - Background batch processing with SSE updates
  - `webhook_service.py` - n8n webhook with retry logic
- `app/routers/` - API routes (main, employees, settings)
- `app/templates/` - Jinja2 templates with HTMX partials

### Data Flow

1. Excel upload → `excel_parser` extracts employee data → stored in PostgreSQL
2. Generate image → `salary_slip_service_optimized` creates PNG via LibreOffice + PyMuPDF
3. Send notification → `webhook_service` POSTs to n8n with base64 image → n8n sends Zalo message

### Webhook Payload Format

```json
{"SDT": "0901234567", "Ten": "Name", "Luong": 15000000, "HinhAnhBase64": "data:image/png;base64,..."}
```

### Frontend Pattern

Server-rendered with HTMX for partial updates. Alpine.js manages client state (selected employees). Templates in `app/templates/partials/` return HTML fragments for HTMX swapping.

## Configuration

Environment variables loaded via Pydantic Settings from `.env`:
- `DATABASE_URL` - PostgreSQL connection string
- `N8N_WEBHOOK_URL` - Webhook endpoint for Zalo notifications
- `SECRET_KEY` - Application secret key

Excel column mapping is configurable via Settings page and stored in database.
