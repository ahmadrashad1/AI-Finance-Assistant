# Milestone 2 — Basic AI Chat — Design

Status: Approved (pending final user sign-off on this document)
Date: 2026-07-05
Relates to: `docs/PRD.md` Chapter 16 (Milestone 2), Chapter 8 (AI Architecture),
Chapter 13 (AI Request Lifecycle), Chapter 15 (Frontend Architecture);
`docs/adr/0001-fastapi-as-orchestrator.md`, `docs/adr/0002-two-phase-llm-execution.md`.

## Goal

The assistant behaves like a general chat assistant — conversational, streamed,
with persisted history. **No finance tools yet.** This proves the full
pipeline (frontend → FastAPI → LLM → frontend, with persistence) end to end,
per the Chapter 16 "Hello" walkthrough.

## Scope decisions (resolved during brainstorming)

- **LLM provider:** Anthropic, via the official `anthropic` Python SDK.
  Model: `claude-haiku-4-5` (cheapest current Claude model) — cost-conscious
  choice for pre-revenue development; swapping to a more capable Anthropic
  model later is a one-line config change because the rest of the app depends
  only on an `LLMService` protocol, never the SDK directly.
- **Two-phase LLM execution (ADR-0002):** **Not implemented yet.** ADR-0002's
  split exists to separate tool planning from response generation. Milestone 2
  has no tools to plan — the tool registry stays empty until Milestone 3. A
  trivial Phase 1 with nothing to decide would be pure overhead. Milestone 2
  is therefore a single LLM call (`PromptBuilder` → stream reply). The
  two-phase split gets introduced in Milestone 3 when tool selection becomes
  a real decision.
- **Streaming transport:** Server-Sent Events (SSE) over a plain
  `POST /api/chat` `StreamingResponse` — no WebSocket, no extra infra.
- **Conversation scope:** Full sidebar (per Ch.15), not a single default
  conversation — the brief explicitly asks for conversation history sidebar +
  new-conversation button.
- **"Sessions" table:** Represents an anonymous browser session (no auth
  system exists yet). A session ID is generated client-side, stored in
  `localStorage`, and sent with every request; conversations belong to a
  session so the sidebar can list "my" conversations without real user
  accounts.

## Architecture

```
Browser (localStorage: session_id)
    │
    ▼
Next.js Chat UI (sidebar + message list + input)
    │  POST /api/chat {session_id, conversation_id?, message}  → SSE
    │  GET  /api/chat/conversations?session_id=...
    │  GET  /api/chat/conversations/{id}/messages
    ▼
FastAPI endpoints (backend/app/api/chat.py) — thin, delegate only
    │
    ▼
ChatWorkflow (platform/orchestration/chat_workflow.py)
    Initialize → Validate → Execute → Log → Evaluate → Complete
        Execute:
          1. Upsert session; create conversation if absent
          2. ConversationMemory.get_context_window(conversation_id)
          3. PromptBuilder.build(system_prompt, memory, message)
          4. LLMService.stream_reply(...) — tokens forwarded as SSE
          5. ConversationRepository.add_message() for user + assistant turns
    │
    ├──▶ platform/memory/        (ConversationRepository, ConversationMemory)
    ├──▶ platform/llm/           (LLMService protocol, AnthropicLLMService)
    ├──▶ platform/prompts/       (versioned system prompt)
    └──▶ platform/workflow/      (Workflow lifecycle base class)
    │
    ▼
PostgreSQL — `application` schema: sessions, conversations, messages
```

`platform/tool_registry/` and `domains/finance/` are untouched — still
README-only placeholders. No finance capability, no tool calling this
milestone (Milestone 3 per the roadmap).

## Components

### `platform/workflow/` (first real code)

`Workflow` — an abstract base class with six methods matching the mandatory
lifecycle (`initialize`, `validate`, `execute`, `log`, `evaluate`,
`complete`), plus a `run()` template method that calls them in order and
propagates a request context (request_id, conversation_id) into structured
logs at each step. No workflow may skip a step; `evaluate()` may be a no-op
for workflows without meaningful eval criteria, but the hook must be called.

- **Depends on:** nothing (pure framework).
- **Used by:** `ChatWorkflow`.

### `platform/memory/` (first real code)

- SQLAlchemy models: `Session`, `Conversation`, `Message`
  (`__table_args__ = {"schema": "application"}`).
- `ConversationRepository`: `get_or_create_session(session_id)`,
  `create_conversation(session_id)`, `list_conversations(session_id)`,
  `add_message(conversation_id, role, content)`,
  `get_messages(conversation_id)`.
- **Title generation:** no extra LLM call for this. When persisting the
  first user message of a conversation, the repository sets `title` to that
  message truncated to 50 characters (+ "…" if truncated). Matches Ch.15's
  "generated automatically from the first meaningful user request" without
  adding a second model call per conversation.
- `ConversationMemory`: `get_context_window(conversation_id) -> list[Message]`.
  For M2 this is "last 10 messages, oldest first" — a deliberately simple
  recency window. The method signature and return type are the seam a future
  milestone can replace with semantic/selective retrieval (Ch.13) without
  touching `ChatWorkflow` or `PromptBuilder`.

- **Depends on:** `backend/app/db` (async session), `platform/workflow` (none
  directly — it's a leaf).
- **Used by:** `ChatWorkflow`, `backend/app/api/chat.py` (for the two GET
  endpoints, via the repository directly — reading conversation history is
  not itself an AI request, so it doesn't need the full workflow).

### `platform/llm/` (first real code)

- `LLMService` (Protocol): `async def stream_reply(system: str, history:
  list[dict], message: str) -> AsyncIterator[str]`.
- `AnthropicLLMService(LLMService)`: wraps `anthropic.AsyncAnthropic`,
  calls `client.messages.stream(model=..., system=..., messages=[...])`,
  yields `event.text` for each `text` delta.
- `FakeLLMService(LLMService)` (test-only, in `backend/tests/`): yields a
  fixed token sequence, no network call — used for integration tests and
  eval cases so CI needs no API key.

- **Depends on:** `app.core.config.Settings` (`llm_api_key`, `llm_model`).
- **Used by:** `ChatWorkflow`, injected via FastAPI `Depends` so tests can
  override it (same pattern as M1's `check_database_connection`).

### `platform/prompts/`

- `system_prompt.py`: module with `VERSION = "1.0.0"`, `AUTHOR`, `CHANGELOG`
  (list of version/date/note entries), and `SYSTEM_PROMPT` (the actual text —
  friendly finance-assistant persona, per Ch.8's "good prompt guidance":
  behavior only, no business rules).

### `platform/orchestration/`

- `PromptBuilder`: pure function/class that takes `(system_prompt: str,
  history: list[Message], user_message: str)` and returns the Anthropic
  `messages` list shape (`[{"role": ..., "content": ...}, ...]`) plus the
  `system` string. No I/O — fully unit-testable.
- `ChatWorkflow(Workflow)`: the concrete workflow described in Architecture
  above.

### `backend/app/api/chat.py`

- `POST /api/chat` — body `{session_id: str, conversation_id: str | None,
  message: str}`. Returns `text/event-stream`:
  `data: {"type":"token","content":"..."}` per chunk,
  `data: {"type":"done","conversation_id":"..."}` at the end,
  `data: {"type":"error","message":"..."}` on failure (friendly message from
  the error-category mapping).
- `GET /api/chat/conversations?session_id=...` — sidebar list
  (id, title, last activity).
- `GET /api/chat/conversations/{id}/messages` — full history for reload.

### Frontend (`frontend/`)

- `app/page.tsx` becomes the chat page: sidebar + `ChatWindow`.
- New components under `frontend/components/chat/`: `ConversationSidebar`,
  `MessageList`, `MessageBubble` (markdown via a minimal renderer — no new
  heavy dependency beyond what's needed for basic markdown), `MessageInput`.
- `lib/api-client.ts` gains `streamChat()` (fetch + `ReadableStream` reader,
  parses SSE lines into typed events), `listConversations()`,
  `getConversationMessages()`.
- `session_id` generated once (`crypto.randomUUID()`) and cached in
  `localStorage`; sent on every request.
- Errors from the `error` SSE event render as an inline banner with the
  friendly message — no raw stack traces or "Internal Server Error" text.

## Data flow — one turn, in detail

1. User submits a message. Frontend sends `POST /api/chat` with the current
   `session_id` and `conversation_id` (or `null` for a brand-new chat).
2. `ChatWorkflow.initialize()` builds the request context (request_id from
   middleware, conversation_id if known).
3. `validate()` checks the message is non-empty and within a reasonable
   length; validation failures return a `Validation`-category error, no LLM
   call made.
4. `execute()`:
   a. Upserts the session row (creates if new).
   b. If `conversation_id` is `None`, creates a conversation row and returns
      its id in the `done` event later.
   c. Persists the user's message immediately (so it survives even if the
      LLM call fails).
   d. `ConversationMemory.get_context_window()` — last 10 messages.
   e. `PromptBuilder.build()` — assembles system + history + new message.
   f. `LLMService.stream_reply()` — tokens streamed to the client as they
      arrive, and buffered server-side to persist as the assistant message
      once the stream ends.
5. `log()` — structured log line: timestamp, request_id, conversation_id,
   workflow="chat", severity, component, plus token count and latency.
6. `evaluate()` — no-op hook for M2 (real eval cases run offline against
   `FakeLLMService`, not per-request).
7. `complete()` — closes out the SSE stream with the `done` event.

## Error handling

| Failure | Category | User sees |
|---|---|---|
| Empty/oversized message | Validation | "Please enter a message." |
| DB unavailable | Infrastructure | "Something went wrong on our end. Please try again." |
| Anthropic auth/rate-limit/connection error | AI | "I couldn't process that right now. Please try again." |
| Anything unclassified | Unexpected | Generic friendly message; full detail in server logs only |

All mapped through the existing `app.core.errors` categorization from
Milestone 1 — no new error categories, just new call sites.

## Testing

- **Unit:** `ConversationMemory` (empty conversation, exactly-10, more-than-10
  messages), `PromptBuilder` (correct role assembly, system prompt included
  verbatim), `Workflow` lifecycle (all six steps invoked in order, in a
  minimal concrete subclass used only by the test), `ConversationRepository`
  CRUD against a real test-schema Postgres (per M1's existing DB-test
  convention).
- **Integration:** ASGI test client hits `POST /api/chat` with
  `FakeLLMService` injected via `Depends` override; asserts the SSE event
  sequence, that both messages are persisted, and that `GET
  /api/chat/conversations/{id}/messages` returns them afterward. A second
  test asserts a new conversation is created when `conversation_id` is
  omitted and its id comes back in the `done` event.
- **AI evaluation (minimal, per Ch.17 — full framework is Milestone 8):**
  2–3 deterministic cases in `platform/evaluation/`, run against
  `FakeLLMService` with scripted responses standing in for real model output,
  checking: (1) a friendly greeting produces a non-empty assistant reply,
  (2) conversation history is included in the prompt sent to the LLM service
  (verifies memory wiring), (3) an empty message is rejected before any LLM
  call. This is intentionally lightweight — real prompt-quality evaluation
  needs a live model and lands with the full EDD framework in Milestone 8.

## Acceptance criteria

- `docker compose up -d` + backend + frontend running: open the app, type
  "Hello", see a streamed reply appear token-by-token.
- Refresh the page: the conversation persists and reloads from Postgres.
- Start a new conversation via the sidebar button; switch between
  conversations; each keeps its own history.
- `pytest` (unit + integration) passes without a real `ANTHROPIC_API_KEY`.
- `ruff`, `mypy`, `eslint`, `tsc` all clean, matching the M1 bar.
- No finance tools, no tool calling, no two-phase planning call — confirmed
  absent by design, not just by omission.

## Explicitly out of scope for Milestone 2

- Tool calling / tool registry population (Milestone 3).
- Two-phase planning/response split (introduced meaningfully in Milestone 3).
- Semantic/selective memory retrieval beyond recency (future work; the
  interface is ready for it).
- Full Evaluation-Driven Development framework (Milestone 8).
- Real Anthropic API key wired into CI (kept local/manual; CI uses the fake
  service).
