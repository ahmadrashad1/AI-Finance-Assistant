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
ai_platform/         # reusable AI employee infrastructure (domain-agnostic)
  orchestration/      # AI request lifecycle: memory -> plan -> execute -> respond
  workflow/           # workflow framework/SDK (Initialize -> Validate -> Execute -> Log -> Evaluate -> Complete)
  tool_registry/      # tool registration, metadata, and the deterministic tool executor
  evaluation/         # Evaluation-Driven Development framework (cassette record/replay)
  memory/             # conversation memory management
  llm/                # provider-agnostic LLMService (Groq/Anthropic implementations)
  prompts/            # versioned prompt artifacts (planning + system prompts)

domains/
  finance/            # the first domain: tools, services, repositories, and the Finance Simulator
    tools/             # 11 deterministic finance tools the planner can select
    services/
    repositories/
    simulator/         # seed generator, consistency check (the dev ERP)

backend/              # FastAPI application (orchestrates everything; the LLM never touches the DB)
  scripts/run_demo.py # scripted PRD success-criterion demo conversations
frontend/             # Next.js application (chat-first presentation layer, no business logic)
evals/                # evaluation suites (53 cases) + recorded LLM cassettes

docs/
  PRD.md              # full Product Requirements & Software Design Document
  adr/                # Architecture Decision Records (0001-0007)
  DEMO.md             # verified demo conversations for every PRD success criterion
  MVP-REPORT.md       # eval scorecard, known limitations, post-MVP priorities
```

## Non-negotiable engineering rules

See [`CLAUDE.md`](./CLAUDE.md) for the full list (data access, natural
language only, two-phase LLM execution, strict layering, workflow
lifecycle, structured logging, error categorization, testing/evaluation
requirements, naming conventions). In short: **the LLM reasons; FastAPI
executes.** Business logic lives in services, never in prompts.

## Getting started (≈10 minutes)

Prerequisites: Docker Desktop (running), Python 3.12+, Node 20+, and a free
[Groq API key](https://console.groq.com) (only needed for live chat — the
tests and the recorded evaluation suite run without one).

```bash
# 1. Database (~1 min)
docker compose up -d                             # Postgres 16

# 2. Backend (~5 min)
cd backend
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on macOS/Linux
pip install -e .. && pip install -e ".[dev]"
cp .env.example .env                             # then set LLM_API_KEY=<your Groq key> in .env
alembic upgrade head                             # create the schema
python -m domains.finance.simulator.seed         # seed Northwind Manufacturing Ltd. (seed=42)
uvicorn app.main:app --reload                    # http://localhost:8000/api/health

# 3. Frontend (~3 min, new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                                      # http://localhost:3000
```

Open http://localhost:3000 and ask: *"Which customers haven't paid us?"*,
*"Generate an aging report."*, *"Find duplicate invoices."* Every assistant
reply has a "View trace" toggle showing the plan, prompt versions, and tool
executions behind it.

## Demo, tests, and evaluation

```bash
cd backend
.venv/Scripts/python scripts/run_demo.py            # scripted PRD success-criterion demos (backend must be running)
.venv/Scripts/python -m pytest                      # unit + integration tests
.venv/Scripts/python -m ai_platform.evaluation.run --suite core   # AI evaluation suite (recorded mode, no API key needed)
```

The recorded eval suite deliberately reports 39/53 — the 14 failing cases
are documented model-behavior findings, not regressions (the runner exits
non-zero by design until they're fixed by prompt/model improvements). See
`docs/MVP-REPORT.md` for the scorecard and known limitations, and
`docs/DEMO.md` for verified demo conversations.

`make test` and `make lint` run the backend (pytest, ruff, mypy) and
frontend (ESLint, tsc) checks; see the root `Makefile`. CI (`.github/workflows/ci.yml`)
runs the same checks on every push/PR.

## Status

**MVP complete (Milestone 10).** All ten milestones from `docs/PRD.md`
Chapter 16 are done: conversational finance assistant, Finance Simulator
(seeded, internally consistent), 12 deterministic tools, two-phase
planning/response execution, request tracing, a 53-case evaluation
framework with recorded-cassette replay, CI, and documentation. See
`docs/MVP-REPORT.md` for the evaluation scorecard, the honest gap list
(tool-selection accuracy vs. the PRD target), and prioritized post-MVP
work; `docs/DEMO.md` for the verified success-criterion conversations;
and `docs/adr/` for the seven architecture decision records.
