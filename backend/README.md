# Backend (FastAPI)

The application runtime. FastAPI orchestrates every request — the LLM
reasons but never executes code, touches the database, or generates SQL
(see `docs/adr/0001-fastapi-as-orchestrator.md`).

**Milestone 1 (Project Foundation) is implemented: infrastructure only, no
finance functionality.** When Finance tools/services land, this package
should follow the layering from the PRD (Chapter 14):

    api/ (thin endpoints) -> workflows/ -> platform (ai/orchestration) ->
    domains/finance/tools -> domains/finance/services ->
    repositories -> PostgreSQL

Endpoints must never contain SQL, business rules, prompt construction, or
tool selection — those belong to workflows, services, and the platform
orchestration engine respectively.

## What's here

```
app/
  main.py             # FastAPI app factory/instance, wires everything together
  core/
    config.py          # Pydantic v2 Settings, loaded from environment / .env
    logging.py          # Structured JSON log formatter + request/conversation/workflow context vars
    errors.py            # Error categories (Validation/Business/Infrastructure/AI/Unexpected) + handlers
  middleware/
    request_context.py  # Attaches a request_id to every request (generated or echoed)
  api/
    health.py            # GET /api/health
  db/
    base.py               # Shared SQLAlchemy declarative base (no models yet)
    session.py             # Async engine/session + check_database_connection()
alembic/                    # Migrations tooling (no migrations yet — no models yet)
tests/                        # pytest + httpx async tests for all of the above
```

## Local setup

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -e ..
pip install -e ".[dev]"
cp .env.example .env           # adjust DATABASE_URL etc. if needed
uvicorn app.main:app --reload
```

`GET /api/health` returns `{"status": "healthy", "app": "ok", "database": "ok"}`
when PostgreSQL (see the repo-root `docker-compose.yml`) is reachable, or
`"status": "degraded"` / `"database": "unavailable"` otherwise — it never
raises just because the database is down.

Python tooling (ruff + mypy strict) is configured in `pyproject.toml`.
