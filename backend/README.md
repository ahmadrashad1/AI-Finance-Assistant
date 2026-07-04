# Backend (FastAPI)

The application runtime. FastAPI orchestrates every request — the LLM
reasons but never executes code, touches the database, or generates SQL
(see `docs/adr/0001-fastapi-as-orchestrator.md`).

No application code exists yet. When implementation begins, this package
should follow the layering from the PRD (Chapter 14):

    api/ (thin endpoints) -> workflows/ -> platform (ai/orchestration) ->
    domains/finance/tools -> domains/finance/services ->
    repositories -> PostgreSQL

Endpoints must never contain SQL, business rules, prompt construction, or
tool selection — those belong to workflows, services, and the platform
orchestration engine respectively.

Python tooling (ruff + mypy) is configured in `pyproject.toml` in this
directory.
