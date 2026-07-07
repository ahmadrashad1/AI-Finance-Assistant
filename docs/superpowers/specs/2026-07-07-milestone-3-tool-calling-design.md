# Milestone 3 — Tool Calling — Design Spec

**Date:** 2026-07-07
**Status:** Approved for planning

## Goal

Implement the two-phase execution pipeline (ADR-0002) with exactly one
registered tool, `get_current_date()`, to prove the mechanism end to end
before any real finance tool exists. No finance capability lands this
milestone — that's Milestone 4/5, per the existing roadmap.

Reference material: `CLAUDE.md` (non-negotiable rules), `docs/PRD.md`
Chapters 8 (AI Architecture), 9 (Tool & Service Design Principles), 10
(Finance Tool Architecture), 13 (AI Request Lifecycle & Orchestration),
`docs/adr/0001-fastapi-as-orchestrator.md`,
`docs/adr/0002-two-phase-llm-execution.md`,
`docs/adr/0004-tool-registry.md`.

## Architecture Overview

```
User message
    │
    ▼
ChatWorkflow.execute()
    │
    ├── fetch conversation history (ConversationMemory)
    ├── persist user message
    │
    ├── Phase 1: Planner.create_plan(history, message)
    │       │
    │       ▼
    │   Plan { clarification_needed | tool_calls | direct_answer }
    │
    ├── clarification_needed → yield token(text), persist, done, STOP
    │
    ├── tool_calls (or direct_answer, which has none) →
    │       for each tool_call:
    │           yield tool_call SSE event
    │           ToolExecutor.execute(tool_call)
    │               → ToolRegistry lookup
    │               → validate parameters (Pydantic)
    │               → run handler
    │               → ResultValidator.validate_result()
    │               → persist row to application.tool_executions
    │           collect ToolExecutionOutcome
    │
    └── Phase 2: stream_reply(RESPONSE_SYSTEM_PROMPT, history, message+results)
            → yield token events, persist assistant message, done
```

All of this lives in `ai_platform/` (domain-agnostic) except the FastAPI
wiring itself, matching the existing Milestone 2 layering.

## 1. Tool Registry (`ai_platform/tool_registry/`)

- `ToolSpec` (frozen dataclass): `name: str`, `description: str`,
  `parameters_model: type[BaseModel]`, `result_model: type[BaseModel]`,
  `handler: Callable[[BaseModel], Awaitable[BaseModel]]`.
- The JSON schema the planner sees is derived from
  `parameters_model.model_json_schema()` — one source of truth, never
  hand-duplicated.
- `ToolRegistry`:
  - `register(spec: ToolSpec) -> None` (raises on duplicate name — fail
    fast, per ADR-0004's "missing or malformed tool definition should fail
    fast rather than surface as a runtime planner error").
  - `get(name: str) -> ToolSpec | None`
  - `list_specs() -> list[ToolSpec]`
  - `to_planner_json() -> list[dict]` — name/description/parameters-schema
    only. Never exposes `handler` or `result_model` to the prompt.
- Registered once at startup in `backend/app/main.py` (a module-level
  singleton `ToolRegistry` instance, populated before the app accepts
  requests).

### The one tool: `get_current_date`

`ai_platform/tool_registry/tools/get_current_date.py`:
- `GetCurrentDateParams(BaseModel)` — no fields (`model_config =
  ConfigDict(extra="forbid")`).
- `GetCurrentDateResult(BaseModel)` — `date: str` (ISO 8601, e.g.
  `"2026-07-07"`), `day_of_week: str` (e.g. `"Tuesday"`).
- Async handler using `datetime.now(UTC)`.
- Lives in `ai_platform/`, not `domains/finance/tools/` — it's a generic
  infrastructure-proving tool, not a finance capability. `domains/finance/`
  stays README-only until Milestone 4/5.

## 2. Phase 1 — Planner (`ai_platform/orchestration/planner.py`)

- `ToolCall(BaseModel)`: `tool: str`, `parameters: dict[str, Any] = {}`.
- `Plan(BaseModel)`: `clarification_needed: str | None = None`,
  `tool_calls: list[ToolCall] | None = None`, `direct_answer: bool | None =
  None`, with a `model_validator(mode="after")` enforcing **exactly one**
  of the three is set. A plan that sets zero or more than one is a
  validation failure.
- New versioned prompt, `ai_platform/prompts/planning_prompt.py`
  (`VERSION`, `AUTHOR`, `CHANGELOG`, `PLANNING_SYSTEM_PROMPT` template):
  instructs the model to think in business capabilities (Ch.9 Philosophy),
  choose exactly one branch, and output *only* JSON matching the schema —
  no prose, no markdown code fences. The tool registry's
  `to_planner_json()` output is embedded into this prompt at call time.
- **Deliberate deviation from PRD Ch.13 Step 4**: the chapter lists
  "Current Date" as a fixed element of the planning context. This
  milestone intentionally does *not* inject today's date into the
  planner's context, because doing so would let the model answer "what's
  today's date" from context alone and never call `get_current_date()` —
  defeating the one thing this milestone exists to prove. Revisit this
  once a real reason to give the planner a fixed "as of" date emerges
  (e.g. a "days overdue" style tool) — that is a separate, later concern.
- `LLMService` protocol gains one new method:
  `complete(system: str, history: list[dict[str, str]], message: str) ->
  str` — a plain non-streaming completion, used only by the planner.
  - `GroqLLMService.complete()` passes `response_format={"type":
    "json_object"}` (Groq/OpenAI-compatible JSON mode).
  - `AnthropicLLMService.complete()` is a plain non-streaming call relying
    on prompt instructions (Anthropic has no equivalent native JSON mode
    for this SDK version).
  - `FakeLLMService` (test double) gains a matching `complete()` that
    returns a pre-configured canned string, so `Planner` tests and
    `ChatWorkflow` integration tests don't need a real model.
- `Planner.create_plan(history, message) -> Plan`: builds the prompt,
  calls `complete()`, strips markdown code fences defensively, then
  `json.loads` + `Plan.model_validate`. Any parse or validation failure
  raises `AIError` with a friendly message — reuses the existing SSE
  error-event path in `backend/app/api/chat.py`, no new error-handling
  machinery needed there.

## 3. Execution Planner + Tool Executor + `tool_executions` persistence

- New table `application.tool_executions` (Alembic migration, same
  pattern as the Milestone 2 schema): `id (UUID PK)`, `request_id (str)`,
  `conversation_id (UUID FK -> application.conversations.id)`, `tool
  (str)`, `parameters (JSONB)`, `result (JSONB, nullable)`, `duration_ms
  (int)`, `status (str: "success"|"error")`, `error_message (str,
  nullable)`, `created_at`.
- Model lives in `ai_platform/tool_registry/models.py` — it's an execution
  audit log, not conversation memory, so it doesn't belong in
  `ai_platform/memory/models.py`. `backend/alembic/env.py` gets one more
  import line so it registers on `Base.metadata`.
- `ToolExecutionRepository` (`ai_platform/tool_registry/repository.py`):
  `record_execution(request_id, conversation_id, tool, parameters, result,
  duration_ms, status, error_message) -> ToolExecutionModel`.
- `ToolExecutor` (`ai_platform/tool_registry/executor.py`). For each
  `ToolCall`:
  1. Look up the tool in the registry. **Unknown tool name** → treated as
     a failed execution (`status="error"`, `error_message="Unknown tool:
     ..."`), not a crash — the planner hallucinating a tool name shouldn't
     take down the whole turn.
  2. Validate `parameters` against `parameters_model`. **Validation
     failure** → same graceful `status="error"` treatment.
  3. Run the handler, timing it (`duration_ms`, via `time.monotonic()`).
  4. Pass the result through the Result Validator (below). **Validator
     failure** → same graceful `status="error"` treatment.
  5. Persist one row to `tool_executions` regardless of outcome.
  6. Emit one structured log line per execution (`logger.info`, via the
     existing `request_id_ctx_var`/`conversation_id_ctx_var`/
     `workflow_ctx_var` pattern from Milestone 2 — never `extra=`, since
     `JSONFormatter` only reads those ContextVars) carrying `tool`,
     `status`, and `duration_ms` in the message text, so tool execution is
     independently visible in both the database and the logs, per the
     acceptance criteria.
  7. Return a `ToolExecutionOutcome` dataclass (`tool`, `parameters`,
     `result: dict | None`, `status`, `error_message: str | None`,
     `duration_ms`) for Phase 2 to consume.
- This directly implements PRD Ch.13's Error Recovery Branch: a failed
  tool doesn't crash the request — it becomes a fact Phase 2 explains to
  the user ("I couldn't retrieve the date right now because...").
- **Sequential execution only** — there is exactly one registrable tool
  this milestone, so a parallel-execution graph (Ch.13's "Parallel
  Execution" section) would be pure speculation with nothing to
  parallelize. Revisit once ≥2 independently-selectable tools exist
  (Milestone 4+).

## 4. Result Validator (`ai_platform/tool_registry/result_validator.py`)

- One function: `validate_result(spec: ToolSpec, raw_result: dict) ->
  dict`. Re-validates the handler's return value against
  `spec.result_model` — even though the handler is already typed to return
  that model, this catches a handler bug that returns the wrong shape
  before it ever reaches the LLM. Raises `ResultValidationError` on
  mismatch; `ToolExecutor` catches it and converts it into the same
  graceful `status="error"` outcome as any other tool failure.

## 5. Phase 2 — Response Generator

- `ai_platform/prompts/system_prompt.py`'s `SYSTEM_PROMPT` bumps
  `VERSION` to `"1.1.0"` with a changelog entry: adds an explicit
  instruction to use only the provided tool results as fact and never
  state a finance figure or date absent from them — strengthening the
  existing "never invent finance data" line now that real tool output can
  be present in the prompt.
- `stream_reply`'s existing `message` parameter (already separate from
  what gets persisted to the DB — established in Milestone 2) carries the
  extra payload for Phase 2: when there are tool results, the LLM-facing
  message becomes:
  ```
  f"{original_message}\n\n[Tool results — use only this data]\n{json.dumps(results)}"
  ```
  where `results` is a list built from each `ToolExecutionOutcome`:
  `{"tool": outcome.tool, "status": outcome.status, "result":
  outcome.result, "error": outcome.error_message}` (one dict per tool
  call, `result`/`error` are mutually exclusive per outcome). This lets
  the model explain a failed tool ("I couldn't retrieve the date because
  ...") as well as report a successful one. The DB still stores the
  user's original raw message, unchanged. No change needed to
  `PromptBuilder`'s interface.

## 6. `ChatWorkflow` wiring (`ai_platform/orchestration/chat_workflow.py`)

`execute()` is rewritten to:

1. Fetch history (unchanged — must happen before persisting the new user
   message, per the Milestone 2 bug-fix pattern that prevents sending the
   current turn to the LLM twice).
2. Persist the user message.
3. Call `Planner.create_plan(history, message)`.
4. **`clarification_needed` branch**: yield one `token` event containing
   the clarification text, persist it as the assistant message, yield
   `done`, return. No tool execution, no Phase 2 call.
5. **`tool_calls` branch**: for each call, yield a new SSE event
   `{"type": "tool_call", "tool": "<name>"}` *before* invoking it (so the
   UI can show something changed while it runs), then execute it via
   `ToolExecutor`, collecting `ToolExecutionOutcome`s.
6. **`direct_answer` branch**: skip straight to Phase 2 with an empty
   tool-results list — identical code path to the tool_calls branch, just
   nothing to execute. Preserves Milestone 2's small-talk behavior
   unchanged.
7. Phase 2: stream the response as in Milestone 2, yield `token` events,
   persist the assistant message, yield `done`.

### New SSE event: `tool_call`

`ChatEvent` gains an optional `tool: str | None = None` field.
`_format_event` in `backend/app/api/chat.py` includes it when present.

### Frontend (small, contained changes)

- `ChatStreamEvent` (in `frontend/lib/api-client.ts`) gains
  `ChatToolCallEvent { type: "tool_call"; tool: string }`.
- `frontend/app/page.tsx`'s `handleSend` renders a `tool_call` event as a
  transient one-line status message (e.g. "Running get_current_date…")
  that gets replaced once real `token` events start arriving for that
  turn — it is not persisted as a stored message, purely a live-stream
  affordance during that turn.
- No other frontend changes. The sidebar, message list, and markdown
  rendering are untouched.

## 7. Testing Plan

**Unit:**
- `ToolRegistry`: registration, duplicate-name rejection, `to_planner_json()`
  shape.
- `Planner`: `Plan`'s exactly-one-branch validation, accepting valid
  payloads and rejecting payloads with zero or multiple branches set.
- `ResultValidator`: accepts a correct payload, rejects a malformed one.
- `ToolExecutor`: records a `tool_executions` row on success and on each
  failure mode (unknown tool, bad params, handler exception,
  result-validation failure), against a real test DB — mirrors the
  `ConversationRepository` test pattern from Milestone 2.

**Integration (mocked LLM):**
- A fake planner response of `{"tool_calls": [{"tool":
  "get_current_date", "parameters": {}}]}` for Phase 1 and a canned reply
  for Phase 2, asserting: the SSE stream contains a `tool_call` event, the
  final response text contains the date, and a matching row exists in
  `application.tool_executions`. Uses `FakeLLMService` extended with a
  `complete()` canned response.

**AI evaluation cases** (lightweight, per-milestone bar established in
Milestone 2 — not the full Milestone 8 framework):
- "What's today's date?" selects `get_current_date`.
- A greeting ("hi") takes the `direct_answer` branch and never touches the
  registry.
- An ambiguous request can produce a `clarification_needed` plan that
  short-circuits before any tool call.

## Explicitly Out of Scope This Milestone

- Any real finance tool (Milestone 4/5).
- Parallel tool execution / execution graphs beyond a simple sequential
  loop (revisit once ≥2 tools exist).
- Retry logic for malformed Phase 1 JSON output (a parse/validation
  failure surfaces as a friendly SSE error event, same as any other
  `AIError`, per Milestone 2's existing pattern).
- Injecting a fixed "current date" fact into the planner's context (see
  the deliberate deviation noted in §2).
- Full Milestone 8 Evaluation-Driven Development framework (datasets,
  ground truth, regression tracking) — this milestone's AI evaluation
  cases stay as lightweight direct-workflow tests, matching Milestone 2's
  precedent.
