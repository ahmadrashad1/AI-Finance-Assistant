# Backend (FastAPI)

The application runtime. FastAPI orchestrates every request — the LLM
reasons but never executes code, touches the database, or generates SQL
(see `docs/adr/0001-fastapi-as-orchestrator.md`).

Layering is one-directional and strict (PRD Chapter 14):

    api/ (thin endpoints) -> ChatWorkflow (ai_platform/orchestration) ->
    domains/finance/tools -> domains/finance/services ->
    domains/finance/repositories -> PostgreSQL

Endpoints must never contain SQL, business rules, prompt construction, or
tool selection — those belong to workflows, services, and the platform
orchestration engine respectively.

## What's here

```
app/
  main.py             # FastAPI app factory, CORS (exposes X-Request-ID), router wiring
  core/
    config.py         # Pydantic v2 Settings, loaded from environment / .env
    logging.py        # Structured JSON logs + request/conversation/workflow context vars
    errors.py         # Error categories (Validation/Business/Infrastructure/AI/Unexpected) + handlers
    tool_registry.py  # Builds the app's ToolRegistry (12 tools: 11 finance + get_current_date)
  middleware/
    request_context.py # Attaches a request_id to every request (generated or echoed)
  api/
    chat.py           # POST /api/chat (SSE stream), conversation list/messages endpoints
    trace.py          # GET /api/trace/{request_id} — plan, prompt versions, tool executions
    health.py         # GET /api/health
  db/
    base.py           # Shared SQLAlchemy declarative base
    session.py        # Async engine/session + check_database_connection()
alembic/              # Migrations (finance, application, and evaluation schemas)
scripts/
  run_demo.py         # Scripted PRD success-criterion demo conversations (see docs/DEMO.md)
tests/                # pytest suite: unit + integration tests for backend, ai_platform, domains
```

The `ai_platform` and `domains` packages live at the repo root and are
installed editable into this virtualenv (`pip install -e ..`).

## Local setup

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -e ..              # ai_platform + domains (repo root)
pip install -e ".[dev]"        # backend + dev tooling
cp .env.example .env           # set LLM_API_KEY (Groq); adjust DATABASE_URL if needed
alembic upgrade head           # create finance/application/evaluation schemas
python -m domains.finance.simulator.seed   # seed Northwind Manufacturing Ltd. (seed=42)
uvicorn app.main:app --reload
```

`GET /api/health` returns `{"status": "healthy", "app": "ok", "database": "ok"}`
when PostgreSQL (see the repo-root `docker-compose.yml`) is reachable, or
`"status": "degraded"` / `"database": "unavailable"` otherwise — it never
raises just because the database is down.

Useful commands (from `backend/`):

```bash
.venv/Scripts/python -m pytest                                    # full test suite
.venv/Scripts/python -m ruff check . ../ai_platform ../domains    # lint, full project scope
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains  # strict types
.venv/Scripts/python -m domains.finance.simulator.seed --reset    # reseed from scratch
.venv/Scripts/python -m domains.finance.simulator.consistency_check
.venv/Scripts/python -m ai_platform.evaluation.run --suite core   # eval suite (recorded)
.venv/Scripts/python scripts/run_demo.py                          # demo conversations (server must be running)
```

Note: pytest truncates the finance tables (`clean_db`); reseed before
anything that reads seeded data (demos, eval recording, manual chat).

Python tooling (ruff + mypy strict) is configured in `pyproject.toml`.
