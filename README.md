# AI Employee Platform

An AI Employee Platform for building AI-powered business assistants that
reason over deterministic, structured business capabilities instead of
navigating traditional software UIs. **Finance is the first domain** built
on this platform: the AI Finance Assistant, an assistant that lets finance
employees ask natural-language questions ("Which customers haven't paid
us?", "Find duplicate invoices.", "Generate an aging report.") and get
accurate, explained answers grounded in real (initially simulated)
finance data.

The platform is deliberately domain-agnostic so that later AI employees
(HR, Procurement, Sales, ...) can be added without rebuilding the
orchestration, workflow, tool-registry, evaluation, or memory
infrastructure — only a new `domains/<name>/` package is needed.

## Why an MVP on a simulator, not a real ERP

The MVP's only goal is to answer one question: *can an AI assistant
consistently understand finance questions, choose the right tools, reason
correctly, and respond accurately?* Everything else — real ERP
integration, cloud deployment, multi-tenancy, authentication — is
explicitly out of scope until that question is answered. See
`docs/PRD.md` for the full product/design document and
`docs/adr/0003-finance-simulator-over-real-erp.md` for why a Finance
Simulation Environment stands in for a real ERP during MVP development.

## Repository layout

```
platform/            # reusable AI employee infrastructure (domain-agnostic)
  orchestration/      # AI request lifecycle: memory -> plan -> execute -> respond
  workflow/           # workflow framework/SDK (Initialize -> Validate -> Execute -> Log -> Evaluate -> Complete)
  tool_registry/      # tool registration & metadata the LLM planner reads
  evaluation/         # Evaluation-Driven Development framework
  memory/             # conversation memory management

domains/
  finance/            # the first domain: tools, services, and the Finance Simulator
    tools/
    services/
    simulator/

backend/              # FastAPI application (orchestrates everything; the LLM never touches the DB)
frontend/             # Next.js application (chat-first presentation layer, no business logic)

docs/
  PRD.md              # full Product Requirements & Software Design Document
  adr/                # Architecture Decision Records
```

## Non-negotiable engineering rules

See [`CLAUDE.md`](./CLAUDE.md) for the full list (data access, natural
language only, two-phase LLM execution, strict layering, workflow
lifecycle, structured logging, error categorization, testing/evaluation
requirements, naming conventions). In short: **the LLM reasons; FastAPI
executes.** Business logic lives in services, never in prompts.

## Getting started (Milestone 1: Project Foundation)

```bash
make db-up                                  # Postgres 16 via docker-compose

cd backend
python -m venv .venv && .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload                # http://localhost:8000/api/health

cd ../frontend
npm install
cp .env.example .env.local
npm run dev                                  # http://localhost:3000
```

`make test` and `make lint` run the backend (pytest, ruff, mypy) and
frontend (ESLint, tsc) checks; see the root `Makefile`. CI (`.github/workflows/ci.yml`)
runs the same checks on every push/PR.

## Status

Milestone 1 (Project Foundation) is complete: FastAPI + Next.js skeletons,
structured logging, the five-category error-handling middleware, async
SQLAlchemy + Alembic wiring, Postgres via docker-compose, and CI — no
finance functionality yet. See `docs/PRD.md`, Chapter 16 ("Development
Roadmap & Milestones") for the full planned build sequence through
Milestone 10 (MVP complete).
