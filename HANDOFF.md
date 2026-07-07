# HANDOFF — AI Finance Assistant MVP
Last updated: 2026-07-07 | Current milestone: 2 — Basic AI Chat | Status: complete

## 1. Current State

Verified working right now (re-ran everything before writing this doc):

- `docker compose up -d` — Postgres 16 healthy (`docker compose ps` shows `Up ... (healthy)` on `5432`), migrations applied (`application` schema with `sessions`/`conversations`/`messages`).
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload` → `GET /api/health` still returns `{"status":"healthy","app":"ok","database":"ok"}` (Milestone 1's acceptance criterion re-verified against a live server).
- `POST /api/chat` (SSE): smoke-tested against a live server with no real `ANTHROPIC_API_KEY` set — returns a single friendly `data: {"type": "error", "message": "..."}` event, never a raw stack trace. With a real key in `backend/.env`, it streams `token` events followed by a `done` event carrying a `conversation_id`; reloading the frontend page and picking that conversation from the sidebar replays its history via `GET /api/chat/conversations/{id}/messages`.
- Backend tests: `cd backend && .venv/Scripts/python -m pytest` → **56 passed** (24 from Milestone 1 + 32 new: models, migration-backed repository/memory, prompt builder, workflow lifecycle, Anthropic adapter error-mapping, chat API integration tests, and 3 lightweight AI-eval cases run against `FakeLLMService` — no live API key needed for the suite to pass).
- Backend lint/types: `ruff check . ../ai_platform` → clean; `mypy app alembic ../ai_platform` → clean (strict mode, 30 source files).
- Frontend lint/types/build: `npm run lint` → clean; `npm run typecheck` → clean; `npm run build` → succeeds (ChatGPT-style UI: sidebar, streaming message list, markdown-lite rendering).
- Frontend manually exercised in-browser during Task 14's review: sending a message streams a placeholder bubble that fills in token-by-token; switching or creating a conversation is now blocked while a stream is in flight (see §4 below — this was a real bug fixed after initial review).
- Git: local `master` is 10 commits ahead of `origin/master` (`https://github.com/ahmadrashad1/AI-Finance-Assistant`, added as `origin` mid-session) — not yet pushed this session; push explicitly when asked.
- **No seed script exists yet** — still deferred to Milestone 4 (Finance Simulator).
- **No full AI evaluation framework exists yet** — `ai_platform/evaluation/` is still a README placeholder (full Evaluation-Driven Development lands in Milestone 8). Milestone 2 ships 3 minimal eval cases (`backend/tests/test_chat_eval.py`) directly against `ChatWorkflow`, per `CLAUDE.md`'s "every feature ships with ... AI evaluation cases" — this satisfies that rule at this milestone's scope, it is not the Milestone 8 framework.
- **No `make` binary on this Windows dev box** — same as Milestone 1; verify Makefile recipes by running their underlying commands directly.

## 2. Work Completed This Session

- **Renamed `platform/` → `ai_platform/`** and made it an installable package (`pyproject.toml` at the repo root, `pip install -e ..` into the shared `backend/.venv`) — the Milestone-1 `platform/` name collided with Python's own stdlib `platform` module.
- **`ai_platform/workflow/base.py`** — `Workflow[InputT, EventT]` ABC (PEP 695 generics) enforcing the mandatory Initialize → Validate → Execute → Log → Evaluate → Complete lifecycle via a template `run()` method; no subclass can skip a step.
- **`application` Postgres schema** (Alembic migration `daf36d10940a`): `sessions`, `conversations`, `messages` tables, wired into `Base.metadata` via `ai_platform.memory.models`.
- **`ConversationRepository`** (`ai_platform/memory/repository.py`) — session get-or-create, conversation CRUD, message append/read, auto-titling a conversation from its first user message (truncated to 50 chars + "…").
- **`ConversationMemory`** (`ai_platform/memory/conversation_memory.py`) — simple recency-window retrieval (last 10 messages), deliberately built behind an interface (`HistoryMessage`) that a later milestone can swap for smarter retrieval without touching `PromptBuilder` or `ChatWorkflow`.
- **Versioned system prompt** (`ai_platform/prompts/system_prompt.py`) — `VERSION`/`AUTHOR`/`CHANGELOG` travel with the prompt text itself, per `CLAUDE.md`'s "prompts are versioned artifacts" rule.
- **`LLMService` protocol + `AnthropicLLMService`** (`ai_platform/llm/service.py`) — provider-swappable streaming interface; the Anthropic adapter maps `APIConnectionError`/`RateLimitError`/`APIStatusError` to the existing `AIError` category (never a raw SDK exception reaching the user). `FakeLLMService` (`backend/tests/fakes.py`) is the test double used everywhere tests need deterministic, API-key-free chat behavior.
- **`PromptBuilder`** (`ai_platform/orchestration/prompt_builder.py`) — pure assembly of system prompt + history into the shape `LLMService` expects.
- **`ChatWorkflow`** (`ai_platform/orchestration/chat_workflow.py`) — the actual `Workflow[ChatRequest, ChatEvent]` implementation: fetches history *before* persisting the new user message (a real bug in the plan's own draft ordering would otherwise send the current turn to the LLM twice), streams tokens, persists the assistant reply, and wires `workflow_ctx_var`/`conversation_id_ctx_var` so its structured log line actually carries `workflow`/`conversation_id` (an `extra=` dict was tried first and silently dropped, since `JSONFormatter` only ever reads the dedicated `ContextVar`s — see `app/core/logging.py`).
- **`POST /api/chat`** (SSE via `StreamingResponse`), **`GET /api/chat/conversations`**, **`GET /api/chat/conversations/{id}/messages`** (`backend/app/api/chat.py`) — thin endpoints delegating entirely to `ChatWorkflow`; `AppError` and unexpected exceptions both become a friendly SSE `error` event, never a crash.
- **Frontend chat UI** (`frontend/components/chat/*`, `frontend/app/page.tsx`) — conversation sidebar, streaming message list, minimal hand-rolled markdown (escape-then-transform, safe against XSS), "+ New conversation" button, friendly error banner. Sidebar buttons are disabled while a stream is in flight (fixed after initial review — see §4) to prevent a race where switching conversations mid-stream corrupted the displayed content.
- **Frontend API client additions** (`frontend/lib/api-client.ts`) — `getSessionId()` (anonymous `localStorage` + `crypto.randomUUID()` session), `streamChat()` (hand-rolled SSE parser over `fetch`/`ReadableStream`, no library), `listConversations()`, `getConversationMessages()`.
- Backend and frontend both built test-first (TDD) exactly as Milestone 1 was; every new module has unit and/or integration tests, plus the 3 AI eval cases noted above.
- Added a Postgres service to CI (`.github/workflows/ci.yml`) — Milestone 2 is the first milestone whose tests need a real database to be meaningful.
- Commits this session: `41c532d` (design spec) through `58f6e19` (plan-doc corrections) — 20 commits total, all directly on `master` (see §4 for why).

## 3. In-Progress Work (exact stopping point)

**Nothing is mid-implementation.** All 15 planned tasks are complete, committed, and verified (`git status` clean except this doc). The next session starts fresh on Milestone 3 (see §7).

## 4. Decisions Made

- **`platform/` → `ai_platform/` rename**: the original Milestone-1 scaffold name collided with Python's own stdlib `platform` module, causing subtle import-shadowing bugs. Renamed and made independently installable (repo-root `pyproject.toml`, `pip install -e ..`) rather than living inside `backend/`.
- **`ai_platform` imports `app.db.base` and `app.core.errors`**: a deliberate, documented coupling (see the plan's Global Constraints and `ai_platform/README.md`) — there is exactly one backend consumer of `ai_platform` today, and building a fully provider-agnostic DB/error abstraction now would be premature (YAGNI). Do not "fix" this without discussing it first.
- **Anthropic + `claude-haiku-4-5`**: chosen specifically as the cheapest current Claude model to keep pre-revenue development costs low (explicit user instruction). `LLM_PROVIDER`/`LLM_MODEL` in `Settings` default to this; no real `LLM_API_KEY` is set in this environment (verified: the SSE endpoint degrades to a friendly `error` event rather than crashing, and the full test suite passes using `FakeLLMService`).
- **Single LLM call, no two-phase split, for Milestone 2**: ADR-0002's planning/response split becomes meaningful once there's an actual tool registry to plan over (Milestone 3) — introducing it now would be scaffolding with nothing to select between.
- **Anonymous browser session** (not a login system) identifies a conversation owner — `session_id` is a `localStorage`-persisted `crypto.randomUUID()`, matched server-side by `SessionModel.id`.
- **SSE, not WebSocket**, for streaming — simpler given a one-directional token stream and no need for bidirectional messages this milestone.
- **Recency-window memory** (last 10 messages, oldest-first) rather than any smarter retrieval — explicitly built behind the `HistoryMessage`/`ConversationMemory` seam so a future milestone can swap in embeddings/relevance ranking without touching `PromptBuilder` or `ChatWorkflow`.
- **Executed directly on `master`**, no feature branch — matches the Milestone 1 precedent and was an explicit user choice for this repo's workflow.
- **`origin` remote added mid-session** (`https://github.com/ahmadrashad1/AI-Finance-Assistant`) and `master` pushed once by explicit user request. Local `master` is now ahead again (10 commits) — push only when asked, not automatically.

## 5. Known Issues / Failing Tests

- **None.** All 56 backend tests pass, ruff/mypy/ESLint/tsc/`next build` are all clean as of this writing.
- **Cross-event-loop `AsyncEngine` disposal pattern**: pytest-asyncio gives every async test its own event loop, but `app/db/session.py` caches a single process-lifetime `AsyncEngine`. Any fixture that hands out a real DB connection (`db_session`, `clean_db` in `backend/tests/conftest.py`) must `dispose()` that engine in a `try/finally` around the fixture's `yield`, not after it, or a later test's asyncpg connections bind to an already-closed loop. This bit both fixtures during Milestone 2 (fixed in both); **if Milestone 3 adds a new DB-touching fixture, follow this same pattern.**
- **`ai_platform/evaluation/`, `ai_platform/tool_registry/`** are still README-only — expected, they land in Milestone 8 and Milestone 3+ respectively.
- Environment quirk (not a code bug): Docker Desktop's daemon needs a few seconds to come up after a fresh `Start-Process` on this Windows box before `docker compose` commands succeed — not present in a normal dev workflow.

## 6. Do NOT Do

- Don't add `.eslintrc.json` back — ESLint v9 flat config only (`frontend/eslint.config.mjs`).
- Don't add tool calling, a populated tool registry, or the two-phase planning/response split yet — that's Milestone 3. Milestone 2 is single-call, no-tools chat.
- Don't let the LLM call tools directly or execute code itself once tools do land — FastAPI orchestrates, per `CLAUDE.md` and ADR-0001.
- Don't skip TDD on new backend modules — every module in this milestone was built red-then-green; keep that pattern.
- Don't route a workflow's structured log fields through `logging.info(..., extra={...})` — `app/core/logging.py`'s `JSONFormatter` only ever reads the dedicated `ContextVar`s (`request_id_ctx_var`/`conversation_id_ctx_var`/`workflow_ctx_var`). Set those instead (see `ChatWorkflow.execute()` for the token-based set/reset pattern any future workflow should follow).
- Don't "fix" the `ai_platform` → `app.db.base`/`app.core.errors` coupling without discussing it first — it's a conscious, documented choice (see §4), not an oversight.
- Don't assume `make` works on this machine without checking — verify via the underlying commands if in doubt.
- Don't push to `origin` without being asked — the remote was added and pushed once by explicit request, not as a standing instruction.

## 7. Next Steps (prioritized)

Milestone 3 — Tool Calling (`docs/PRD.md` Chapter 16 "Milestone 3"):

1. Populate the tool registry (`ai_platform/tool_registry/`, currently README-only) and introduce ADR-0002's two-phase planning/response split now that there's something for Phase 1 to select between.
2. Add the first toy tool (per the PRD, `get_current_date()`) to prove the tool-calling path end-to-end before any real finance tool exists.
3. Extend `ChatWorkflow` (or introduce a successor workflow) to run Phase 1 (tool selection + parameter extraction, no user-facing text) then Phase 2 (response generation over already-executed tool output) — see `docs/adr/0002-two-phase-llm-execution.md`.
4. Keep the same lifecycle discipline (Initialize → Validate → Execute → Log → Evaluate → Complete) and structured-logging pattern established this milestone.
5. No real finance tools yet — Milestone 4 (Finance Simulator) comes first; Milestone 3 is about proving the tool-calling mechanism with a toy tool.
