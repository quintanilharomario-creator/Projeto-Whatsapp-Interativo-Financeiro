# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Personal financial management SaaS integrated with WhatsApp and AI. Users send natural-language messages ("Gastei R$50 no mercado") and the system records, categorizes, and analyzes transactions automatically.

**Status:** Early development — only `app/core/` and `app/main.py` have real content. All other files under `app/` are empty stubs defining the intended structure.

## Running the backend

The backend uses Python 3.12+ with a virtual environment at `backend/venv/`.

```bash
cd backend

# Install dependencies
pip install -r requirements.txt          # production
pip install -r requirements-dev.txt      # includes test/lint tools

# Run dev server (requires .env with SECRET_KEY and DATABASE_URL)
uvicorn app.main:app --reload --port 8000

# API docs available at http://localhost:8000/docs
```

Copy `backend/.env.example` to `backend/.env` and fill required values (`SECRET_KEY` must be ≥32 chars — generate with `openssl rand -hex 32`).

## Tests

```bash
cd backend

# All tests
pytest

# Single test file
pytest tests/unit/test_foo.py

# With coverage
pytest --cov=app --cov-report=term-missing
```

Test layout: `tests/unit/` and `tests/integration/`. Tests use `pytest-asyncio`, `factory-boy`, and `faker`.

## Linting and type-checking

```bash
cd backend
ruff check .          # linting
ruff format .         # formatting
mypy app/             # type checking
```

## Architecture

Clean Architecture with four layers:

```
app/
├── api/          # HTTP layer: FastAPI routes, middleware, dependency injection
│   └── v1/endpoints/   # auth, users, transactions, reports, audio, whatsapp
├── core/         # Cross-cutting: config, exceptions, logging, security, rate_limit
├── domain/       # Business logic (framework-independent)
│   ├── entities/       # Pure business objects
│   ├── interfaces/     # Repository and provider abstract contracts
│   ├── rules/          # Domain rules (balance_calculator, transaction_validator)
│   └── value_objects/  # Money, TransactionType
├── services/     # Application use cases (orchestrate domain + infra)
├── schemas/      # Pydantic request/response models
├── infrastructure/  # External concerns: DB, AI, cache, storage, WhatsApp, audio
│   ├── database/models/        # SQLAlchemy ORM models
│   ├── database/repositories/  # Concrete repository implementations
│   ├── ai/                     # OpenAI and Claude provider implementations
│   └── (cache, storage, payments, memory, whatsapp)
└── workers/      # Celery async tasks (ai_tasks, audio_tasks, whatsapp_tasks)
```

**Dependency direction:** `api` → `services` → `domain`; `infrastructure` implements `domain/interfaces`.

## Key conventions

**Settings:** All config lives in `app/core/config.py` (`Settings` via pydantic-settings). Access via `from app.core.config import settings`. Required env vars: `SECRET_KEY`, `DATABASE_URL`.

**Logging:** Use `structlog` — always `from app.core.logging import get_logger; logger = get_logger(__name__)`. Log with keyword args: `logger.info("event_name", key=value)`. Dev output is colored console; production is JSON.

**Exceptions:** Raise typed exceptions from `app/core/exceptions.py` (e.g., `raise UserNotFoundError(user_id=42)`). Never raise raw `Exception`. The hierarchy maps directly to HTTP status codes (`AuthenticationError=401`, `NotFoundError=404`, etc.).

**AI provider:** Configurable via `AI_PROVIDER` env var (`"openai"` or `"claude"`). Implementations in `app/infrastructure/ai/`.

**Database:** SQLAlchemy async with `asyncpg`. Alembic migrations in `backend/migrations/`. The sync URL variant (for Alembic) is available via `settings.database_url_sync`.

## Infrastructure services

- **PostgreSQL 16** — primary data store
- **Redis 7** — cache (`REDIS_DB=0`) and Celery broker (`REDIS_DB=1`) / result backend (`REDIS_DB=2`)
- **Celery** — async task queue for AI processing, audio transcription, WhatsApp messaging
- **MinIO** (default) or S3 — file storage
- **ChromaDB** (default) or Pinecone — semantic memory for AI context
- **WhatsApp Cloud API** — primary messaging channel (Evolution API and Baileys also supported via `WHATSAPP_PROVIDER`)
