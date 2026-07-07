# HANDOFF — AI Finance Assistant MVP
Last updated: 2026-07-08 | Current milestone: 3 — Tool Calling | Status: complete

## 1. Current State

Verified working right now (re-ran everything before writing this doc):

- `docker compose up -d` — Postgres 16 healthy, migrations applied (`application` schema now has `sessions`/`conversations`/`messages`/`tool_executions`).
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload` → `GET /api/health` still returns `{"status":"healthy","app":"ok","database":"ok"}` (Milestones 1-2's acceptance criterion re-verified against a live server).
- **`POST /api/chat` two-phase pipeline, smoke-tested end to end against a live server with a real Groq API key**: sending `"What is today's date?"` returns, in order, a `tool_call` event (`{"type": "tool_call", "tool": "get_current_date"}`), then streamed `token` events whose text is grounded in the tool's actual output, then `done`. Confirmed all three acceptance-criteria legs directly:
  - **UI/API**: the SSE stream above.
  - **Database**: `SELECT tool, status, result FROM application.tool_executions ORDER BY created_at DESC LIMIT 1` returned `get_current_date | success | {"date": "2026-07-07", "day_of_week": "Tuesday"}`.
  - **Structured logs**: the server log contains `{"severity": "INFO", "component": "ai_platform.tool_executor", "message": "tool execution complete: tool=get_current_date status=success duration_ms=0", "request_id": "...", "conversation_id": "...", "workflow": "chat"}` — tool, status, and duration in the message, full request/conversation/workflow context from the existing ContextVar pattern.
  - Notably, the model's reply self-corrected mid-sentence ("...Wednesday, ...but based on the tool result, the correct day of the week is actually Tuesday") — good evidence the response-phase grounding instruction (Task 10) is doing real work, not just decoration.
- A plain greeting ("hi") still takes the `direct_answer` branch with no tool call — Milestone 2's small-talk behavior is unchanged.
- Backend tests: `cd backend && .venv/Scripts/python -m pytest` → **99 passed** (56 from Milestone 2 + 43 new: tool registry, `get_current_date` tool, `tool_executions` model/repository, result validator, tool executor, `LLMService.complete()` for both providers, versioned planning prompt, `Planner`, rewired `ChatWorkflow` tests, chat API integration test, and 3 new AI-eval cases — no live API key needed for the suite to pass, `FakeLLMService` covers both `stream_reply` and `complete`).
- Backend lint/types: `ruff check . ../ai_platform` → clean; `mypy app alembic ../ai_platform` → clean (strict mode, 42 source files).
- Frontend lint/types/build: `npm run lint` → clean; `npm run typecheck` → clean; `npm run build` → succeeds. Manually verified in-browser (network-throttled) that a `tool_call` event shows a transient "Running get_current_date…" status that's cleanly replaced once real tokens arrive, with no leftover artifact even if an error lands mid-flight.
- Git: all Milestone 3 work is committed directly to `master` (same policy as Milestones 1-2). Not pushed this session — push only when asked.
- **`domains/finance/`** is still README-only — expected, no real finance tools yet (Milestone 4/5).
- **No full AI evaluation framework exists yet** — `ai_platform/evaluation/` is still a README placeholder (full Evaluation-Driven Development lands in Milestone 8). This milestone's AI eval cases stay lightweight, direct-`ChatWorkflow` tests, matching Milestone 2's precedent.

## 2. Work Completed This Session

- **Tool Registry** (`ai_platform/tool_registry/registry.py`) — `ToolSpec` (name, description, `parameters_model`/`result_model` as Pydantic classes, an async `handler`), `ToolRegistry` (register/get/list_specs, plus `to_planner_json()` which exposes only name/description/JSON-schema to the LLM — never the handler or result model, per ADR-0004).
- **`get_current_date` tool** (`ai_platform/tool_registry/tools/get_current_date.py`) — the milestone's one and only tool, parameter-less, `extra="forbid"` on its params model. Deliberately domain-agnostic infrastructure, not a finance capability — lives in `ai_platform/`, not `domains/finance/`.
- **`application.tool_executions` table** (Alembic migration `7d249154768c`, model in `ai_platform/tool_registry/models.py`) — records every tool call: `request_id`, `conversation_id`, `tool`, `parameters`, `result`, `duration_ms`, `status`, `error_message`, `created_at`.
- **`ToolExecutionRepository`** (`ai_platform/tool_registry/repository.py`) — `record_execution`/`list_for_conversation`, same thin-wrapper pattern as `ConversationRepository`.
- **Result Validator** (`ai_platform/tool_registry/result_validator.py`) — re-validates a tool handler's return value against its declared `result_model` before it's trusted further up the pipeline (PRD Ch.13 Step 9).
- **`ToolExecutor`** (`ai_platform/tool_registry/executor.py`) — runs one planned tool call: looks up the tool, validates parameters, runs the handler, validates the result, persists the execution row, logs it. All four failure modes (unknown tool, bad parameters, handler exception, malformed result) degrade to a graceful `status="error"` outcome — **never** crashes the request (PRD Ch.13 Error Recovery Branch) — and are still persisted and logged like a success.
- **`LLMService.complete()`** (`ai_platform/llm/service.py`) — a new non-streaming completion method added to the existing protocol (purely additive — `stream_reply` unchanged), implemented for both `AnthropicLLMService` and `GroqLLMService` (Groq's uses `response_format={"type": "json_object"}` for reliable JSON output; Anthropic has no equivalent, relies on prompt instructions). Used only by the planner.
- **Versioned planning prompt** (`ai_platform/prompts/planning_prompt.py`) — instructs the model to respond with strict JSON matching one of three shapes, embeds the tool registry's JSON specs at call time.
- **`Planner`** (`ai_platform/orchestration/planner.py`) — `ToolCall`/`Plan` (Pydantic, with a `model_validator` enforcing exactly one of `clarification_needed`/`tool_calls`/`direct_answer` is set), `Planner.create_plan()` calls `LLMService.complete()`, strips defensive markdown fences, parses/validates the JSON, raising `AIError` (flowing through the existing SSE error path) on any malformed response.
- **Response-phase system prompt bumped to 1.1.0** (`ai_platform/prompts/system_prompt.py`) — added an explicit instruction to ground responses in provided tool results and never state a finance figure or date absent from them; removed the now-stale "no tools yet" language.
- **`ChatWorkflow` rewired** (`ai_platform/orchestration/chat_workflow.py`) to the full two-phase pipeline: fetch history → persist user message → `Planner.create_plan()` → branch:
  - `clarification_needed` → single `token` event with the question, persist, `done`, **no tool execution, no Phase 2 call**.
  - `tool_calls` → emit a `tool_call` SSE event per call (before executing it), run each via `ToolExecutor`, feed the outcomes into Phase 2's LLM-facing message (`[Tool results — use only this data]` marker) without polluting the persisted DB message.
  - `direct_answer` → same code path as `tool_calls` with zero outcomes — Milestone 2's small-talk behavior, unchanged.
  - `ChatEvent` gained a `tool: str | None` field for the new event type.
- **FastAPI wiring** (`backend/app/core/tool_registry.py`, `backend/app/main.py`, `backend/app/api/chat.py`) — `get_tool_registry()` (`@lru_cache`, mirrors `get_settings()`), registered eagerly at app startup (fail-fast per ADR-0004, not lazily on first request); `POST /api/chat` now builds `Planner`/`ToolExecutor`/`ToolExecutionRepository` per request and wires them into `ChatWorkflow`; SSE payloads include `tool` when present.
- **Frontend**: `ChatStreamEvent` gained `ChatToolCallEvent`; the chat page shows a transient "Running {tool}…" status while a tool call is in flight, cleanly replaced by real tokens or cleared on error (see §4 for the two-round fix this needed).
- Backend and frontend both built test-first; every new module has unit and/or integration tests, plus 3 new AI eval cases in `backend/tests/test_chat_eval.py` (asking for the date selects `get_current_date`; a greeting takes `direct_answer`; an ambiguous request can short-circuit with a clarification, no tool executed).
- Commits this session: `28e8217` (design spec) through `7f6aea6` (final frontend fix) — 20 commits total, all directly on `master`.

## 3. In-Progress Work (exact stopping point)

**Nothing is mid-implementation.** All 15 planned tasks are complete, committed, and verified (`git status` clean except this doc). The next session starts fresh on the next milestone (see §7).

## 4. Decisions Made

- **The planner does NOT receive today's date as a given fact in its context** — a deliberate deviation from PRD Ch.13's "Build AI Context" step, which lists "Current Date" as a fixed context element. Injecting it here would let the model answer "what's today's date" from context and never call `get_current_date()`, defeating the one thing this milestone exists to prove. Revisit only if a real "as of" date reference need emerges elsewhere (e.g. a "days overdue" tool) — that's a separate concern from this milestone's planner context.
- **Phase 1 uses strict JSON-mode prompting, not native provider tool-calling APIs** — one uniform, provider-agnostic parsing/validation path (a `Plan` Pydantic model with an exactly-one-branch validator) rather than two different native tool-calling schemas that still wouldn't express the clarification/direct-answer branches natively. Groq's `response_format=json_object` is used where available; Anthropic relies on prompt instructions only.
- **A failed tool call degrades gracefully, it never crashes the request** — unknown tool name, bad parameters, handler exception, and malformed result all become a `status="error"` outcome that's still persisted and still fed to Phase 2 so the LLM can explain the failure (PRD Ch.13 Error Recovery Branch), rather than raising and killing the turn.
- **Sequential-only tool execution, no parallel execution graph** — there is exactly one registrable tool this milestone, so a concurrency dispatcher would be pure speculation. Revisit once ≥2 independently-selectable tools exist.
- **`tool_call` SSE event added to the wire contract** (not required by the stated acceptance criteria, which only needed DB/log visibility) — an explicit user choice, made during design brainstorming, to also surface tool activity in the UI rather than keep it backend-only.
- **`get_current_date` lives in `ai_platform/tool_registry/tools/`, not `domains/finance/tools/`** — it's a generic infrastructure-proving tool, not a finance capability. `domains/finance/` stays README-only until Milestone 4/5.
- Executed directly on `master`, no feature branch — same policy as Milestones 1-2.

## 5. Known Issues / Failing Tests

- **None.** All 99 backend tests pass, ruff/mypy/ESLint/tsc/`next build` are all clean as of this writing.
- **A real, subtle bug was caught mid-milestone by independently reproducing rather than trusting an implementer's "pre-existing, unrelated" dismissal** (Task 4): the full suite intermittently failed with `RuntimeError: Event loop is closed` during asyncpg pool cleanup, reproducing only after enough prior DB-touching tests had run in the same process. Root cause: `app/db/session.py`'s module-level `_engine`/`_sessionmaker` globals outlived pytest-asyncio's per-test event loops even after `.dispose()`. Fixed by also nulling both globals in `db_session`/`clean_db` fixtures' `finally` blocks (`backend/tests/conftest.py`), forcing a fully fresh `AsyncEngine`/sessionmaker per test, not just a fresh pool — extends the existing `test_db_session.py` precedent. **If a future milestone adds a new DB-touching fixture and this class of failure resurfaces, this is the fix pattern.**
- **`ai_platform/evaluation/`** is still README-only — expected, lands in Milestone 8.
- `ChatWorkflow.log()`'s "chat turn complete" summary log line runs after `Workflow.run()`'s template method has already drained/closed the `execute()` generator, so by the time it fires, `workflow_ctx_var`/`conversation_id_ctx_var` are already reset to `None` (only `request_id` survives, from the broader HTTP-level ContextVar). This is inherited unchanged from Milestone 2's `Workflow.run()` ordering, not introduced this milestone, and doesn't affect this milestone's own logging acceptance criterion (`ToolExecutor`'s own log line fires mid-request with full context, verified above). Low-priority cleanup if it ever matters: either log a summary line from inside `execute()` before the `finally`, or restructure `Workflow.run()`'s template ordering — needs a decision, not a quick patch, since `Workflow` is shared base infrastructure other future workflows also depend on.

## 6. Do NOT Do

- Don't add `.eslintrc.json` back — ESLint v9 flat config only.
- Don't add real finance tools yet — that's Milestone 4/5. This milestone proves the tool-calling *mechanism* with one toy tool (`get_current_date`), nothing finance-specific.
- Don't build a parallel/concurrent tool-execution graph until there are ≥2 independently-selectable tools — sequential-only was a deliberate YAGNI choice this milestone.
- Don't inject today's date (or any other "free" fact) into the planner's context without checking whether doing so would let the model bypass a tool it should be calling instead — this is exactly the trap Milestone 3's design avoided for `get_current_date`.
- Don't let a tool failure raise all the way out of `ChatWorkflow` — `ToolExecutor` must keep degrading failures to a `status="error"` outcome that Phase 2 can explain, never a crash.
- Don't route structured log fields through `logging.info(..., extra={...})` — `JSONFormatter` only reads the dedicated ContextVars. See known-issue note above about `ChatWorkflow.log()`'s summary line before assuming every log call automatically has full context.
- Don't trust an implementer/reviewer's "pre-existing, unrelated failure" claim without independently reproducing it — this exact milestone caught two real bugs (Task 4's fixture-disposal bug, Task 14's stale-placeholder-on-error bug) that were initially mischaracterized or under-scoped, both fixed only because the controller verified directly rather than accepting the claim.
- Don't assume `make` works on this machine without checking.
- Don't push to `origin` without being asked.

## 7. Next Steps (prioritized)

Per `docs/PRD.md`'s roadmap (Chapter 16), the next milestone is the **Finance Simulator** (Milestone 4) — a simulated ERP backing store that real finance tools (Milestone 5+) will read from, so the tool-calling pipeline this milestone built has real data to operate on:

1. Design and build the Finance Simulator's data model and seed data (invoices, customers, vendors, payments) — see ADR-0003 (simulator over real ERP) for why this exists instead of a live ERP integration.
2. Only after the simulator exists, start Finance Tool Architecture (PRD Ch.10): Domain 1 (Accounts Receivable) first — `get_unpaid_invoices`, `get_overdue_invoices`, `get_invoice`, `search_invoices`, `get_customer_balance` — registered the same way `get_current_date` was this milestone (`ToolSpec`, Pydantic params/result models, registered via `ToolRegistry`).
3. Keep the two-phase pipeline, graceful tool-failure degradation, and structured-logging patterns established this milestone unchanged — real finance tools plug into the exact same `Planner`/`ToolExecutor`/`ChatWorkflow` machinery, no orchestration changes expected.
4. Once ≥2 tools exist, revisit the sequential-only tool execution decision (§4) — PRD Ch.13's parallel-execution guidance becomes relevant.
5. Domain Adapters (PRD Ch.10, "A Design Improvement") — introduce the adapter layer between services and repositories now, before real tools accumulate, so swapping the Finance Simulator for a real ERP later stays a repository/adapter-layer change only.
