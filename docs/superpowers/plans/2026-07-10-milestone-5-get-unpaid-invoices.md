# Milestone 5 — `get_unpaid_invoices` Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one complete, demonstrable finance vertical slice —
`get_unpaid_invoices()` — end to end: repository query, `InvoiceService`
business logic, a registered `ToolSpec`, Phase-1/Phase-2 prompt updates, and
markdown-table rendering in the chat UI, so "Who still owes us money?" (and
four other phrasings) returns an accurate table backed by real seeded data
with the tool execution logged.

**Architecture:** Strict `endpoint -> workflow -> tool -> service ->
repository -> Postgres` layering (CLAUDE.md). `InvoiceRepository` gets one
new data-access method (`list_by_statuses`, no business meaning attached).
`InvoiceService` (new file) owns the business meaning of "unpaid", computes
`days_outstanding`, and sorts by materiality. The tool
(`domains/finance/tools/get_unpaid_invoices.py`) validates input and shapes
output; it never touches SQL. Because this is the **first** tool that needs
a live database connection (unlike Milestone 3's `get_current_date`), this
plan also fixes the one real architectural gap blocking any DB-backed tool:
`ToolSpec.handler` currently receives only validated parameters, with no way
to reach a request-scoped `AsyncSession`. That gets fixed by introducing a
`ToolContext` (carrying `db`) that `ToolExecutor` builds once per call and
passes to every handler — `get_current_date`'s handler ignores it,
`get_unpaid_invoices`'s handler uses it to construct its own repositories.
This keeps `ToolRegistry` itself DB-free and buildable once at startup
(ADR-0004's fail-fast requirement) unchanged.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest +
pytest-asyncio, Postgres 16, Next.js/React (frontend, no new dependency).

## Global Constraints

- The LLM never accesses PostgreSQL, generates SQL, or knows table/schema
  names (CLAUDE.md, "Data access").
- No keyword matching anywhere in the application — intent routing to
  `get_unpaid_invoices` for all five phrasings must come from the tool's
  description text and the Phase-1 planning prompt, never from Python
  `if "unpaid" in message` style code.
- Layering is one-directional and strict: `endpoints -> workflows ->
  services -> repositories -> PostgreSQL`. Tools never execute SQL, never
  generate prose, never hold state (CLAUDE.md, "Orchestration").
- Every workflow lifecycle step (Initialize -> Validate -> Execute -> Log ->
  Evaluate -> Complete) already exists in `ChatWorkflow` — this milestone
  does not change that lifecycle, only what happens inside `Execute`.
- Structured logging only; every tool execution is persisted via the
  existing `ToolExecutionRepository` (timestamp, request_id,
  conversation_id, tool, status — already wired, do not bypass it).
- Every feature ships with unit tests, integration tests, and an AI
  evaluation case (CLAUDE.md, "Testing and evaluation"). A prompt version
  bump must come with an updated changelog header and updated tests.
- Names reflect business meaning (`InvoiceService`, not `InvoiceHelper` or
  `InvoiceManager`).
- Don't reimplement invoice-status derivation anywhere new —
  `compute_invoice_status` in `domains/finance/repositories/invoice_repository.py`
  stays the single source of truth; this milestone reads `status` as
  already stored, it does not recompute it.
- Don't touch `PaymentRepository.record_payment`'s validation gap or its
  `date.today()` fallback (HANDOFF.md §5) — out of scope, no tool in this
  milestone calls it.
- Don't build the `InvoiceAdapter`/`CustomerAdapter` domain-adapter layer,
  persona packs, or any of the other Milestone-4 "explicitly out of scope"
  items — still not needed for one read-only tool.
- Line length 100 (ruff), `mypy --strict` clean, `from __future__ import
  annotations` at the top of every new/edited Python file (existing
  project convention).

---

## Design Decisions (read before implementing)

These resolve ambiguity in the milestone brief. Follow them exactly so
later tasks stay consistent.

1. **What "unpaid" means** lives in `InvoiceService`, not the repository:
   `UNPAID_STATUSES = ("sent", "partially_paid", "overdue")`. The
   repository only knows how to filter by an arbitrary status list
   (`list_by_statuses`) — it has no opinion on which statuses count as
   "unpaid".
2. **`customer_id` is a business code, not the internal UUID.** The LLM
   never sees schema/PK details, so the tool's `customer_id: str | None`
   parameter is resolved via `CustomerRepository.get_by_code(...)` (e.g.
   `"CUST-0007"`), never the raw `uuid.UUID` primary key. An unresolvable
   `customer_id` raises `ValueError("Customer not found: <id>")`, which
   `ToolExecutor` already turns into a categorized `status="error"` outcome
   — no executor changes needed for this.
3. **`days_outstanding`** = `max(0, (as_of - due_date).days)` — days past
   the due date, zero if not yet due. This mirrors the vocabulary Chapter
   10 already uses for the (future) `get_overdue_invoices(minimum_days=...)`
   tool, so the two stay conceptually aligned.
4. **Materiality sort** = descending by `balance` (largest amount owed
   first) — the plain-English reading of "materiality" for an AR list.
5. **`as_of` for `days_outstanding`** defaults to real `date.today()`
   inside `InvoiceService.get_unpaid_invoices`, overridable via an optional
   keyword arg for deterministic tests. This is a live, ongoing business
   query (not the frozen-clock simulator), so real "today" is correct
   production behavior; it is *not* exposed as a tool parameter (the
   milestone's tool signature only has `customer_id` and `minimum_amount`).
6. **The DB-access architecture gap**: `ToolSpec.handler` today is
   `Callable[[Any], Awaitable[BaseModel]]` — params only, no way to reach a
   database. This plan adds a `ToolContext(db: AsyncSession)` that
   `ToolExecutor` constructs once per `execute()` call (from a `db` session
   it now receives at construction) and passes as a second positional arg
   to every handler. `get_current_date_handler` gains an unused `context`
   parameter; every future DB-backed tool uses `context.db`. This is a
   one-time, small, unavoidable ripple across existing tests (documented
   task by task below) and keeps `ToolRegistry`/`get_tool_registry()`
   exactly as DB-free and cacheable as it is today — `app/main.py`'s
   startup fail-fast call (`get_tool_registry()`) needs **no changes**.
7. **Decimal/date JSON-safety bug fix (prerequisite, not optional)**:
   `result_validator.validate_result` currently does
   `validated.model_dump()` (Python-native types). `get_unpaid_invoices`'s
   result contains `Decimal` and `date` fields; storing those into the
   `tool_executions.result` JSONB column via SQLAlchemy's default
   `json.dumps`-based serializer raises `TypeError`, and the same broken
   dict also feeds `chat_workflow._build_response_message`'s
   `json.dumps(results)` call for the Phase-2 prompt. Fixed once, centrally,
   by changing to `validated.model_dump(mode="json")` (converts `Decimal`
   and `date` to JSON-safe strings). This is Task 2, done before any tool
   that returns non-string data exists.
8. **Frontend markdown tables**: the existing hand-rolled `markdown.ts` (no
   dependency, by original Milestone-2 design choice) is extended with a
   GFM-style pipe-table parser, not replaced with a library. No frontend
   test framework exists in this repo yet (`frontend/package.json` has no
   test script) — introducing one is out of scope for a single rendering
   function; this milestone verifies the renderer manually in a browser
   instead (see Task 11), which is a deliberate, documented scope boundary,
   not an oversight.

---

### Task 1: Thread a `ToolContext` through the tool-execution pipeline

**Files:**
- Modify: `ai_platform/tool_registry/registry.py`
- Modify: `ai_platform/tool_registry/executor.py`
- Modify: `ai_platform/tool_registry/tools/get_current_date.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/test_tool_registry.py`
- Modify: `backend/tests/test_result_validator.py`
- Modify: `backend/tests/test_tool_executor.py`
- Modify: `backend/tests/test_get_current_date_tool.py`
- Modify: `backend/tests/test_chat_workflow.py`
- Modify: `backend/tests/test_chat_eval.py`

**Interfaces:**
- Produces: `ToolContext` dataclass (`db: AsyncSession`) in
  `ai_platform.tool_registry.registry`, importable by every future tool
  handler. `ToolSpec.handler` type becomes
  `Callable[[Any, ToolContext], Awaitable[BaseModel]]`.
  `ToolExecutor.__init__(self, registry: ToolRegistry, execution_repository:
  ToolExecutionRepository, db: AsyncSession) -> None`.

- [ ] **Step 1: Write the failing tests for the new `ToolExecutor` constructor shape**

Update `backend/tests/test_tool_executor.py` — change every dummy handler to
accept `context`, and every `ToolExecutor(...)` construction to pass a third
`db_session` argument:

```python
from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolContext, ToolRegistry, ToolSpec
from ai_platform.tool_registry.repository import ToolExecutionRepository


class _OkParams(BaseModel):
    value: int = 0


class _OkResult(BaseModel):
    doubled: int


async def _ok_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    return _OkResult(doubled=params.value * 2)


class _BrokenResult(BaseModel):
    required_field: str


async def _crashing_handler(params: _OkParams, context: ToolContext) -> _OkResult:
    raise RuntimeError("boom")


async def _make_conversation(db_session: AsyncSession, session_id: str) -> uuid.UUID:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session(session_id)
    conversation = await repo.create_conversation(session_id)
    await db_session.commit()
    return conversation.id


@pytest.mark.asyncio
async def test_execute_records_success(clean_db: None, db_session: AsyncSession) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-1")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-1",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": 21},
    )
    await db_session.commit()

    assert outcome.status == "success"
    assert outcome.result == {"doubled": 42}
    assert outcome.error_message is None

    rows = await execution_repo.list_for_conversation(conversation_id)
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].result == {"doubled": 42}


@pytest.mark.asyncio
async def test_execute_records_unknown_tool_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-2")
    registry = ToolRegistry()
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-2", conversation_id=conversation_id, tool="does_not_exist", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert outcome.result is None
    assert "Unknown tool" in (outcome.error_message or "")

    rows = await execution_repo.list_for_conversation(conversation_id)
    assert rows[0].status == "error"


@pytest.mark.asyncio
async def test_execute_records_invalid_parameters_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-3")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="double_it",
            description="Doubles a number.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-3",
        conversation_id=conversation_id,
        tool="double_it",
        parameters={"value": "not-a-number"},
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert "Invalid parameters" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_execute_records_handler_exception_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-4")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="crasher",
            description="Always raises.",
            parameters_model=_OkParams,
            result_model=_OkResult,
            handler=_crashing_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-4", conversation_id=conversation_id, tool="crasher", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert "boom" in (outcome.error_message or "")


@pytest.mark.asyncio
async def test_execute_records_result_validation_failure_as_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_id = await _make_conversation(db_session, "session-exec-5")
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="mismatched",
            description="Returns the wrong shape.",
            parameters_model=_OkParams,
            result_model=_BrokenResult,
            handler=_ok_handler,
        )
    )
    execution_repo = ToolExecutionRepository(db_session)
    executor = ToolExecutor(registry, execution_repo, db_session)

    outcome = await executor.execute(
        request_id="req-5", conversation_id=conversation_id, tool="mismatched", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert outcome.result is None
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_tool_executor.py -v`
Expected: FAIL — `ToolExecutor.__init__()` takes 3 positional arguments (2
given) / `_ok_handler() missing 1 required positional argument: 'context'`.

- [ ] **Step 3: Add `ToolContext` and update `ToolSpec`'s handler type**

Modify `ai_platform/tool_registry/registry.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ToolContext:
    """Per-call context passed to every tool handler alongside its params.

    Handlers that need the database (most finance tools) build their own
    repositories/services from `context.db`; handlers with no I/O
    dependency (e.g. `get_current_date`) simply ignore it. This keeps
    `ToolRegistry` itself DB-free and buildable once at startup (ADR-0004's
    fail-fast requirement) while still giving DB-backed tools a live,
    request-scoped session at call time.
    """

    db: AsyncSession


@dataclass(frozen=True)
class ToolSpec:
    """Declarative metadata for one tool exposed to the LLM planner.

    `handler` is typed to accept `Any` (not the concrete parameters_model)
    so a registry can hold specs for many different tools with different
    parameter/result models without fighting parameter-type variance.
    """

    name: str
    description: str
    parameters_model: type[BaseModel]
    result_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], Awaitable[BaseModel]]


class DuplicateToolError(ValueError):
    """Raised when a tool name is registered more than once."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def to_planner_json(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters_model.model_json_schema(),
            }
            for spec in self._tools.values()
        ]
```

- [ ] **Step 4: Update `ToolExecutor` to accept `db` and build/pass `ToolContext`**

Modify `ai_platform/tool_registry/executor.py`:

```python
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext, ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.result_validator import ResultValidationError, validate_result

logger = logging.getLogger("ai_platform.tool_executor")


@dataclass
class ToolExecutionOutcome:
    tool: str
    parameters: dict[str, Any]
    result: dict[str, Any] | None
    status: str
    error_message: str | None
    duration_ms: int


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        execution_repository: ToolExecutionRepository,
        db: AsyncSession,
    ) -> None:
        self._registry = registry
        self._execution_repository = execution_repository
        self._db = db

    async def execute(
        self,
        *,
        request_id: str | None,
        conversation_id: uuid.UUID,
        tool: str,
        parameters: dict[str, Any],
    ) -> ToolExecutionOutcome:
        start = time.monotonic()
        result: dict[str, Any] | None = None
        status = "success"
        error_message: str | None = None

        spec = self._registry.get(tool)
        if spec is None:
            status = "error"
            error_message = f"Unknown tool: {tool}"
        else:
            try:
                validated_params = spec.parameters_model.model_validate(parameters)
            except PydanticValidationError as exc:
                status = "error"
                error_message = f"Invalid parameters for tool '{tool}': {exc}"
            else:
                try:
                    context = ToolContext(db=self._db)
                    raw_result = await spec.handler(validated_params, context)
                except Exception as exc:
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"
                else:
                    try:
                        result = validate_result(spec, raw_result.model_dump())
                    except ResultValidationError as exc:
                        status = "error"
                        error_message = str(exc)

        duration_ms = int((time.monotonic() - start) * 1000)

        await self._execution_repository.record_execution(
            request_id=request_id or "unknown",
            conversation_id=conversation_id,
            tool=tool,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        logger.info(
            "tool execution complete: tool=%s status=%s duration_ms=%d", tool, status, duration_ms
        )
        return ToolExecutionOutcome(
            tool=tool,
            parameters=parameters,
            result=result,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )
```

- [ ] **Step 5: Update `get_current_date_handler`'s signature**

Modify `ai_platform/tool_registry/tools/get_current_date.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec


class GetCurrentDateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCurrentDateResult(BaseModel):
    date: str
    day_of_week: str


async def get_current_date_handler(
    params: GetCurrentDateParams, context: ToolContext
) -> GetCurrentDateResult:
    now = datetime.now(UTC)
    return GetCurrentDateResult(date=now.date().isoformat(), day_of_week=now.strftime("%A"))


GET_CURRENT_DATE_TOOL = ToolSpec(
    name="get_current_date",
    description=(
        "Returns today's current date (ISO 8601, e.g. '2026-07-07') and day "
        "of week. Use this whenever the user asks what today's date is."
    ),
    parameters_model=GetCurrentDateParams,
    result_model=GetCurrentDateResult,
    handler=get_current_date_handler,
)
```

- [ ] **Step 6: Wire `db` into `ToolExecutor` at its one production call site**

Modify `backend/app/api/chat.py` — change the line:

```python
    tool_executor = ToolExecutor(tool_registry, execution_repository)
```

to:

```python
    tool_executor = ToolExecutor(tool_registry, execution_repository, db)
```

- [ ] **Step 7: Fix every other test file that constructs a `ToolSpec`/`ToolExecutor`/handler**

Modify `backend/tests/test_tool_registry.py` — update the dummy handler and import:

```python
from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import DuplicateToolError, ToolContext, ToolRegistry, ToolSpec


class _Params(BaseModel):
    value: int = 0


class _Result(BaseModel):
    doubled: int


async def _handler(params: _Params, context: ToolContext) -> _Result:
    return _Result(doubled=params.value * 2)


def _make_spec(name: str = "double_it") -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Doubles a number.",
        parameters_model=_Params,
        result_model=_Result,
        handler=_handler,
    )


def test_register_and_get() -> None:
    registry = ToolRegistry()
    spec = _make_spec()
    registry.register(spec)
    assert registry.get("double_it") is spec
    assert registry.get("missing") is None


def test_register_rejects_duplicate_name() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec())
    with pytest.raises(DuplicateToolError):
        registry.register(_make_spec())


def test_list_specs_returns_all_registered_tools() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec("double_it"))
    registry.register(_make_spec("triple_it"))
    names = {spec.name for spec in registry.list_specs()}
    assert names == {"double_it", "triple_it"}


def test_to_planner_json_exposes_name_description_parameters_only() -> None:
    registry = ToolRegistry()
    registry.register(_make_spec())
    [spec_json] = registry.to_planner_json()
    assert spec_json["name"] == "double_it"
    assert spec_json["description"] == "Doubles a number."
    assert "properties" in spec_json["parameters"]
    assert "value" in spec_json["parameters"]["properties"]
    assert set(spec_json.keys()) == {"name", "description", "parameters"}
```

Modify `backend/tests/test_result_validator.py` — update the dummy handler and import:

```python
from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from ai_platform.tool_registry.result_validator import ResultValidationError, validate_result


class _Params(BaseModel):
    pass


class _Result(BaseModel):
    value: int


async def _handler(params: _Params, context: ToolContext) -> _Result:
    return _Result(value=1)


_SPEC = ToolSpec(
    name="dummy",
    description="dummy tool",
    parameters_model=_Params,
    result_model=_Result,
    handler=_handler,
)


def test_validate_result_accepts_matching_payload() -> None:
    validated = validate_result(_SPEC, {"value": 42})
    assert validated == {"value": 42}


def test_validate_result_rejects_mismatched_payload() -> None:
    with pytest.raises(ResultValidationError):
        validate_result(_SPEC, {"wrong_field": "oops"})
```

Modify `backend/tests/test_get_current_date_tool.py` — pass a `ToolContext` built from the real `db_session` fixture (matches this codebase's "no mocks, real DB fixture" convention):

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from ai_platform.tool_registry.tools.get_current_date import (
    GET_CURRENT_DATE_TOOL,
    GetCurrentDateParams,
    get_current_date_handler,
)


@pytest.mark.asyncio
async def test_handler_returns_iso_date_and_day_of_week(db_session: AsyncSession) -> None:
    result = await get_current_date_handler(GetCurrentDateParams(), ToolContext(db=db_session))
    assert len(result.date) == 10
    assert result.date[4] == "-"
    assert result.date[7] == "-"
    assert result.day_of_week in {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCurrentDateParams(unexpected="value")


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_CURRENT_DATE_TOOL.name == "get_current_date"
    assert "date" in GET_CURRENT_DATE_TOOL.description.lower()
    assert GET_CURRENT_DATE_TOOL.handler is get_current_date_handler
    assert GET_CURRENT_DATE_TOOL.parameters_model is GetCurrentDateParams
```

Modify `backend/tests/test_chat_workflow.py` — in `_make_workflow`, change:

```python
    tool_executor = ToolExecutor(registry, execution_repository)
```

to:

```python
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
```

Modify `backend/tests/test_chat_eval.py` — in `_make_workflow`, change the same line the same way:

```python
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
```

- [ ] **Step 8: Run the full backend test suite to confirm everything passes again**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS, same total minus none removed (this task only changes
signatures, no behavior).

- [ ] **Step 9: Run lint and type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Expected: clean.
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add ai_platform/tool_registry/registry.py ai_platform/tool_registry/executor.py \
  ai_platform/tool_registry/tools/get_current_date.py backend/app/api/chat.py \
  backend/tests/test_tool_registry.py backend/tests/test_result_validator.py \
  backend/tests/test_tool_executor.py backend/tests/test_get_current_date_tool.py \
  backend/tests/test_chat_workflow.py backend/tests/test_chat_eval.py
git commit -m "feat: thread a ToolContext(db) through tool execution

Every tool handler now receives (params, context) instead of just
params, so DB-backed tools can build their own repositories from
context.db. ToolRegistry stays DB-free and buildable once at startup;
get_current_date's handler simply ignores the new argument."
```

---

### Task 2: Fix Decimal/date JSON-safety in `validate_result`

**Files:**
- Modify: `ai_platform/tool_registry/result_validator.py`
- Modify: `backend/tests/test_result_validator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `validate_result(spec, raw_result) -> dict[str, Any]` now
  returns JSON-safe values (str for `Decimal`/`date`/`datetime`) instead of
  native Python objects — every downstream consumer (`ToolExecutionRepository`'s
  JSONB column, `chat_workflow._build_response_message`'s `json.dumps`) relies
  on this.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_result_validator.py`:

```python
import json
from decimal import Decimal


class _DecimalResult(BaseModel):
    amount: Decimal


async def _decimal_handler(params: _Params, context: ToolContext) -> _DecimalResult:
    return _DecimalResult(amount=Decimal("1234.50"))


_DECIMAL_SPEC = ToolSpec(
    name="decimal_dummy",
    description="dummy tool returning Decimal",
    parameters_model=_Params,
    result_model=_DecimalResult,
    handler=_decimal_handler,
)


def test_validate_result_serializes_decimal_as_json_safe_string() -> None:
    validated = validate_result(_DECIMAL_SPEC, {"amount": Decimal("1234.50")})
    assert validated == {"amount": "1234.50"}
    # Must be usable by json.dumps directly - this is the actual bug this
    # test guards against (tool_executions.result JSONB storage and
    # ChatWorkflow's Phase-2 prompt both call json.dumps on this dict).
    json.dumps(validated)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_result_validator.py -v`
Expected: FAIL — `validated == {"amount": "1234.50"}` fails because
`validated == {"amount": Decimal("1234.50")}` (still a `Decimal`, not a
string).

- [ ] **Step 3: Fix `validate_result`**

Modify `ai_platform/tool_registry/result_validator.py` — change the return
line:

```python
def validate_result(spec: ToolSpec, raw_result: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = spec.result_model.model_validate(raw_result)
    except PydanticValidationError as exc:
        raise ResultValidationError(
            f"Tool '{spec.name}' returned a result that doesn't match its declared schema: {exc}"
        ) from exc
    return validated.model_dump(mode="json")
```

(Only the final `return` line changes: `model_dump()` -> `model_dump(mode="json")`.)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_result_validator.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS (existing `get_current_date`/`double_it`-style results are
plain strings/ints, unaffected by `mode="json"`).

- [ ] **Step 6: Commit**

```bash
git add ai_platform/tool_registry/result_validator.py backend/tests/test_result_validator.py
git commit -m "fix: serialize tool results with model_dump(mode='json')

Decimal/date fields (needed by get_unpaid_invoices) aren't JSON-safe
under plain model_dump() - they'd crash both the tool_executions JSONB
write and ChatWorkflow's Phase-2 json.dumps call. mode='json' fixes both
call sites at their single shared source."
```

---

### Task 3: `InvoiceRepository.list_by_statuses`

**Files:**
- Modify: `domains/finance/repositories/invoice_repository.py`
- Modify: `backend/tests/test_invoice_repository.py`

**Interfaces:**
- Produces: `InvoiceRepository.list_by_statuses(self, *, statuses:
  Sequence[str], customer_id: uuid.UUID | None = None, minimum_balance:
  Decimal | None = None) -> list[InvoiceModel]` — pure data access, no
  business meaning attached to which statuses are passed in.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_invoice_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_status_set(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7101")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7101", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7102", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent", "overdue"))
    assert [i.invoice_number for i in results] == ["INV-7101"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_customer_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-7201")
    globex = await _make_customer(db_session, "CUST-7202")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7201", customer_id=acme.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7202", customer_id=globex.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), customer_id=acme.id)
    assert [i.invoice_number for i in results] == ["INV-7201"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_minimum_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7301")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7301", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await repo.create(
        invoice_number="INV-7302", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), minimum_balance=Decimal("100"))
    assert [i.invoice_number for i in results] == ["INV-7302"]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_invoice_repository.py -v`
Expected: FAIL — `AttributeError: 'InvoiceRepository' object has no
attribute 'list_by_statuses'`.

- [ ] **Step 3: Implement `list_by_statuses`**

Modify `domains/finance/repositories/invoice_repository.py` — add the
`Sequence` import and the new method:

```python
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import InvoiceModel
```

(only the `from collections.abc import Sequence` line is new in the import
block; everything else stays as-is)

Then add the method to the `InvoiceRepository` class, after `list_overdue`:

```python
    async def list_by_statuses(
        self,
        *,
        statuses: Sequence[str],
        customer_id: uuid.UUID | None = None,
        minimum_balance: Decimal | None = None,
    ) -> list[InvoiceModel]:
        conditions = [InvoiceModel.status.in_(statuses)]
        if customer_id is not None:
            conditions.append(InvoiceModel.customer_id == customer_id)
        if minimum_balance is not None:
            conditions.append(InvoiceModel.balance >= minimum_balance)
        stmt = select(InvoiceModel).where(*conditions).order_by(InvoiceModel.due_date)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_invoice_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/repositories/invoice_repository.py backend/tests/test_invoice_repository.py
git commit -m "feat: add InvoiceRepository.list_by_statuses

Pure data-access query (status set + optional customer/minimum-balance
filter). Deliberately has no opinion on which statuses mean 'unpaid' -
that business meaning belongs to InvoiceService (Milestone 5)."
```

---

### Task 4: `InvoiceService`

**Files:**
- Create: `domains/finance/services/__init__.py`
- Create: `domains/finance/services/invoice_service.py`
- Modify: `domains/finance/services/README.md`
- Create: `backend/tests/test_invoice_service.py`

**Interfaces:**
- Consumes: `InvoiceRepository.list_by_statuses(...)` (Task 3),
  `CustomerRepository.get_by_code(...)` / `.list_all()` (existing).
- Produces:
  `UNPAID_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")`,
  `@dataclass(frozen=True) class UnpaidInvoice` with fields
  `invoice_number: str, customer_name: str, issue_date: date, due_date:
  date, total: Decimal, balance: Decimal, days_outstanding: int, status:
  str`, and
  `InvoiceService.__init__(self, invoice_repository: InvoiceRepository,
  customer_repository: CustomerRepository) -> None` with
  `async def get_unpaid_invoices(self, *, customer_id: str | None = None,
  minimum_amount: Decimal | None = None, as_of: date | None = None) ->
  list[UnpaidInvoice]` (raises `ValueError` if `customer_id` doesn't
  resolve).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_invoice_service.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.invoice_service import InvoiceService

AS_OF = date(2026, 7, 8)


async def _make_customer(db_session: AsyncSession, code: str, name: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=name, industry="Retail", contact_name="A",
        contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )


def _service(db_session: AsyncSession) -> InvoiceService:
    return InvoiceService(InvoiceRepository(db_session), CustomerRepository(db_session))


@pytest.mark.asyncio
async def test_unpaid_excludes_paid_draft_and_cancelled(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6001", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    for number, status in [("INV-6002", "paid"), ("INV-6003", "draft"), ("INV-6004", "cancelled")]:
        await invoice_repo.create(
            invoice_number=number, customer_id=customer.id, purchase_order_id=None,
            issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status=status,
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert [r.invoice_number for r in results] == ["INV-6001"]


@pytest.mark.asyncio
async def test_partially_paid_and_overdue_are_included(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6101", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    payment_repo = PaymentRepository(db_session)

    partially_paid = await invoice_repo.create(
        invoice_number="INV-6101", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await payment_repo.record_payment(
        invoice_id=partially_paid.id, payment_date=date(2026, 6, 1),
        amount=Decimal("400"), payment_method="check", today=AS_OF,
    )
    await invoice_repo.create(
        invoice_number="INV-6102", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert {r.invoice_number for r in results} == {"INV-6101", "INV-6102"}


@pytest.mark.asyncio
async def test_days_outstanding_is_zero_before_due_date_and_positive_after(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6201", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6201", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        invoice_number="INV-6202", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 6, 20), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)
    by_number = {r.invoice_number: r for r in results}

    assert by_number["INV-6201"].days_outstanding == 0
    assert by_number["INV-6202"].days_outstanding == (AS_OF - date(2026, 6, 20)).days


@pytest.mark.asyncio
async def test_sorts_by_materiality_largest_balance_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6301", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6301", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await invoice_repo.create(
        invoice_number="INV-6302", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert [r.invoice_number for r in results] == ["INV-6302", "INV-6301"]


@pytest.mark.asyncio
async def test_minimum_amount_filters_by_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6401", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6401", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await invoice_repo.create(
        invoice_number="INV-6402", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(
        minimum_amount=Decimal("100"), as_of=AS_OF
    )

    assert [r.invoice_number for r in results] == ["INV-6402"]


@pytest.mark.asyncio
async def test_customer_id_resolves_business_code_to_internal_customer(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-6501", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-6502", "Globex Inc")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6501", customer_id=acme.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        invoice_number="INV-6502", customer_id=globex.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(
        customer_id="CUST-6501", as_of=AS_OF
    )

    assert [r.invoice_number for r in results] == ["INV-6501"]
    assert results[0].customer_name == "Acme Corp"


@pytest.mark.asyncio
async def test_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Customer not found"):
        await _service(db_session).get_unpaid_invoices(customer_id="CUST-DOES-NOT-EXIST")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_invoice_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.services.invoice_service'`.

- [ ] **Step 3: Create the package and the service**

Create `domains/finance/services/__init__.py`:

```python
from __future__ import annotations
```

Create `domains/finance/services/invoice_service.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository

UNPAID_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class UnpaidInvoice:
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class InvoiceService:
    """Business logic for accounts-receivable invoice queries.

    Defines what "unpaid" means (UNPAID_STATUSES), computes
    days_outstanding, and orders results by materiality (largest balance
    first) - InvoiceRepository only knows how to filter rows by status/
    customer/balance, never what those filters mean in business terms.
    """

    def __init__(
        self, invoice_repository: InvoiceRepository, customer_repository: CustomerRepository
    ) -> None:
        self._invoice_repository = invoice_repository
        self._customer_repository = customer_repository

    async def get_unpaid_invoices(
        self,
        *,
        customer_id: str | None = None,
        minimum_amount: Decimal | None = None,
        as_of: date | None = None,
    ) -> list[UnpaidInvoice]:
        resolved_customer_id: uuid.UUID | None = None
        if customer_id is not None:
            customer = await self._customer_repository.get_by_code(customer_id)
            if customer is None:
                raise ValueError(f"Customer not found: {customer_id}")
            resolved_customer_id = customer.id

        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._invoice_repository.list_by_statuses(
            statuses=UNPAID_STATUSES,
            customer_id=resolved_customer_id,
            minimum_balance=minimum_amount,
        )
        customers = await self._customer_repository.list_all()
        customer_names = {customer.id: customer.company_name for customer in customers}

        results = [
            UnpaidInvoice(
                invoice_number=invoice.invoice_number,
                customer_name=customer_names.get(invoice.customer_id, "Unknown customer"),
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                total=invoice.total,
                balance=invoice.balance,
                days_outstanding=max(0, (effective_as_of - invoice.due_date).days),
                status=invoice.status,
            )
            for invoice in invoices
        ]
        results.sort(key=lambda result: result.balance, reverse=True)
        return results
```

- [ ] **Step 4: Update the services README placeholder**

Modify `domains/finance/services/README.md`, replacing the last paragraph:

```markdown
No application logic lives here yet - this is a placeholder for
implementation once the platform skeleton is in place.
```

with:

```markdown
`InvoiceService` (Milestone 5) is the first implementation: it defines
what "unpaid" means (`UNPAID_STATUSES`), computes `days_outstanding`, and
sorts results by materiality. It calls `InvoiceRepository` and
`CustomerRepository` directly - it never executes SQL itself.
```

- [ ] **Step 5: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_invoice_service.py -v`
Expected: PASS.

- [ ] **Step 6: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add domains/finance/services/ backend/tests/test_invoice_service.py
git commit -m "feat: add InvoiceService.get_unpaid_invoices

Business logic layer: defines UNPAID_STATUSES (sent/partially_paid/
overdue), computes days_outstanding relative to due_date, sorts by
materiality (largest balance first), and resolves a customer's business
code to its internal id."
```

---

### Task 5: `get_unpaid_invoices` tool

**Files:**
- Create: `domains/finance/tools/__init__.py`
- Create: `domains/finance/tools/get_unpaid_invoices.py`
- Modify: `domains/finance/tools/README.md`
- Create: `backend/tests/test_get_unpaid_invoices_tool.py`

**Interfaces:**
- Consumes: `InvoiceService` (Task 4), `InvoiceRepository`,
  `CustomerRepository`, `ToolContext`/`ToolSpec` (Task 1).
- Produces: `GetUnpaidInvoicesParams(customer_id: str | None = None,
  minimum_amount: Decimal | None = None)` (extra="forbid", `minimum_amount`
  `ge=0`), `UnpaidInvoiceOut`, `UnpaidInvoicesSummary`,
  `GetUnpaidInvoicesResult(invoices: list[UnpaidInvoiceOut], summary:
  UnpaidInvoicesSummary)`, `async def get_unpaid_invoices_handler(params:
  GetUnpaidInvoicesParams, context: ToolContext) ->
  GetUnpaidInvoicesResult`, and module-level `GET_UNPAID_INVOICES_TOOL:
  ToolSpec`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_get_unpaid_invoices_tool.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.tools.get_unpaid_invoices import (
    GET_UNPAID_INVOICES_TOOL,
    GetUnpaidInvoicesParams,
    get_unpaid_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetUnpaidInvoicesParams(unexpected="value")


def test_params_model_rejects_negative_minimum_amount() -> None:
    with pytest.raises(ValidationError):
        GetUnpaidInvoicesParams(minimum_amount=Decimal("-1"))


def test_params_model_defaults_are_none() -> None:
    params = GetUnpaidInvoicesParams()
    assert params.customer_id is None
    assert params.minimum_amount is None


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_UNPAID_INVOICES_TOOL.name == "get_unpaid_invoices"
    assert GET_UNPAID_INVOICES_TOOL.handler is get_unpaid_invoices_handler
    assert GET_UNPAID_INVOICES_TOOL.parameters_model is GetUnpaidInvoicesParams
    description = GET_UNPAID_INVOICES_TOOL.description.lower()
    for phrase in [
        "who still owes us money",
        "which invoices haven't been paid",
        "outstanding invoices",
        "customers with overdue invoices",
        "show unpaid invoices",
    ]:
        assert phrase in description


@pytest.mark.asyncio
async def test_handler_returns_empty_result_against_empty_db(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(GetUnpaidInvoicesParams(), context)
    assert result.invoices == []
    assert result.summary.count == 0
    assert result.summary.total_outstanding == Decimal("0")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_unpaid_invoices_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.tools.get_unpaid_invoices'`.

- [ ] **Step 3: Create the package and the tool**

Create `domains/finance/tools/__init__.py`:

```python
from __future__ import annotations
```

Create `domains/finance/tools/get_unpaid_invoices.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class GetUnpaidInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    minimum_amount: Decimal | None = Field(default=None, ge=0)


class UnpaidInvoiceOut(BaseModel):
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class UnpaidInvoicesSummary(BaseModel):
    count: int
    total_outstanding: Decimal


class GetUnpaidInvoicesResult(BaseModel):
    invoices: list[UnpaidInvoiceOut]
    summary: UnpaidInvoicesSummary


async def get_unpaid_invoices_handler(
    params: GetUnpaidInvoicesParams, context: ToolContext
) -> GetUnpaidInvoicesResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    unpaid = await service.get_unpaid_invoices(
        customer_id=params.customer_id, minimum_amount=params.minimum_amount
    )
    invoices_out = [
        UnpaidInvoiceOut(
            invoice_number=invoice.invoice_number,
            customer_name=invoice.customer_name,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            total=invoice.total,
            balance=invoice.balance,
            days_outstanding=invoice.days_outstanding,
            status=invoice.status,
        )
        for invoice in unpaid
    ]
    total_outstanding = sum((invoice.balance for invoice in invoices_out), Decimal("0"))
    return GetUnpaidInvoicesResult(
        invoices=invoices_out,
        summary=UnpaidInvoicesSummary(count=len(invoices_out), total_outstanding=total_outstanding),
    )


GET_UNPAID_INVOICES_TOOL = ToolSpec(
    name="get_unpaid_invoices",
    description=(
        "Returns every customer invoice that is still unpaid - status "
        "'sent', 'partially_paid', or 'overdue' (never 'draft' or "
        "'cancelled') - together with the amount still owed (balance), "
        "days outstanding past the due date, and business status. Use "
        "this whenever the user asks who owes money or wants a list of "
        "outstanding/unpaid customer invoices, however they phrase it - "
        "e.g. 'Show unpaid invoices', 'Which invoices haven't been "
        "paid?', 'Outstanding invoices?', 'Who still owes us money?', or "
        "'Customers with overdue invoices'. Optionally filter to one "
        "customer via customer_id (the customer's business code, e.g. "
        "'CUST-0007') and/or to invoices with an outstanding balance at "
        "or above minimum_amount."
    ),
    parameters_model=GetUnpaidInvoicesParams,
    result_model=GetUnpaidInvoicesResult,
    handler=get_unpaid_invoices_handler,
)
```

- [ ] **Step 4: Update the tools README placeholder**

Modify `domains/finance/tools/README.md`, replacing the last paragraph:

```markdown
No application logic lives here yet - this is a placeholder for Milestone 3+
(see the PRD's development roadmap).
```

with:

```markdown
`get_unpaid_invoices` (Milestone 5) is the first implementation: it
validates its own parameters, calls `InvoiceService`, and returns
`{invoices: [...], summary: {count, total_outstanding}}`. It never touches
SQL and never calls another tool.
```

- [ ] **Step 5: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_unpaid_invoices_tool.py -v`
Expected: PASS.

- [ ] **Step 6: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add domains/finance/tools/ backend/tests/test_get_unpaid_invoices_tool.py
git commit -m "feat: add get_unpaid_invoices tool

Validates its own parameters (extra=forbid, minimum_amount>=0), calls
InvoiceService, and returns structured JSON matching the milestone's
{invoices, summary} contract. Description embeds all five phrasings the
Phase-1 planner must map to this tool."
```

---

### Task 6: Register the tool in the platform's tool registry

**Files:**
- Modify: `backend/app/core/tool_registry.py`
- Create: `backend/tests/test_app_tool_registry.py`

**Interfaces:**
- Consumes: `GET_UNPAID_INVOICES_TOOL` (Task 5).
- Produces: no change to `get_tool_registry()`'s public shape (still
  `@lru_cache`, still zero-argument, still called bare in
  `app/main.py`'s startup) - only registers one more tool.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_app_tool_registry.py`:

```python
from __future__ import annotations

from app.core.tool_registry import get_tool_registry


def test_registry_includes_get_current_date_and_get_unpaid_invoices() -> None:
    get_tool_registry.cache_clear()
    registry = get_tool_registry()
    names = {spec.name for spec in registry.list_specs()}
    assert names == {"get_current_date", "get_unpaid_invoices"}
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_app_tool_registry.py -v`
Expected: FAIL — `names == {"get_current_date"}`, missing
`"get_unpaid_invoices"`.

- [ ] **Step 3: Register the tool**

Modify `backend/app/core/tool_registry.py`:

```python
from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    return registry
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_app_tool_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite (confirms `app/main.py`'s startup call still works with no DB)**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS.

- [ ] **Step 6: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/tool_registry.py backend/tests/test_app_tool_registry.py
git commit -m "feat: register get_unpaid_invoices in the platform tool registry

Same registration pattern as get_current_date (Milestone 3) - the
registry stays DB-free and buildable once at startup; the new tool's
handler reaches the database only via ToolContext at call time."
```

---

### Task 7: Integration test — seeded DB through the full tool handler

**Files:**
- Create: `backend/tests/test_get_unpaid_invoices_integration.py`

**Interfaces:**
- Consumes: `get_unpaid_invoices_handler`, `GetUnpaidInvoicesParams` (Task
  5), `ToolContext` (Task 1), `InvoiceRepository`, `CustomerRepository`.

- [ ] **Step 1: Write the integration tests**

Create `backend/tests/test_get_unpaid_invoices_integration.py`:

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_unpaid_invoices import (
    GetUnpaidInvoicesParams,
    get_unpaid_invoices_handler,
)

TODAY = date.today()


async def _make_customer(db_session: AsyncSession, code: str, name: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=name, industry="Retail", contact_name="A",
        contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )


async def _make_invoice(
    db_session: AsyncSession,
    *,
    number: str,
    customer_id: object,
    status: str,
    total: Decimal,
    due_offset_days: int,
) -> None:
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number=number,
        customer_id=customer_id,
        purchase_order_id=None,
        issue_date=TODAY - timedelta(days=60),
        due_date=TODAY + timedelta(days=due_offset_days),
        status=status,
        subtotal=total,
        tax=Decimal("0"),
        total=total,
    )


@pytest.mark.asyncio
async def test_seeded_db_returns_only_unpaid_invoices_with_correct_totals(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8001", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-8002", "Globex Inc")

    await _make_invoice(
        db_session, number="INV-8001", customer_id=acme.id, status="overdue",
        total=Decimal("500.00"), due_offset_days=-10,
    )
    await _make_invoice(
        db_session, number="INV-8002", customer_id=acme.id, status="sent",
        total=Decimal("600.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8003", customer_id=globex.id, status="paid",
        total=Decimal("2000.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8004", customer_id=globex.id, status="draft",
        total=Decimal("300.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8005", customer_id=globex.id, status="cancelled",
        total=Decimal("300.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(GetUnpaidInvoicesParams(), context)

    numbers = {invoice.invoice_number for invoice in result.invoices}
    assert numbers == {"INV-8001", "INV-8002"}
    assert result.summary.count == 2
    assert result.summary.total_outstanding == Decimal("500.00") + Decimal("600.00")
    # Materiality sort: larger outstanding balance (INV-8002, 600) first.
    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8002", "INV-8001"]

    overdue_invoice = next(i for i in result.invoices if i.invoice_number == "INV-8001")
    assert overdue_invoice.days_outstanding == 10
    not_yet_due_invoice = next(i for i in result.invoices if i.invoice_number == "INV-8002")
    assert not_yet_due_invoice.days_outstanding == 0
    assert overdue_invoice.customer_name == "Acme Corp"


@pytest.mark.asyncio
async def test_customer_id_filters_to_one_customer(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8101", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-8102", "Globex Inc")
    await _make_invoice(
        db_session, number="INV-8101", customer_id=acme.id, status="sent",
        total=Decimal("100.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8102", customer_id=globex.id, status="sent",
        total=Decimal("200.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(
        GetUnpaidInvoicesParams(customer_id="CUST-8101"), context
    )

    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8101"]


@pytest.mark.asyncio
async def test_minimum_amount_filters_out_small_balances(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8201", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-8201", customer_id=acme.id, status="sent",
        total=Decimal("50.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8202", customer_id=acme.id, status="sent",
        total=Decimal("5000.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(
        GetUnpaidInvoicesParams(minimum_amount=Decimal("1000.00")), context
    )

    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8202"]


@pytest.mark.asyncio
async def test_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_unpaid_invoices_handler(
            GetUnpaidInvoicesParams(customer_id="CUST-DOES-NOT-EXIST"), context
        )
```

- [ ] **Step 2: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_unpaid_invoices_integration.py -v`
Expected: PASS. (No implementation changes in this task — this is the
integration proof that Tasks 3-6 compose correctly end to end.)

- [ ] **Step 3: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_get_unpaid_invoices_integration.py
git commit -m "test: add seeded-DB integration coverage for get_unpaid_invoices

Exercises the full tool handler (params -> service -> repository ->
Postgres) against hand-seeded rows covering every unpaid/paid/draft/
cancelled status, customer_id filtering, minimum_amount filtering, and
the customer-not-found error path."
```

---

### Task 8: Bump the Phase-1 planning prompt

**Files:**
- Modify: `ai_platform/prompts/planning_prompt.py`
- Modify: `backend/tests/test_planning_prompt.py`

**Interfaces:**
- Produces: `VERSION = "1.1.0"`, updated `CHANGELOG`, and a new rule line
  in `PLANNING_SYSTEM_PROMPT_TEMPLATE` embedding all five phrasings from
  the milestone brief as one worked, paraphrase-invariance example (kept
  generic - no tool name hardcoded - so it stays useful as more tools ship).

- [ ] **Step 1: Write the failing test**

Modify `backend/tests/test_planning_prompt.py`:

```python
from __future__ import annotations

from ai_platform.prompts.planning_prompt import AUTHOR, CHANGELOG, VERSION, build_planning_prompt


def test_planning_prompt_is_versioned() -> None:
    assert VERSION == "1.1.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 2


def test_build_planning_prompt_embeds_tool_specs_and_schema_shapes() -> None:
    prompt = build_planning_prompt('[{"name": "get_current_date"}]')
    assert "get_current_date" in prompt
    assert "clarification_needed" in prompt
    assert "tool_calls" in prompt
    assert "direct_answer" in prompt


def test_build_planning_prompt_teaches_paraphrase_invariant_tool_selection() -> None:
    prompt = build_planning_prompt("[]").lower()
    for phrase in [
        "show unpaid invoices",
        "which invoices haven't been paid",
        "outstanding invoices",
        "who still owes us money",
        "customers with overdue invoices",
    ]:
        assert phrase in prompt
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: FAIL — `VERSION == "1.1.0"` fails (`VERSION` is still `"1.0.0"`);
the paraphrase-invariance test also fails (text not present yet).

- [ ] **Step 3: Update the prompt**

Modify `ai_platform/prompts/planning_prompt.py`:

```python
"""Versioned system prompt for the Phase 1 planner.

Version: 1.1.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-07): Initial version. Three-branch planning contract
    (clarification_needed / tool_calls / direct_answer) for Milestone 3's
    two-phase pipeline.
  - 1.1.0 (2026-07-10): Add a paraphrase-invariance rule with a worked
    accounts-receivable example, now that Milestone 5 ships the first
    data-retrieval tool (get_unpaid_invoices) alongside get_current_date -
    reinforces that intent-to-tool mapping is the model's job, never
    keyword matching in code.
"""

from __future__ import annotations

VERSION = "1.1.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-07): Initial version - three-branch planning contract "
    "(clarification_needed / tool_calls / direct_answer).",
    "1.1.0 (2026-07-10): Add a paraphrase-invariance rule with a worked "
    "accounts-receivable example (get_unpaid_invoices).",
]

PLANNING_SYSTEM_PROMPT_TEMPLATE = (
    "You are the planning stage of an AI finance assistant. "
    "You do not talk to the user directly - you decide what should happen "
    "next, then stop.\n\n"
    "You have access to the following tools:\n{tools_json}\n\n"
    "Given the user's message and conversation history, respond with ONLY a "
    "single JSON object (no prose, no markdown code fences) matching exactly "
    "one of these three shapes:\n\n"
    "1. Ask for clarification when the request is ambiguous:\n"
    '{{"clarification_needed": "<question to ask the user>"}}\n\n'
    "2. Call one or more tools when the request needs data this system can "
    "retrieve:\n"
    '{{"tool_calls": [{{"tool": "<tool name>", "parameters": {{}}}}]}}\n\n'
    "3. Answer directly for small talk or general conversation that needs no "
    "tool and no clarification:\n"
    '{{"direct_answer": true}}\n\n'
    "Rules:\n"
    "- Think in terms of business capabilities, not implementation details.\n"
    "- Choose exactly one of the three shapes above - never combine them, "
    "never leave all three empty.\n"
    "- Only use tool names and parameters from the tool list above. "
    "Never invent a tool.\n"
    "- Match tool selection to business intent, not literal wording - many "
    "different phrasings describe the same request and must select the "
    "same tool. For example, 'Show unpaid invoices', 'Which invoices "
    "haven't been paid?', 'Outstanding invoices?', 'Who still owes us "
    "money?', and 'Customers with overdue invoices' all describe the same "
    "retrieval capability, even though none of the words match each other.\n"
    "- Output ONLY the JSON object. No explanation, no markdown fences, "
    "no extra text.\n"
)


def build_planning_prompt(tools_json: str) -> str:
    return PLANNING_SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/prompts/planning_prompt.py backend/tests/test_planning_prompt.py
git commit -m "feat: bump planning prompt to 1.1.0 for paraphrase-invariant tool selection

Adds one worked example (the five get_unpaid_invoices phrasings from
the Milestone 5 brief) to the Rules section, teaching the planner to
match business intent rather than literal wording - the routing logic
lives entirely in the prompt/LLM, never in application code."
```

---

### Task 9: Bump the Phase-2 system prompt for markdown-table output

**Files:**
- Modify: `ai_platform/prompts/system_prompt.py`
- Modify: `backend/tests/test_system_prompt.py`

**Interfaces:**
- Produces: `VERSION = "1.2.0"`, updated `CHANGELOG`, and an added
  instruction telling the model to render list-shaped tool results as
  markdown tables.

- [ ] **Step 1: Write the failing test**

Modify `backend/tests/test_system_prompt.py`:

```python
from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.2.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 3


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    assert "$" not in SYSTEM_PROMPT


def test_system_prompt_instructs_grounding_in_tool_results() -> None:
    assert "tool results" in SYSTEM_PROMPT.lower()


def test_system_prompt_instructs_markdown_tables_for_lists() -> None:
    assert "markdown table" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_system_prompt.py -v`
Expected: FAIL — `VERSION == "1.2.0"` fails (still `"1.1.0"`); the
markdown-table test fails (text not present yet).

- [ ] **Step 3: Update the prompt**

Modify `ai_platform/prompts/system_prompt.py`:

```python
"""Versioned system prompt for the general chat assistant.

Version: 1.2.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-05): Initial version. General-purpose finance-assistant
    persona, no business rules, no tool-use instructions (Milestone 2 has
    no tools yet).
  - 1.1.0 (2026-07-07): Milestone 3 adds tool-backed responses. Removed the
    "no tools yet" language and added an explicit instruction to use only
    the provided tool results as fact and never state a finance figure or
    date absent from them.
  - 1.2.0 (2026-07-10): Milestone 5 adds get_unpaid_invoices, the first
    tool whose result is a list of records rather than a single value.
    Instructs the model to render such lists as markdown tables so the
    chat UI's table renderer has something to render.
"""

from __future__ import annotations

VERSION = "1.2.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
    "1.1.0 (2026-07-07): Add tool-result grounding instruction now that "
    "get_current_date() can supply real tool output.",
    "1.2.0 (2026-07-10): Instruct the model to render list-shaped tool "
    "results (e.g. unpaid invoices) as markdown tables now that "
    "get_unpaid_invoices exists and the frontend can render them.",
]

SYSTEM_PROMPT = (
    "You are an AI Finance Assistant. Be concise and friendly. "
    "You may be given tool results alongside the conversation - if so, use "
    "only that data as fact. Never state a finance figure or date that is "
    "absent from the provided tool results, and never invent finance data. "
    "If no tool results are provided and the question needs data this "
    "system can't yet retrieve, say so rather than guessing. "
    "When a tool result contains a list of records (e.g. unpaid invoices), "
    "present them as a markdown table - a header row, a separator row, and "
    "one row per record - followed by a one-line summary; don't retype the "
    "list as prose."
)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_system_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/prompts/system_prompt.py backend/tests/test_system_prompt.py
git commit -m "feat: bump system prompt to 1.2.0 to request markdown tables for lists

get_unpaid_invoices is the first tool whose result is a list of
records rather than a single value - the Phase-2 model now knows to
format such lists as markdown tables, matching the frontend's new
table renderer."
```

---

### Task 10: AI smoke tests + HTTP acceptance test

**Files:**
- Modify: `backend/tests/test_chat_eval.py`
- Modify: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `ChatWorkflow`, `Planner`, `FakeLLMService` (existing),
  `GET_UNPAID_INVOICES_TOOL` (Task 5).

- [ ] **Step 1: Write the five-phrasing AI smoke test**

Modify `backend/tests/test_chat_eval.py` — first, register the new tool in
`_make_workflow` and fix its `ToolExecutor` construction:

```python
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        tool_executor=tool_executor,
        request_id="eval-req",
    )
```

Then append this test to the end of the file:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrasing",
    [
        "Show unpaid invoices",
        "Which invoices haven't been paid?",
        "Outstanding invoices?",
        "Who still owes us money?",
        "Customers with overdue invoices",
    ],
)
async def test_eval_unpaid_invoice_phrasings_all_select_get_unpaid_invoices(
    clean_db: None, db_session: AsyncSession, phrasing: str
) -> None:
    """Milestone 5 acceptance: every natural-language phrasing for 'who
    owes us money' must plan get_unpaid_invoices - proves intent routing
    lives in the LLM/prompt layer, not in keyword-matching code."""
    llm_service = FakeLLMService(
        tokens=["Here are the unpaid invoices."],
        plan_response='{"tool_calls": [{"tool": "get_unpaid_invoices", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id=f"eval-unpaid-{phrasing}", message=phrasing)
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_unpaid_invoices"]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_eval.py -v`
Expected: FAIL initially with `DuplicateToolError`/`Unknown tool` if the
registration or `ToolExecutor` args are wrong, or simply not collected yet.
After the edit in Step 1 above, re-run:
Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_eval.py -k unpaid_invoice_phrasings -v`
Expected: PASS immediately (Tasks 1-6 already made the tool real; this task
only adds the test).

- [ ] **Step 3: Write the HTTP acceptance test**

Modify `backend/tests/test_chat_api.py` — append at the end of the file:

```python
@pytest.mark.asyncio
async def test_post_chat_unpaid_invoices_tool_call_logs_execution(clean_db: None) -> None:
    from datetime import date
    from decimal import Decimal

    from app.db.session import get_sessionmaker
    from domains.finance.repositories.customer_repository import CustomerRepository
    from domains.finance.repositories.invoice_repository import InvoiceRepository

    async with get_sessionmaker()() as setup_session:
        customer_repo = CustomerRepository(setup_session)
        customer = await customer_repo.create(
            customer_code="CUST-9001",
            company_name="Acme Testing Ltd.",
            industry="Testing",
            contact_name="A",
            contact_email="a@example.com",
            payment_terms="net_30",
            credit_limit=Decimal("5000.00"),
        )
        invoice_repo = InvoiceRepository(setup_session)
        await invoice_repo.create(
            invoice_number="INV-9001",
            customer_id=customer.id,
            purchase_order_id=None,
            issue_date=date(2026, 6, 1),
            due_date=date(2026, 6, 15),
            status="overdue",
            subtotal=Decimal("900.00"),
            tax=Decimal("100.00"),
            total=Decimal("1000.00"),
        )
        await setup_session.commit()

    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(
        tokens=["You have one unpaid invoice."],
        plan_response='{"tool_calls": [{"tool": "get_unpaid_invoices", "parameters": {}}]}',
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"session_id": "api-session-5", "message": "Who still owes us money?"},
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)

        tool_call_events = [e for e in events if e["type"] == "tool_call"]
        assert [e["tool"] for e in tool_call_events] == ["get_unpaid_invoices"]

        done_events = [e for e in events if e["type"] == "done"]
        conversation_id = uuid.UUID(done_events[0]["conversation_id"])
    finally:
        app.dependency_overrides.pop(get_llm_service, None)

    from sqlalchemy import text

    async with get_sessionmaker()() as session:
        result = await session.execute(
            text(
                "SELECT tool, status, result FROM application.tool_executions "
                "WHERE conversation_id = :conversation_id"
            ),
            {"conversation_id": conversation_id},
        )
        rows = result.all()

    assert len(rows) == 1
    assert rows[0].tool == "get_unpaid_invoices"
    assert rows[0].status == "success"
    assert rows[0].result["summary"]["count"] == 1
    assert rows[0].result["invoices"][0]["invoice_number"] == "INV-9001"
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_api.py -v`
Expected: PASS. This is the closest automated proxy to the milestone's
literal acceptance criterion ("Who still owes us money?" -> accurate data,
tool execution logged) — the remaining gap (a real LLM producing a
markdown-table reply, rendered in a real browser) is closed manually in
Task 11.

- [ ] **Step 5: Run the full suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_chat_eval.py backend/tests/test_chat_api.py
git commit -m "test: add AI smoke tests and HTTP acceptance test for get_unpaid_invoices

Five parametrized eval cases prove every phrasing from the Milestone 5
brief plans get_unpaid_invoices. One HTTP-level test proves the full
stack - seeded invoice, real /api/chat call, tool_call event, and a
persisted tool_executions row with the correct result."
```

---

### Task 11: Frontend — render markdown tables in chat

**Files:**
- Modify: `frontend/components/chat/markdown.ts`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Produces: `renderInlineMarkdown(text: string): string` (same public
  signature, extended behavior) — now detects GFM-style pipe-table blocks
  (header row + `---` separator row + data rows) inside `text` and emits
  an HTML `<table>` for each, while still bolding/code-formatting/escaping
  everything else exactly as before.

- [ ] **Step 1: Rewrite `markdown.ts`**

Modify `frontend/components/chat/markdown.ts`:

```typescript
// Deliberately minimal: escapes HTML first, then applies a handful of
// markdown transforms (bold, inline code, line breaks, and GFM-style pipe
// tables). No new dependency, per the Milestone 2 design doc - Milestone 5
// adds table support by hand rather than pulling in a markdown library,
// since a full-dependency renderer is out of scope for one syntax feature.
// Escaping before transforming is what makes this safe to render with
// dangerouslySetInnerHTML - raw "<script>" etc. in model output becomes
// inert text, not markup.

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInlineSpan(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>");
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function isTableRowLine(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.length > 1;
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((cell) => /^:?-+:?$/.test(cell));
}

function renderTable(headerCells: string[], bodyRows: string[][]): string {
  const thead = `<thead><tr>${headerCells
    .map((cell) => `<th>${renderInlineSpan(escapeHtml(cell))}</th>`)
    .join("")}</tr></thead>`;
  const tbody = `<tbody>${bodyRows
    .map(
      (row) =>
        `<tr>${row
          .map((cell) => `<td>${renderInlineSpan(escapeHtml(cell))}</td>`)
          .join("")}</tr>`,
    )
    .join("")}</tbody>`;
  return `<table>${thead}${tbody}</table>`;
}

export function renderInlineMarkdown(text: string): string {
  const lines = text.split("\n");
  const htmlParts: string[] = [];
  let proseBuffer: string[] = [];

  const flushProse = () => {
    if (proseBuffer.length === 0) {
      return;
    }
    const joined = proseBuffer.join("\n");
    htmlParts.push(renderInlineSpan(escapeHtml(joined)).replace(/\n/g, "<br />"));
    proseBuffer = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const next = lines[i + 1];
    if (
      isTableRowLine(line) &&
      next !== undefined &&
      isTableRowLine(next) &&
      isSeparatorRow(parseTableRow(next))
    ) {
      flushProse();
      const headerCells = parseTableRow(line);
      const bodyRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length && isTableRowLine(lines[j])) {
        bodyRows.push(parseTableRow(lines[j]));
        j++;
      }
      htmlParts.push(renderTable(headerCells, bodyRows));
      i = j;
    } else {
      proseBuffer.push(line);
      i++;
    }
  }
  flushProse();
  return htmlParts.join("");
}
```

- [ ] **Step 2: Add minimal table styling**

Modify `frontend/app/globals.css` — append:

```css
table {
  border-collapse: collapse;
  margin: 0.5rem 0;
  font-size: 0.9rem;
}

th,
td {
  border: 1px solid currentColor;
  padding: 0.25rem 0.5rem;
  text-align: left;
}
```

- [ ] **Step 3: Manually verify in a browser**

There is no frontend test framework in this repo yet (`frontend/package.json`
has no test script) — introducing one is out of scope for a single
rendering function, so this step is a manual, documented verification
instead of an automated one.

Run: `cd frontend && npm run dev`

Then, with the backend also running (`cd backend && .venv/Scripts/uvicorn
app.main:app --reload`) and the database seeded
(`.venv/Scripts/python -m domains.finance.simulator.seed --reset`), open
the chat UI and send: `Who still owes us money?`. Confirm:
- A `Running get_unpaid_invoices…` interim message appears.
- The final assistant reply renders as an actual HTML `<table>` (header
  row bold/bordered, one row per invoice), not a wall of `|`-delimited
  text.
- No other message rendering (plain prose, `**bold**`, `` `code` ``)
  regressed.

- [ ] **Step 4: Typecheck and lint the frontend**

Run: `cd frontend && npm run typecheck`
Run: `cd frontend && npm run lint`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/markdown.ts frontend/app/globals.css
git commit -m "feat: render GFM-style markdown tables in the chat UI

Extends the existing dependency-free markdown renderer (no library
added) to detect header+separator+data-row pipe-table blocks and emit
an HTML table, so Phase-2 replies that list invoices (Milestone 5)
render as an actual table instead of raw pipe-delimited text."
```

---

### Task 12: Full verification pass and HANDOFF.md update

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Run the complete backend verification suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all tests pass, ruff clean, mypy clean (strict mode). Record the
exact passing test count from the pytest summary line.

- [ ] **Step 2: Re-verify the literal acceptance criterion end to end**

Run (from `backend/`):
```bash
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.consistency_check
```
Expected: `Seeded Northwind Manufacturing Ltd. (seed=42).` and `Consistency
check passed: 0 violations.` Then start the backend and frontend dev
servers and repeat Task 11 Step 3's manual browser check against the real
seeded data (not hand-built test fixtures) — this is the actual "in the UI,
'Who still owes us money?' returns an accurate table backed by simulator
data, with the tool execution logged" acceptance criterion. Confirm the
`tool_executions` row exists via:
```sql
SELECT tool, status FROM application.tool_executions ORDER BY created_at DESC LIMIT 1;
```

- [ ] **Step 3: Run the frontend verification suite**

Run: `cd frontend && npm run lint`
Run: `cd frontend && npm run typecheck`
Run: `cd frontend && npm run build`
Expected: all clean.

- [ ] **Step 4: Update `HANDOFF.md`**

Rewrite `HANDOFF.md` following its existing structure (sections 1-7: Current
State, Work Completed This Session, In-Progress Work, Decisions Made, Known
Issues/Failing Tests, Do NOT Do, Next Steps). Update the header line to:

```markdown
# HANDOFF — AI Finance Assistant MVP
Last updated: <today's date> | Current milestone: 5 — get_unpaid_invoices vertical slice | Status: complete
```

In §1, replace the verified-state bullets with this milestone's actual
re-run results (exact pytest pass count from Step 1, the reseed/
consistency-check output from Step 2, ruff/mypy clean confirmation, and the
frontend build/lint/typecheck results from Step 3). In §2, summarize what
was built, in the same file-by-file style as Milestone 4's entry: the
`ToolContext` threading fix (Task 1), the Decimal/date JSON-safety fix
(Task 2), `InvoiceRepository.list_by_statuses` (Task 3), `InvoiceService`
(Task 4), the `get_unpaid_invoices` tool (Task 5), its registry entry (Task
6), the planning/system prompt version bumps (Tasks 8-9), and the frontend
table renderer (Task 11). In §4, record the design decisions from this
plan's "Design Decisions" section (what "unpaid" means, `customer_id` as a
business code, the `days_outstanding`/materiality-sort definitions, the
`ToolContext` architecture change and why it was needed). In §5, note that
`PaymentRepository.record_payment`'s validation gap (from Milestone 4's
HANDOFF) is still untouched and still relevant for any future write-tool.
In §6, add "Don't call a tool handler with only `(params)` — every handler
now takes `(params, context: ToolContext)`, even if it ignores `context`."
In §7, set the next milestone per `docs/PRD.md` Chapter 16 (the remaining
Domain 1 AR tools: `get_overdue_invoices`, `get_invoice`, `search_invoices`,
`get_customer_balance`, `list_overdue_customers`, plus the still-deferred
`InvoiceAdapter`/`CustomerAdapter` layer once ≥2 real tools exist).

- [ ] **Step 5: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 5 completion"
```
