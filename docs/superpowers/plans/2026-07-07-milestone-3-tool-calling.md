# Milestone 3 — Tool Calling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the two-phase execution pipeline (ADR-0002) with exactly
one registered tool, `get_current_date()`, proving the planner → executor →
result-validator → response-generator mechanism end to end before any real
finance tool exists.

**Architecture:** A new `ai_platform/tool_registry/` package holds the
domain-agnostic Tool Registry, Tool Executor, and Result Validator. A new
`ai_platform/orchestration/planner.py` adds the Phase 1 Planner. `ChatWorkflow`
(Milestone 2) is rewired to call the planner first, branch on its three-way
plan (clarification / tool_calls / direct_answer), execute any tool calls
through the registry, and only then generate the final streamed response
(Phase 2). Every tool execution is persisted to a new
`application.tool_executions` table.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2 (tool
parameter/result schemas), `anthropic`/`groq` Python SDKs (Phase 1 planning
completion + Phase 2 streaming), Next.js App Router, TypeScript strict, SSE.

## Global Constraints

- Python 3.12+, full type hints, `ruff` + `mypy --strict` clean (matches
  Milestones 1-2's bar — see `backend/pyproject.toml`).
- The LLM never executes tools itself and never sees SQL, table names, or
  repositories — it only sees the tool registry's name/description/JSON-schema
  view (ADR-0004).
- Every tool call is validated (parameters against the tool's Pydantic model,
  result against its declared result model) before/after execution — a
  malformed planner output or a buggy handler must degrade to a graceful
  `status="error"` outcome, never crash the request (PRD Ch.13 Error Recovery
  Branch).
- Structured JSON logs only, using the existing `request_id_ctx_var` /
  `conversation_id_ctx_var` / `workflow_ctx_var` from `app.core.logging` —
  never `logging.info(..., extra=...)`, since `JSONFormatter` only reads those
  ContextVars.
- Every error surfaces through the existing `app.core.errors` categories
  (Validation/Business/Infrastructure/AI/Unexpected) — no new categories.
- Exactly one tool this milestone: `get_current_date()`. No finance tools, no
  parallel tool execution graph (both deferred — see the design spec's
  "Explicitly Out of Scope" section).
- The planner does NOT receive today's date as a given fact in its context —
  this is deliberate, so that asking "what's today's date" is forced through
  the `get_current_date` tool rather than answered from context (see design
  spec §2).
- Design reference:
  `docs/superpowers/specs/2026-07-07-milestone-3-tool-calling-design.md`.

---

### Task 1: Tool Registry core (`ToolSpec`, `ToolRegistry`)

**Files:**
- Create: `ai_platform/tool_registry/__init__.py` (empty)
- Create: `ai_platform/tool_registry/registry.py`
- Test: `backend/tests/test_tool_registry.py`

**Interfaces:**
- Consumes: nothing (pure, domain-agnostic infrastructure).
- Produces: `ToolSpec` (frozen dataclass: `name: str`, `description: str`,
  `parameters_model: type[BaseModel]`, `result_model: type[BaseModel]`,
  `handler: Callable[[Any], Awaitable[BaseModel]]`); `DuplicateToolError`
  (subclass of `ValueError`); `ToolRegistry` with `register(spec: ToolSpec) ->
  None`, `get(name: str) -> ToolSpec | None`, `list_specs() -> list[ToolSpec]`,
  `to_planner_json() -> list[dict[str, Any]]` (each entry: `name`,
  `description`, `parameters` — the tool's JSON schema, nothing else).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_tool_registry.py`:
```python
from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import DuplicateToolError, ToolRegistry, ToolSpec


class _Params(BaseModel):
    value: int = 0


class _Result(BaseModel):
    doubled: int


async def _handler(params: _Params) -> _Result:
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

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tool_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.tool_registry.registry'`

- [ ] **Step 3: Write the implementation**

`ai_platform/tool_registry/__init__.py`: empty file (0 bytes).

`ai_platform/tool_registry/registry.py`:
```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


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
    handler: Callable[[Any], Awaitable[BaseModel]]


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tool_registry.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/tool_registry/__init__.py ai_platform/tool_registry/registry.py backend/tests/test_tool_registry.py
git commit -m "feat: add ToolSpec and ToolRegistry"
```

---

### Task 2: `get_current_date` tool

**Files:**
- Create: `ai_platform/tool_registry/tools/__init__.py` (empty)
- Create: `ai_platform/tool_registry/tools/get_current_date.py`
- Test: `backend/tests/test_get_current_date_tool.py`

**Interfaces:**
- Consumes: `ToolSpec` (Task 1).
- Produces: `GetCurrentDateParams` (Pydantic model, no fields,
  `extra="forbid"`), `GetCurrentDateResult` (`date: str`, `day_of_week: str`),
  `get_current_date_handler(params: GetCurrentDateParams) ->
  GetCurrentDateResult`, `GET_CURRENT_DATE_TOOL: ToolSpec`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_get_current_date_tool.py`:
```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_platform.tool_registry.tools.get_current_date import (
    GET_CURRENT_DATE_TOOL,
    GetCurrentDateParams,
    get_current_date_handler,
)


@pytest.mark.asyncio
async def test_handler_returns_iso_date_and_day_of_week() -> None:
    result = await get_current_date_handler(GetCurrentDateParams())
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

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_get_current_date_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.tool_registry.tools.get_current_date'`

- [ ] **Step 3: Write the implementation**

`ai_platform/tool_registry/tools/__init__.py`: empty file (0 bytes).

`ai_platform/tool_registry/tools/get_current_date.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolSpec


class GetCurrentDateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCurrentDateResult(BaseModel):
    date: str
    day_of_week: str


async def get_current_date_handler(params: GetCurrentDateParams) -> GetCurrentDateResult:
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_get_current_date_tool.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/tool_registry/tools backend/tests/test_get_current_date_tool.py
git commit -m "feat: add get_current_date tool"
```

---

### Task 3: `tool_executions` table (model + migration + fixture update)

**Files:**
- Create: `ai_platform/tool_registry/models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/<generated>_create_tool_executions_table.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_tool_execution_model.py`

**Interfaces:**
- Consumes: `app.db.base.Base` (existing), `application.conversations` table
  (Milestone 2).
- Produces: `ToolExecutionModel(id: uuid.UUID, request_id: str,
  conversation_id: uuid.UUID, tool: str, parameters: dict, result: dict |
  None, duration_ms: int, status: str, error_message: str | None, created_at:
  datetime)` under Postgres schema `"application"`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_tool_execution_model.py`:
```python
from ai_platform.tool_registry.models import ToolExecutionModel


def test_model_uses_application_schema() -> None:
    assert ToolExecutionModel.__table__.schema == "application"


def test_references_conversation() -> None:
    fk_targets = {fk.target_fullname for fk in ToolExecutionModel.__table__.foreign_keys}
    assert "application.conversations.id" in fk_targets


def test_has_expected_columns() -> None:
    columns = {c.name for c in ToolExecutionModel.__table__.columns}
    assert {
        "id",
        "request_id",
        "conversation_id",
        "tool",
        "parameters",
        "result",
        "duration_ms",
        "status",
        "error_message",
        "created_at",
    } <= columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tool_execution_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.tool_registry.models'`

- [ ] **Step 3: Write the model**

`ai_platform/tool_registry/models.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "application"


class ToolExecutionModel(Base):
    __tablename__ = "tool_executions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tool_execution_model.py -v`
Expected: 3 passed

- [ ] **Step 5: Register the model on `Base.metadata` for Alembic**

In `backend/alembic/env.py`, find this existing line:
```python
from ai_platform.memory import models as _memory_models  # noqa: E402,F401

target_metadata = Base.metadata
```
and change it to:
```python
from ai_platform.memory import models as _memory_models  # noqa: E402,F401
from ai_platform.tool_registry import models as _tool_registry_models  # noqa: E402,F401

target_metadata = Base.metadata
```

- [ ] **Step 6: Generate the migration file**

```bash
cd backend
alembic revision -m "create tool_executions table"
```
This prints the created file path, e.g.
`alembic/versions/<hash>_create_tool_executions_table.py`, with
`down_revision` auto-set to the current head (`daf36d10940a`).

- [ ] **Step 7: Fill in the migration**

Open the generated file and replace its `upgrade()`/`downgrade()` bodies
(keep the auto-generated `revision`, `down_revision`, `branch_labels`,
`depends_on`, and docstring/`Create Date` Alembic already wrote):
```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"),
            nullable=False,
        ),
        sa.Column("tool", sa.String(length=100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="application",
    )


def downgrade() -> None:
    op.drop_table("tool_executions", schema="application")
```

- [ ] **Step 8: Apply the migration against the local dev database**

```bash
docker compose up -d
cd backend
alembic upgrade head
```
Expected: no errors; the command prints the applied revision id.

- [ ] **Step 9: Update the `clean_db` fixture to also truncate `tool_executions`**

In `backend/tests/conftest.py`, find:
```python
        await conn.execute(
            text(
                "TRUNCATE TABLE application.messages, "
                "application.conversations, application.sessions CASCADE"
            )
        )
```
and change it to:
```python
        await conn.execute(
            text(
                "TRUNCATE TABLE application.tool_executions, application.messages, "
                "application.conversations, application.sessions CASCADE"
            )
        )
```

- [ ] **Step 10: Verify the fixture works against the migrated database**

```bash
cd backend
python -c "
import asyncio
from sqlalchemy import text
from app.db.session import get_engine

async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'application' ORDER BY table_name\")
        )
        print([row[0] for row in result])

asyncio.run(main())
"
```
Expected output: `['conversations', 'messages', 'sessions', 'tool_executions']`

- [ ] **Step 11: Commit**

```bash
git add ai_platform/tool_registry/models.py backend/alembic backend/tests/conftest.py backend/tests/test_tool_execution_model.py
git commit -m "feat: add tool_executions table"
```

---

### Task 4: `ToolExecutionRepository`

**Files:**
- Create: `ai_platform/tool_registry/repository.py`
- Test: `backend/tests/test_tool_execution_repository.py`

**Interfaces:**
- Consumes: `ToolExecutionModel` (Task 3), `ConversationRepository` (Milestone
  2, used only in this task's test setup to satisfy the `conversation_id`
  foreign key).
- Produces: `ToolExecutionRepository(db: AsyncSession)` with
  `record_execution(*, request_id: str, conversation_id: uuid.UUID, tool: str,
  parameters: dict[str, Any], result: dict[str, Any] | None, duration_ms:
  int, status: str, error_message: str | None) -> ToolExecutionModel`,
  `list_for_conversation(conversation_id: uuid.UUID) ->
  list[ToolExecutionModel]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_tool_execution_repository.py`:
```python
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.repository import ToolExecutionRepository


@pytest.mark.asyncio
async def test_record_execution_and_list_for_conversation(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-1")
    conversation = await conversation_repo.create_conversation("session-tool-1")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    execution = await repo.record_execution(
        request_id="req-1",
        conversation_id=conversation.id,
        tool="get_current_date",
        parameters={},
        result={"date": "2026-07-07", "day_of_week": "Tuesday"},
        duration_ms=5,
        status="success",
        error_message=None,
    )
    await db_session.commit()

    executions = await repo.list_for_conversation(conversation.id)
    assert [e.id for e in executions] == [execution.id]
    assert executions[0].tool == "get_current_date"
    assert executions[0].status == "success"
    assert executions[0].result == {"date": "2026-07-07", "day_of_week": "Tuesday"}


@pytest.mark.asyncio
async def test_record_execution_stores_error_state(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-2")
    conversation = await conversation_repo.create_conversation("session-tool-2")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    await repo.record_execution(
        request_id="req-2",
        conversation_id=conversation.id,
        tool="unknown_tool",
        parameters={},
        result=None,
        duration_ms=1,
        status="error",
        error_message="Unknown tool: unknown_tool",
    )
    await db_session.commit()

    executions = await repo.list_for_conversation(conversation.id)
    assert executions[0].status == "error"
    assert executions[0].result is None
    assert executions[0].error_message == "Unknown tool: unknown_tool"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tool_execution_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.tool_registry.repository'`

- [ ] **Step 3: Write the implementation**

`ai_platform/tool_registry/repository.py`:
```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.models import ToolExecutionModel


class ToolExecutionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_execution(
        self,
        *,
        request_id: str,
        conversation_id: uuid.UUID,
        tool: str,
        parameters: dict[str, Any],
        result: dict[str, Any] | None,
        duration_ms: int,
        status: str,
        error_message: str | None,
    ) -> ToolExecutionModel:
        execution = ToolExecutionModel(
            id=uuid.uuid4(),
            request_id=request_id,
            conversation_id=conversation_id,
            tool=tool,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )
        self._db.add(execution)
        await self._db.flush()
        return execution

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[ToolExecutionModel]:
        stmt = (
            select(ToolExecutionModel)
            .where(ToolExecutionModel.conversation_id == conversation_id)
            .order_by(ToolExecutionModel.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tool_execution_repository.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/tool_registry/repository.py backend/tests/test_tool_execution_repository.py
git commit -m "feat: add ToolExecutionRepository"
```

---

### Task 5: Result Validator

**Files:**
- Create: `ai_platform/tool_registry/result_validator.py`
- Test: `backend/tests/test_result_validator.py`

**Interfaces:**
- Consumes: `ToolSpec` (Task 1).
- Produces: `ResultValidationError(Exception)`, `validate_result(spec:
  ToolSpec, raw_result: dict[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_result_validator.py`:
```python
from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import ToolSpec
from ai_platform.tool_registry.result_validator import ResultValidationError, validate_result


class _Params(BaseModel):
    pass


class _Result(BaseModel):
    value: int


async def _handler(params: _Params) -> _Result:
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

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_result_validator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.tool_registry.result_validator'`

- [ ] **Step 3: Write the implementation**

`ai_platform/tool_registry/result_validator.py`:
```python
from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ai_platform.tool_registry.registry import ToolSpec


class ResultValidationError(Exception):
    """Raised when a tool handler's return value doesn't match its declared result schema."""


def validate_result(spec: ToolSpec, raw_result: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = spec.result_model.model_validate(raw_result)
    except PydanticValidationError as exc:
        raise ResultValidationError(
            f"Tool '{spec.name}' returned a result that doesn't match its declared schema: {exc}"
        ) from exc
    return validated.model_dump()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_result_validator.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/tool_registry/result_validator.py backend/tests/test_result_validator.py
git commit -m "feat: add tool result validator"
```

---

### Task 6: `ToolExecutor`

**Files:**
- Create: `ai_platform/tool_registry/executor.py`
- Test: `backend/tests/test_tool_executor.py`

**Interfaces:**
- Consumes: `ToolRegistry`, `ToolSpec` (Task 1); `ToolExecutionRepository`
  (Task 4); `ResultValidationError`, `validate_result` (Task 5);
  `ConversationRepository` (Milestone 2, test setup only).
- Produces: `ToolExecutionOutcome` (dataclass: `tool: str`, `parameters:
  dict[str, Any]`, `result: dict[str, Any] | None`, `status: str`
  (`"success"` or `"error"`), `error_message: str | None`, `duration_ms:
  int`); `ToolExecutor(registry: ToolRegistry, execution_repository:
  ToolExecutionRepository)` with `execute(*, request_id: str | None,
  conversation_id: uuid.UUID, tool: str, parameters: dict[str, Any]) ->
  ToolExecutionOutcome`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_tool_executor.py`:
```python
from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry, ToolSpec
from ai_platform.tool_registry.repository import ToolExecutionRepository


class _OkParams(BaseModel):
    value: int = 0


class _OkResult(BaseModel):
    doubled: int


async def _ok_handler(params: _OkParams) -> _OkResult:
    return _OkResult(doubled=params.value * 2)


class _BrokenResult(BaseModel):
    required_field: str


async def _crashing_handler(params: _OkParams) -> _OkResult:
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
    executor = ToolExecutor(registry, execution_repo)

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
    executor = ToolExecutor(registry, execution_repo)

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
    executor = ToolExecutor(registry, execution_repo)

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
    executor = ToolExecutor(registry, execution_repo)

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
    executor = ToolExecutor(registry, execution_repo)

    outcome = await executor.execute(
        request_id="req-5", conversation_id=conversation_id, tool="mismatched", parameters={}
    )
    await db_session.commit()

    assert outcome.status == "error"
    assert outcome.result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tool_executor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.tool_registry.executor'`

- [ ] **Step 3: Write the implementation**

`ai_platform/tool_registry/executor.py`:
```python
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ai_platform.tool_registry.registry import ToolRegistry
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
    def __init__(self, registry: ToolRegistry, execution_repository: ToolExecutionRepository) -> None:
        self._registry = registry
        self._execution_repository = execution_repository

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
                    raw_result = await spec.handler(validated_params)
                    result = validate_result(spec, raw_result.model_dump())
                except ResultValidationError as exc:
                    status = "error"
                    error_message = str(exc)
                except Exception as exc:
                    status = "error"
                    error_message = f"Tool '{tool}' failed: {exc}"

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tool_executor.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/tool_registry/executor.py backend/tests/test_tool_executor.py
git commit -m "feat: add ToolExecutor"
```

---

### Task 7: `LLMService.complete()` for Anthropic, Groq, and the fake

**Files:**
- Modify: `ai_platform/llm/service.py`
- Modify: `backend/tests/test_anthropic_llm_service.py`
- Modify: `backend/tests/test_groq_llm_service.py`
- Modify: `backend/tests/fakes.py`

**Interfaces:**
- Consumes: `app.core.errors.AIError` (existing).
- Produces: `LLMService` protocol gains `complete(system: str, history:
  list[dict[str, str]], message: str) -> str` (non-streaming, full-text
  completion; used only by the Phase 1 planner). `FakeLLMService` gains a
  `plan_response: str = '{"direct_answer": true}'` constructor parameter and
  `last_complete_system` / `last_complete_history` / `last_complete_message`
  attributes recorded by `complete()`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_anthropic_llm_service.py` (the existing
imports and `_FakeStream`/`_fake_request` helpers at the top of the file stay
as-is):
```python
@pytest.mark.asyncio
async def test_complete_returns_full_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    class _FakeTextBlock:
        type = "text"
        text = "Hello world"

    class _FakeMessage:
        content = [_FakeTextBlock()]

    async def fake_create(**kwargs: Any) -> _FakeMessage:
        return _FakeMessage()

    monkeypatch.setattr(service._client.messages, "create", fake_create)

    result = await service.complete("system", [], "hi")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_complete_rate_limit_error_becomes_ai_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    async def fake_create(**kwargs: Any) -> Any:
        raise anthropic.RateLimitError(
            message="rate limited",
            response=httpx.Response(429, request=_fake_request()),
            body=None,
        )

    monkeypatch.setattr(service._client.messages, "create", fake_create)

    with pytest.raises(AIError):
        await service.complete("system", [], "hi")
```

Append to `backend/tests/test_groq_llm_service.py` (existing imports and
helpers at the top of the file stay as-is):
```python
@pytest.mark.asyncio
async def test_complete_returns_message_content(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GroqLLMService(api_key="test-key", model="llama-3.1-8b-instant")

    class _FakeMessage:
        content = '{"direct_answer": true}'

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    async def fake_create(**kwargs: Any) -> _FakeCompletion:
        assert kwargs["response_format"] == {"type": "json_object"}
        return _FakeCompletion()

    monkeypatch.setattr(service._client.chat.completions, "create", fake_create)

    result = await service.complete("system", [], "hi")
    assert result == '{"direct_answer": true}'


@pytest.mark.asyncio
async def test_complete_rate_limit_error_becomes_ai_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GroqLLMService(api_key="test-key", model="llama-3.1-8b-instant")

    async def fake_create(**kwargs: Any) -> Any:
        raise groq.RateLimitError(
            message="rate limited",
            response=httpx.Response(429, request=_fake_request()),
            body=None,
        )

    monkeypatch.setattr(service._client.chat.completions, "create", fake_create)

    with pytest.raises(AIError):
        await service.complete("system", [], "hi")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_anthropic_llm_service.py tests/test_groq_llm_service.py -v`
Expected: FAIL with `AttributeError: 'AnthropicLLMService' object has no
attribute 'complete'` (and the same for `GroqLLMService`)

- [ ] **Step 3: Add `complete()` to the protocol and both providers**

In `ai_platform/llm/service.py`, change the `LLMService` protocol from:
```python
class LLMService(Protocol):
    def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]: ...
```
to:
```python
class LLMService(Protocol):
    def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]: ...

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str: ...
```

Add this method to `AnthropicLLMService` (after `stream_reply`):
```python
    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        messages = [*history, {"role": "user", "content": message}]
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=CHAT_MAX_TOKENS,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
            return "".join(block.text for block in response.content if block.type == "text")
        except anthropic.APIConnectionError as exc:
            raise AIError("I couldn't reach the assistant right now. Please try again.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("The assistant is busy right now. Please try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise AIError("I couldn't process that right now. Please try again.") from exc
```

Add this method to `GroqLLMService` (after `stream_reply`):
```python
    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        messages = [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": message},
        ]
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except groq.APIConnectionError as exc:
            raise AIError("I couldn't reach the assistant right now. Please try again.") from exc
        except groq.RateLimitError as exc:
            raise AIError("The assistant is busy right now. Please try again shortly.") from exc
        except groq.APIStatusError as exc:
            raise AIError("I couldn't process that right now. Please try again.") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_anthropic_llm_service.py tests/test_groq_llm_service.py -v`
Expected: 8 passed

- [ ] **Step 5: Add `complete()` to `FakeLLMService`**

Replace the full contents of `backend/tests/fakes.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator


class FakeLLMService:
    """Test double for LLMService. Records the last call's arguments so
    tests can assert on prompt assembly (system prompt, conversation
    history) without hitting a real LLM provider.
    """

    def __init__(self, tokens: list[str], plan_response: str = '{"direct_answer": true}') -> None:
        self._tokens = tokens
        self._plan_response = plan_response
        self.last_system: str | None = None
        self.last_history: list[dict[str, str]] | None = None
        self.last_message: str | None = None
        self.last_complete_system: str | None = None
        self.last_complete_history: list[dict[str, str]] | None = None
        self.last_complete_message: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.last_system = system
        self.last_history = history
        self.last_message = message
        for token in self._tokens:
            yield token

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        self.last_complete_system = system
        self.last_complete_history = history
        self.last_complete_message = message
        return self._plan_response
```

- [ ] **Step 6: Run the full backend test suite to confirm nothing else broke**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass (the default `plan_response` keeps every existing
`FakeLLMService(tokens=[...])` call site working unchanged).

- [ ] **Step 7: Commit**

```bash
git add ai_platform/llm/service.py backend/tests/test_anthropic_llm_service.py backend/tests/test_groq_llm_service.py backend/tests/fakes.py
git commit -m "feat: add LLMService.complete() for planning-phase calls"
```

---

### Task 8: Versioned planning prompt

**Files:**
- Create: `ai_platform/prompts/planning_prompt.py`
- Test: `backend/tests/test_planning_prompt.py`

**Interfaces:**
- Produces: `VERSION: str`, `AUTHOR: str`, `CHANGELOG: list[str]`,
  `build_planning_prompt(tools_json: str) -> str`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_planning_prompt.py`:
```python
from __future__ import annotations

from ai_platform.prompts.planning_prompt import AUTHOR, CHANGELOG, VERSION, build_planning_prompt


def test_planning_prompt_is_versioned() -> None:
    assert VERSION == "1.0.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 1


def test_build_planning_prompt_embeds_tool_specs_and_schema_shapes() -> None:
    prompt = build_planning_prompt('[{"name": "get_current_date"}]')
    assert "get_current_date" in prompt
    assert "clarification_needed" in prompt
    assert "tool_calls" in prompt
    assert "direct_answer" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_planning_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.prompts.planning_prompt'`

- [ ] **Step 3: Write the implementation**

`ai_platform/prompts/planning_prompt.py`:
```python
"""Versioned system prompt for the Phase 1 planner.

Version: 1.0.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-07): Initial version. Three-branch planning contract
    (clarification_needed / tool_calls / direct_answer) for Milestone 3's
    two-phase pipeline.
"""

from __future__ import annotations

VERSION = "1.0.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-07): Initial version - three-branch planning contract "
    "(clarification_needed / tool_calls / direct_answer).",
]

PLANNING_SYSTEM_PROMPT_TEMPLATE = """You are the planning stage of an AI finance assistant. You do not talk to \
the user directly - you decide what should happen next, then stop.

You have access to the following tools:
{tools_json}

Given the user's message and conversation history, respond with ONLY a \
single JSON object (no prose, no markdown code fences) matching exactly \
one of these three shapes:

1. Ask for clarification when the request is ambiguous:
{{"clarification_needed": "<question to ask the user>"}}

2. Call one or more tools when the request needs data this system can \
retrieve:
{{"tool_calls": [{{"tool": "<tool name>", "parameters": {{}}}}]}}

3. Answer directly for small talk or general conversation that needs no \
tool and no clarification:
{{"direct_answer": true}}

Rules:
- Think in terms of business capabilities, not implementation details.
- Choose exactly one of the three shapes above - never combine them, \
never leave all three empty.
- Only use tool names and parameters from the tool list above. Never \
invent a tool.
- Output ONLY the JSON object. No explanation, no markdown fences, no \
extra text.
"""


def build_planning_prompt(tools_json: str) -> str:
    return PLANNING_SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_planning_prompt.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/prompts/planning_prompt.py backend/tests/test_planning_prompt.py
git commit -m "feat: add versioned planning prompt"
```

---

### Task 9: `Planner`

**Files:**
- Create: `ai_platform/orchestration/planner.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: `LLMService.complete` (Task 7); `HistoryMessage` (Milestone 2);
  `PromptBuilder` (Milestone 2); `build_planning_prompt` (Task 8);
  `ToolRegistry.to_planner_json` (Task 1); `app.core.errors.AIError`
  (existing); `FakeLLMService` (Task 7, test only).
- Produces: `ToolCall` (Pydantic model: `tool: str`, `parameters:
  dict[str, Any]` defaulting to `{}`); `Plan` (Pydantic model:
  `clarification_needed: str | None`, `tool_calls: list[ToolCall] | None`,
  `direct_answer: bool | None`, validated to have exactly one branch set);
  `Planner(llm_service: LLMService, registry: ToolRegistry, prompt_builder:
  PromptBuilder)` with `create_plan(history: list[HistoryMessage], message:
  str) -> Plan`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_planner.py`:
```python
from __future__ import annotations

import pytest

from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.planner import Plan, Planner, ToolCall
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.registry import ToolRegistry
from app.core.errors import AIError
from tests.fakes import FakeLLMService


def test_plan_requires_exactly_one_branch_clarification_only() -> None:
    plan = Plan(clarification_needed="Which invoices?")
    assert plan.clarification_needed == "Which invoices?"


def test_plan_requires_exactly_one_branch_tool_calls_only() -> None:
    plan = Plan(tool_calls=[ToolCall(tool="get_current_date")])
    assert plan.tool_calls is not None
    assert plan.tool_calls[0].tool == "get_current_date"


def test_plan_requires_exactly_one_branch_direct_answer_only() -> None:
    plan = Plan(direct_answer=True)
    assert plan.direct_answer is True


def test_plan_rejects_zero_branches_set() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Plan()


def test_plan_rejects_multiple_branches_set() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Plan(direct_answer=True, clarification_needed="huh?")


@pytest.mark.asyncio
async def test_create_plan_parses_tool_calls_response() -> None:
    llm_service = FakeLLMService(
        tokens=[], plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    )
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    plan = await planner.create_plan([], "What's today's date?")

    assert plan.tool_calls == [ToolCall(tool="get_current_date", parameters={})]


@pytest.mark.asyncio
async def test_create_plan_strips_markdown_code_fences() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response='```json\n{"direct_answer": true}\n```')
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    plan = await planner.create_plan([], "hi")

    assert plan.direct_answer is True


@pytest.mark.asyncio
async def test_create_plan_raises_ai_error_on_malformed_json() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response="not json at all")
    planner = Planner(llm_service, ToolRegistry(), PromptBuilder())

    with pytest.raises(AIError):
        await planner.create_plan([], "hi")


@pytest.mark.asyncio
async def test_create_plan_passes_history_and_tool_specs_to_the_llm() -> None:
    llm_service = FakeLLMService(tokens=[], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    planner = Planner(llm_service, registry, PromptBuilder())
    history = [HistoryMessage(role="user", content="hello")]

    await planner.create_plan(history, "how are you?")

    assert llm_service.last_complete_history == [{"role": "user", "content": "hello"}]
    assert llm_service.last_complete_message == "how are you?"
    assert "direct_answer" in (llm_service.last_complete_system or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'ai_platform.orchestration.planner'`

- [ ] **Step 3: Write the implementation**

`ai_platform/orchestration/planner.py`:
```python
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from pydantic import model_validator

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.planning_prompt import build_planning_prompt
from ai_platform.tool_registry.registry import ToolRegistry
from app.core.errors import AIError


class ToolCall(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    clarification_needed: str | None = None
    tool_calls: list[ToolCall] | None = None
    direct_answer: bool | None = None

    @model_validator(mode="after")
    def _validate_exactly_one_branch(self) -> Plan:
        branches_set = [
            self.clarification_needed is not None,
            bool(self.tool_calls),
            bool(self.direct_answer),
        ]
        if sum(branches_set) != 1:
            raise ValueError(
                "Plan must set exactly one of clarification_needed, tool_calls, direct_answer"
            )
        return self


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


class Planner:
    def __init__(
        self, llm_service: LLMService, registry: ToolRegistry, prompt_builder: PromptBuilder
    ) -> None:
        self._llm_service = llm_service
        self._registry = registry
        self._prompt_builder = prompt_builder

    async def create_plan(self, history: list[HistoryMessage], message: str) -> Plan:
        tools_json = json.dumps(self._registry.to_planner_json(), indent=2)
        system = build_planning_prompt(tools_json)
        prompt = self._prompt_builder.build(system, history)
        raw = await self._llm_service.complete(prompt.system, prompt.messages, message)
        cleaned = _strip_code_fences(raw)
        try:
            data = json.loads(cleaned)
            return Plan.model_validate(data)
        except (json.JSONDecodeError, PydanticValidationError) as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/orchestration/planner.py backend/tests/test_planner.py
git commit -m "feat: add Planner for Phase 1 plan generation"
```

---

### Task 10: Bump the response-phase system prompt to 1.1.0

**Files:**
- Modify: `ai_platform/prompts/system_prompt.py`
- Modify: `backend/tests/test_system_prompt.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `SYSTEM_PROMPT` (unchanged name/shape, updated content),
  `VERSION` now `"1.1.0"`.

- [ ] **Step 1: Update the prompt module**

Replace the full contents of `ai_platform/prompts/system_prompt.py`:
```python
"""Versioned system prompt for the general chat assistant.

Version: 1.1.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-05): Initial version. General-purpose finance-assistant
    persona, no business rules, no tool-use instructions (Milestone 2 has
    no tools yet).
  - 1.1.0 (2026-07-07): Milestone 3 adds tool-backed responses. Removed the
    "no tools yet" language and added an explicit instruction to use only
    the provided tool results as fact and never state a finance figure or
    date absent from them.
"""

from __future__ import annotations

VERSION = "1.1.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
    "1.1.0 (2026-07-07): Add tool-result grounding instruction now that "
    "get_current_date() can supply real tool output.",
]

SYSTEM_PROMPT = (
    "You are an AI Finance Assistant. Be concise and friendly. "
    "You may be given tool results alongside the conversation - if so, use "
    "only that data as fact. Never state a finance figure or date that is "
    "absent from the provided tool results, and never invent finance data. "
    "If no tool results are provided and the question needs data this "
    "system can't yet retrieve, say so rather than guessing."
)
```

- [ ] **Step 2: Update the test's version assertion and add a grounding test**

Replace the full contents of `backend/tests/test_system_prompt.py`:
```python
from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.1.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 2


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    assert "$" not in SYSTEM_PROMPT


def test_system_prompt_instructs_grounding_in_tool_results() -> None:
    assert "tool results" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_system_prompt.py -v`
Expected: 4 passed

- [ ] **Step 4: Commit**

```bash
git add ai_platform/prompts/system_prompt.py backend/tests/test_system_prompt.py
git commit -m "feat: bump system prompt to 1.1.0 for tool-result grounding"
```

---

### Task 11: Rewire `ChatWorkflow` to the two-phase pipeline

**Files:**
- Modify: `ai_platform/orchestration/chat_workflow.py`
- Modify: `backend/tests/test_chat_workflow.py`

**Interfaces:**
- Consumes: `Planner`, `Plan`, `ToolCall` (Task 9); `ToolExecutor`,
  `ToolExecutionOutcome` (Task 6); `SYSTEM_PROMPT` (Task 10); everything else
  from Milestone 2 (`Workflow`, `WorkflowContext`, `ConversationRepository`,
  `ConversationMemory`, `PromptBuilder`, `LLMService`, `ValidationError`,
  `conversation_id_ctx_var`, `workflow_ctx_var`).
- Produces: `ChatWorkflow(repository, memory, prompt_builder, llm_service,
  planner, tool_executor, request_id)` (two new required keyword params
  inserted before `request_id`); `ChatEvent` gains `tool: str | None = None`
  (new event type `"tool_call"` alongside the existing `"token"` / `"done"` /
  `"error"`).

- [ ] **Step 1: Update the failing/changing tests first**

Replace the full contents of `backend/tests/test_chat_workflow.py`:
```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from app.core.errors import ValidationError
from tests.fakes import FakeLLMService


def _make_workflow(
    db_session: AsyncSession, llm_service: FakeLLMService
) -> tuple[ChatWorkflow, ConversationRepository, ToolExecutionRepository]:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository)
    prompt_builder = PromptBuilder()
    planner = Planner(llm_service, registry, prompt_builder)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        tool_executor=tool_executor,
        request_id="req-test",
    )
    return workflow, repository, execution_repository


@pytest.mark.asyncio
async def test_new_conversation_streams_tokens_and_persists_both_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Hel", "lo!"])
    workflow, repository, _execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-1", message="Hi there")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    token_events = [e for e in events if e.type == "token"]
    tool_call_events = [e for e in events if e.type == "tool_call"]
    done_events = [e for e in events if e.type == "done"]
    assert [e.content for e in token_events] == ["Hel", "lo!"]
    assert tool_call_events == []
    assert len(done_events) == 1
    assert done_events[0].conversation_id is not None

    conversation_id = uuid.UUID(done_events[0].conversation_id)
    messages = await repository.get_messages(conversation_id)
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Hi there"),
        ("assistant", "Hello!"),
    ]


@pytest.mark.asyncio
async def test_existing_conversation_includes_prior_history_in_prompt(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Sure."])
    workflow, repository, _execution_repository = _make_workflow(db_session, llm_service)

    await repository.get_or_create_session("session-wf-2")
    conversation = await repository.create_conversation("session-wf-2")
    await repository.add_message(conversation.id, "user", "What's my name?")
    await repository.add_message(conversation.id, "assistant", "I don't know yet.")
    await db_session.commit()

    request = ChatRequest(
        session_id="session-wf-2",
        message="It's Alex.",
        conversation_id=str(conversation.id),
    )
    async for _ in workflow.run(request):
        pass
    await db_session.commit()

    assert llm_service.last_history == [
        {"role": "user", "content": "What's my name?"},
        {"role": "assistant", "content": "I don't know yet."},
    ]
    assert llm_service.last_message == "It's Alex."


@pytest.mark.asyncio
async def test_empty_message_is_rejected_before_any_llm_call(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["should not be used"])
    workflow, _repository, _execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-3", message="   ")
    with pytest.raises(ValidationError):
        async for _ in workflow.run(request):
            pass

    assert llm_service.last_message is None
    assert llm_service.last_complete_message is None


@pytest.mark.asyncio
async def test_context_vars_set_during_run_and_reset_after(
    clean_db: None, db_session: AsyncSession
) -> None:
    from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

    llm_service = FakeLLMService(tokens=["ok"])
    workflow, _repository, _execution_repository = _make_workflow(db_session, llm_service)

    assert conversation_id_ctx_var.get() is None
    assert workflow_ctx_var.get() is None

    seen_workflow_during_run: str | None = None
    seen_conversation_id_during_run: str | None = None
    async for event in workflow.run(ChatRequest(session_id="session-wf-ctx", message="hi")):
        if event.type == "token":
            seen_workflow_during_run = workflow_ctx_var.get()
            seen_conversation_id_during_run = conversation_id_ctx_var.get()
    await db_session.commit()

    assert seen_workflow_during_run == "chat"
    assert seen_conversation_id_during_run is not None
    assert conversation_id_ctx_var.get() is None
    assert workflow_ctx_var.get() is None


@pytest.mark.asyncio
async def test_tool_calls_branch_executes_tool_and_persists_execution_row(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["Today is the date."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    workflow, _repository, execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-4", message="What's today's date?")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_current_date"]

    done_events = [e for e in events if e.type == "done"]
    conversation_id = uuid.UUID(done_events[0].conversation_id or "")

    executions = await execution_repository.list_for_conversation(conversation_id)
    assert len(executions) == 1
    assert executions[0].tool == "get_current_date"
    assert executions[0].status == "success"
    assert executions[0].result is not None
    assert "date" in executions[0].result

    assert llm_service.last_message is not None
    assert "Tool results" in llm_service.last_message


@pytest.mark.asyncio
async def test_clarification_branch_skips_tool_execution_and_phase_two(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["should not be used"],
        plan_response='{"clarification_needed": "Which invoices do you mean?"}',
    )
    workflow, repository, execution_repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-5", message="Show invoices")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    assert [e.type for e in events] == ["token", "done"]
    assert events[0].content == "Which invoices do you mean?"
    assert llm_service.last_message is None

    done_event = events[1]
    conversation_id = uuid.UUID(done_event.conversation_id or "")
    messages = await repository.get_messages(conversation_id)
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Show invoices"),
        ("assistant", "Which invoices do you mean?"),
    ]

    executions = await execution_repository.list_for_conversation(conversation_id)
    assert executions == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chat_workflow.py -v`
Expected: FAIL with `TypeError: ChatWorkflow.__init__() missing 2 required
keyword-only arguments: 'planner' and 'tool_executor'`

- [ ] **Step 3: Rewrite `ChatWorkflow`**

Replace the full contents of `ai_platform/orchestration/chat_workflow.py`:
```python
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextvars import Token
from dataclasses import dataclass

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.system_prompt import SYSTEM_PROMPT
from ai_platform.tool_registry.executor import ToolExecutionOutcome, ToolExecutor
from ai_platform.workflow.base import Workflow, WorkflowContext
from app.core.errors import ValidationError
from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

logger = logging.getLogger("ai_platform.chat")


@dataclass
class ChatRequest:
    session_id: str
    message: str
    conversation_id: str | None = None


@dataclass
class ChatEvent:
    type: str  # "token" | "tool_call" | "done" | "error"
    content: str | None = None
    conversation_id: str | None = None
    message: str | None = None
    tool: str | None = None


def _build_response_message(message: str, outcomes: list[ToolExecutionOutcome]) -> str:
    if not outcomes:
        return message
    results = [
        {
            "tool": outcome.tool,
            "status": outcome.status,
            "result": outcome.result,
            "error": outcome.error_message,
        }
        for outcome in outcomes
    ]
    return f"{message}\n\n[Tool results — use only this data]\n{json.dumps(results)}"


class ChatWorkflow(Workflow[ChatRequest, ChatEvent]):
    name = "chat"

    def __init__(
        self,
        repository: ConversationRepository,
        memory: ConversationMemory,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        planner: Planner,
        tool_executor: ToolExecutor,
        request_id: str | None,
    ) -> None:
        self._repository = repository
        self._memory = memory
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service
        self._planner = planner
        self._tool_executor = tool_executor
        self._request_id = request_id

    def initialize(self, input_data: ChatRequest) -> WorkflowContext:
        return WorkflowContext(
            request_id=self._request_id, conversation_id=input_data.conversation_id
        )

    def validate(self, input_data: ChatRequest, context: WorkflowContext) -> None:
        if not input_data.message.strip():
            raise ValidationError("Please enter a message.")

    async def execute(
        self, input_data: ChatRequest, context: WorkflowContext
    ) -> AsyncIterator[ChatEvent]:
        workflow_token = workflow_ctx_var.set(self.name)
        conversation_token: Token[str | None] | None = None
        try:
            await self._repository.get_or_create_session(input_data.session_id)

            if input_data.conversation_id is None:
                conversation = await self._repository.create_conversation(input_data.session_id)
                conversation_id = conversation.id
            else:
                conversation_id = uuid.UUID(input_data.conversation_id)
            context.conversation_id = str(conversation_id)
            conversation_token = conversation_id_ctx_var.set(context.conversation_id)

            history = await self._memory.get_context_window(conversation_id)
            await self._repository.add_message(conversation_id, "user", input_data.message)

            plan = await self._planner.create_plan(history, input_data.message)

            if plan.clarification_needed is not None:
                yield ChatEvent(type="token", content=plan.clarification_needed)
                await self._repository.add_message(
                    conversation_id, "assistant", plan.clarification_needed
                )
                yield ChatEvent(type="done", conversation_id=str(conversation_id))
                return

            outcomes: list[ToolExecutionOutcome] = []
            for tool_call in plan.tool_calls or []:
                yield ChatEvent(type="tool_call", tool=tool_call.tool)
                outcome = await self._tool_executor.execute(
                    request_id=self._request_id,
                    conversation_id=conversation_id,
                    tool=tool_call.tool,
                    parameters=tool_call.parameters,
                )
                outcomes.append(outcome)

            prompt = self._prompt_builder.build(SYSTEM_PROMPT, history)
            llm_message = _build_response_message(input_data.message, outcomes)

            assistant_reply: list[str] = []
            async for token in self._llm_service.stream_reply(
                prompt.system, prompt.messages, llm_message
            ):
                assistant_reply.append(token)
                yield ChatEvent(type="token", content=token)

            await self._repository.add_message(
                conversation_id, "assistant", "".join(assistant_reply)
            )
            yield ChatEvent(type="done", conversation_id=str(conversation_id))
        finally:
            if conversation_token is not None:
                conversation_id_ctx_var.reset(conversation_token)
            workflow_ctx_var.reset(workflow_token)

    def log(self, context: WorkflowContext, events: list[ChatEvent]) -> None:
        token_count = sum(1 for e in events if e.type == "token")
        tool_call_count = sum(1 for e in events if e.type == "tool_call")
        logger.info("chat turn complete: %d tokens, %d tool calls", token_count, tool_call_count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_workflow.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/orchestration/chat_workflow.py backend/tests/test_chat_workflow.py
git commit -m "feat: rewire ChatWorkflow to the two-phase planning/execution pipeline"
```

---

### Task 12: Wire FastAPI (tool registry startup, `/api/chat` dependencies)

**Files:**
- Create: `backend/app/core/tool_registry.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `ToolRegistry` (Task 1); `GET_CURRENT_DATE_TOOL` (Task 2);
  `Planner` (Task 9); `ToolExecutor` (Task 6); `ToolExecutionRepository`
  (Task 4); everything already wired in `chat.py` from Milestone 2.
- Produces: `app.core.tool_registry.get_tool_registry() -> ToolRegistry`
  (`lru_cache`d, mirrors `get_settings()`'s pattern); `POST /api/chat`'s SSE
  payload gains a `tool` field on `tool_call` events.

- [ ] **Step 1: Add the tool registry dependency**

`backend/app/core/tool_registry.py`:
```python
from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    return registry
```

- [ ] **Step 2: Register the tool registry at startup**

In `backend/app/main.py`, change:
```python
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(title="AI Employee Platform", version="0.1.0")
```
to:
```python
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.tool_registry import get_tool_registry
from app.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    # Forces tool registration to happen now, at startup, rather than lazily
    # on the first chat request - a malformed tool definition should fail
    # fast (ADR-0004), not surface as a runtime planner error.
    get_tool_registry()

    application = FastAPI(title="AI Employee Platform", version="0.1.0")
```

- [ ] **Step 3: Wire `Planner`/`ToolExecutor` into `POST /api/chat`**

In `backend/app/api/chat.py`, change the imports from:
```python
from ai_platform.llm.service import AnthropicLLMService, GroqLLMService, LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx_var
from app.db.session import get_db_session
```
to:
```python
from ai_platform.llm.service import AnthropicLLMService, GroqLLMService, LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx_var
from app.core.tool_registry import get_tool_registry
from app.db.session import get_db_session
```

Change `_format_event` from:
```python
def _format_event(event: ChatEvent) -> str:
    payload: dict[str, str | None] = {"type": event.type}
    if event.content is not None:
        payload["content"] = event.content
    if event.conversation_id is not None:
        payload["conversation_id"] = event.conversation_id
    if event.message is not None:
        payload["message"] = event.message
    return f"data: {json.dumps(payload)}\n\n"
```
to:
```python
def _format_event(event: ChatEvent) -> str:
    payload: dict[str, str | None] = {"type": event.type}
    if event.content is not None:
        payload["content"] = event.content
    if event.conversation_id is not None:
        payload["conversation_id"] = event.conversation_id
    if event.message is not None:
        payload["message"] = event.message
    if event.tool is not None:
        payload["tool"] = event.tool
    return f"data: {json.dumps(payload)}\n\n"
```

Change `post_chat` from:
```python
@router.post("/chat")
async def post_chat(
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    llm_service: LLMService = Depends(get_llm_service),
) -> StreamingResponse:
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id=request_id_ctx_var.get(),
    )
```
to:
```python
@router.post("/chat")
async def post_chat(
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    llm_service: LLMService = Depends(get_llm_service),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> StreamingResponse:
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    prompt_builder = PromptBuilder()
    execution_repository = ToolExecutionRepository(db)
    tool_executor = ToolExecutor(tool_registry, execution_repository)
    planner = Planner(llm_service, tool_registry, prompt_builder)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        tool_executor=tool_executor,
        request_id=request_id_ctx_var.get(),
    )
```

(The rest of `chat.py` — `ChatMessageRequest`, `ConversationSummary`,
`MessageOut`, `get_llm_service`, the `event_stream` closure inside
`post_chat`, `list_conversations`, `get_conversation_messages` — is
unchanged.)

- [ ] **Step 4: Add the tool-call integration test**

In `backend/tests/test_chat_api.py`, add `import uuid` to the top imports
(alongside the existing `import json`), then append this test at the end of
the file:
```python
@pytest.mark.asyncio
async def test_post_chat_tool_call_returns_tool_call_event_and_persists_execution(
    clean_db: None,
) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(
        tokens=["Today is 2026-07-07."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"session_id": "api-session-4", "message": "What's today's date?"},
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)

        tool_call_events = [e for e in events if e["type"] == "tool_call"]
        assert [e["tool"] for e in tool_call_events] == ["get_current_date"]

        token_events = [e for e in events if e["type"] == "token"]
        assert "".join(e["content"] for e in token_events) == "Today is 2026-07-07."

        done_events = [e for e in events if e["type"] == "done"]
        conversation_id = uuid.UUID(done_events[0]["conversation_id"])
    finally:
        app.dependency_overrides.pop(get_llm_service, None)

    from sqlalchemy import text

    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        result = await session.execute(
            text(
                "SELECT tool, status FROM application.tool_executions "
                "WHERE conversation_id = :conversation_id"
            ),
            {"conversation_id": conversation_id},
        )
        rows = result.all()

    assert len(rows) == 1
    assert rows[0].tool == "get_current_date"
    assert rows[0].status == "success"
```

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Smoke-test manually**

```bash
docker compose up -d
cd backend
uvicorn app.main:app --reload
```
In another terminal:
```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test-m3", "message": "What is today'"'"'s date?"}'
```
Expected (with a real `LLM_API_KEY` set): a `tool_call` event naming
`get_current_date`, then streamed `token` events whose text mentions the
date, then a `done` event.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/tool_registry.py backend/app/main.py backend/app/api/chat.py backend/tests/test_chat_api.py
git commit -m "feat: wire tool registry and two-phase pipeline into POST /api/chat"
```

---

### Task 13: AI evaluation cases for the two-phase pipeline

**Files:**
- Modify: `backend/tests/test_chat_eval.py`

**Interfaces:**
- Consumes: `ChatWorkflow` (Task 11, new constructor signature); `Planner`
  (Task 9); `ToolExecutor`, `ToolExecutionRepository` (Tasks 4/6);
  `ToolRegistry`, `GET_CURRENT_DATE_TOOL` (Tasks 1/2).

- [ ] **Step 1: Replace the full contents of the eval test file**

`backend/tests/test_chat_eval.py`:
```python
"""Minimal AI evaluation cases for Milestone 2/3's chat behavior.

These are not a substitute for the full Evaluation-Driven Development
framework (Milestone 8) - they exist to satisfy CLAUDE.md's "every feature
ships with ... AI evaluation cases" for this milestone's scope, using
FakeLLMService so they run deterministically in CI without a live model.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository)
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


@pytest.mark.asyncio
async def test_eval_greeting_produces_non_empty_reply(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A friendly greeting must produce a non-empty assistant reply."""
    llm_service = FakeLLMService(tokens=["Hello", "! How can I help?"])
    workflow = _make_workflow(db_session, llm_service)

    events: list[ChatEvent] = [
        e async for e in workflow.run(ChatRequest(session_id="eval-session-1", message="Hello"))
    ]
    await db_session.commit()

    reply = "".join(e.content or "" for e in events if e.type == "token")
    assert reply.strip() != ""


@pytest.mark.asyncio
async def test_eval_conversation_history_reaches_the_prompt(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Prior turns must be visible to the LLM service on the next turn -
    verifies the memory wiring, not just that a reply comes back."""
    llm_service = FakeLLMService(tokens=["ok"])
    workflow = _make_workflow(db_session, llm_service)

    conversation_id: str | None = None
    async for event in workflow.run(
        ChatRequest(session_id="eval-session-2", message="My favorite color is blue.")
    ):
        if event.type == "done":
            conversation_id = event.conversation_id
    await db_session.commit()
    assert conversation_id is not None

    async for _ in workflow.run(
        ChatRequest(
            session_id="eval-session-2",
            message="What's my favorite color?",
            conversation_id=conversation_id,
        )
    ):
        pass
    await db_session.commit()

    assert llm_service.last_history is not None
    assert any("blue" in m["content"].lower() for m in llm_service.last_history)


@pytest.mark.asyncio
async def test_eval_empty_message_never_reaches_the_llm(
    clean_db: None, db_session: AsyncSession
) -> None:
    """An empty message must be rejected before any model call - prevents
    wasted API spend and matches the 'no unsupported assumptions' AI
    responsibility from Ch.8."""
    from app.core.errors import ValidationError

    llm_service = FakeLLMService(tokens=["should never appear"])
    workflow = _make_workflow(db_session, llm_service)

    with pytest.raises(ValidationError):
        async for _ in workflow.run(ChatRequest(session_id="eval-session-3", message="")):
            pass

    assert llm_service.last_message is None


@pytest.mark.asyncio
async def test_eval_asking_for_the_date_selects_get_current_date_tool(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Asking what today's date is must select the get_current_date tool,
    not answer from context - this is the one thing Milestone 3 exists to
    prove."""
    llm_service = FakeLLMService(
        tokens=["It's July 7th, 2026."],
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="eval-session-4", message="What's today's date?")
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_current_date"]


@pytest.mark.asyncio
async def test_eval_greeting_takes_direct_answer_branch(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A greeting needs no tool - the planner must choose direct_answer,
    never touching the tool registry."""
    llm_service = FakeLLMService(tokens=["Hi there!"], plan_response='{"direct_answer": true}')
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e async for e in workflow.run(ChatRequest(session_id="eval-session-5", message="hi"))
    ]
    await db_session.commit()

    assert [e for e in events if e.type == "tool_call"] == []
    reply = "".join(e.content or "" for e in events if e.type == "token")
    assert reply.strip() != ""


@pytest.mark.asyncio
async def test_eval_ambiguous_request_can_short_circuit_with_clarification(
    clean_db: None, db_session: AsyncSession
) -> None:
    """An ambiguous request must be able to stop at a clarifying question
    before any tool executes."""
    llm_service = FakeLLMService(
        tokens=["should not be used"],
        plan_response='{"clarification_needed": "Which invoices do you mean?"}',
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="eval-session-6", message="Show invoices")
        )
    ]
    await db_session.commit()

    assert [e.type for e in events] == ["token", "done"]
    assert events[0].content == "Which invoices do you mean?"
    assert uuid.UUID(events[1].conversation_id or "")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_eval.py -v`
Expected: 6 passed

- [ ] **Step 3: Run the full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_chat_eval.py
git commit -m "test: add AI evaluation cases for the two-phase pipeline"
```

---

### Task 14: Frontend `tool_call` event handling

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: existing `ChatStreamEvent` union, `streamChat` (Milestone 2).
- Produces: `ChatToolCallEvent { type: "tool_call"; tool: string }` added to
  the `ChatStreamEvent` union; `page.tsx` shows a transient status line while
  a tool call is in flight.

- [ ] **Step 1: Extend `ChatStreamEvent`**

In `frontend/lib/api-client.ts`, change:
```typescript
export interface ChatErrorEvent {
  type: "error";
  message: string;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent | ChatErrorEvent;
```
to:
```typescript
export interface ChatErrorEvent {
  type: "error";
  message: string;
}

export interface ChatToolCallEvent {
  type: "tool_call";
  tool: string;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent | ChatErrorEvent | ChatToolCallEvent;
```

- [ ] **Step 2: Render the transient status in `handleSend`**

In `frontend/app/page.tsx`, inside `handleSend`'s `for await` loop, change:
```typescript
        for await (const event of streamChat(sessionId, message, activeConversationId)) {
          if (event.type === "token") {
            assistantContent += event.content;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent },
            ]);
          } else if (event.type === "done") {
```
to:
```typescript
        for await (const event of streamChat(sessionId, message, activeConversationId)) {
          if (event.type === "tool_call") {
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: `Running ${event.tool}…` },
            ]);
          } else if (event.type === "token") {
            assistantContent += event.content;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent },
            ]);
          } else if (event.type === "done") {
```
(The rest of the loop — the `error` branch and the `finally` block — is
unchanged.)

- [ ] **Step 3: Type-check, lint, and build**

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```
Expected: all three succeed with no errors.

- [ ] **Step 4: Manual verification in the browser**

```bash
docker compose up -d
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev
```
Open `http://localhost:3000`. Type "What's today's date?" and send it. With
a real `LLM_API_KEY` set in `backend/.env`: confirm a brief "Running
get_current_date…" status appears, then is replaced by the streamed reply
once tokens arrive.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api-client.ts frontend/app/page.tsx
git commit -m "feat: show a transient status while a tool call is running"
```

---

### Task 15: Final verification and HANDOFF.md update

**Files:**
- Modify: `HANDOFF.md`

**Interfaces:** none (documentation + verification only).

- [ ] **Step 1: Run the full backend verification**

```bash
cd backend
python -m ruff check . ../ai_platform
python -m mypy app alembic ../ai_platform
python -m pytest -v
```
Expected: ruff clean, mypy clean, all tests pass.

- [ ] **Step 2: Run the full frontend verification**

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```
Expected: all clean.

- [ ] **Step 3: Re-verify Milestones 1-2's acceptance criteria still hold**

```bash
docker compose up -d
cd backend && uvicorn app.main:app --reload
```
In another terminal: `curl http://localhost:8000/api/health` still returns
`{"status":"healthy","app":"ok","database":"ok"}`; a plain chat message
(e.g. "hi") still streams a reply with no tool call.

- [ ] **Step 4: Verify the Milestone 3 acceptance criterion end to end**

With a real `LLM_API_KEY` set, POST "What's today's date?" to `/api/chat`
(via curl or the browser) and confirm: the SSE stream contains a `tool_call`
event naming `get_current_date`, the final response text contains a date,
and a row exists in `application.tool_executions` for that conversation
(query it directly, e.g. `docker compose exec postgres psql -U postgres -d
ai_employee_platform -c "SELECT tool, status, duration_ms FROM
application.tool_executions ORDER BY created_at DESC LIMIT 5;"`), and the
backend log output includes a `tool execution complete: tool=get_current_date
...` line with `request_id`/`conversation_id`/`workflow` populated.

- [ ] **Step 5: Update `HANDOFF.md`**

Rewrite `HANDOFF.md` following the same structure as the current one
(sections: Current State, Work Completed This Session, In-Progress Work,
Decisions Made, Known Issues / Failing Tests, Do NOT Do, Next Steps),
updating:
- Header line 2: `Last updated: <today's date> | Current milestone: 3 —
  Tool Calling | Status: complete`
- §1 Current State: add the tool-calling verification steps (asking "what's
  today's date" triggers a `tool_call` SSE event and a `tool_executions`
  row; `pytest` passes without a real key thanks to `FakeLLMService`).
- §2 Work Completed This Session: list the Tool Registry, `get_current_date`
  tool, `tool_executions` table + repository, Result Validator, Tool
  Executor, `Planner`/`Plan`/`ToolCall`, the `LLMService.complete()`
  addition, the `ChatWorkflow` rewrite, the FastAPI wiring, and the frontend
  `tool_call` status line.
- §4 Decisions Made: record the deliberate choice not to inject today's date
  into the planner's context (forces the tool-call path), the graceful
  tool-failure-degrades-to-explanation pattern (PRD Ch.13 Error Recovery
  Branch), and sequential-only tool execution (no parallel graph yet).
- §6 Do NOT Do: carry forward Milestones 1-2's items, and add "Don't add
  real finance tools yet — Milestone 4/5" and "Don't build a parallel
  tool-execution graph until there are ≥2 independently-selectable tools."
- §7 Next Steps: point to the next milestone per `docs/PRD.md` Chapter 16
  (Finance Simulator / first real finance tools).

- [ ] **Step 6: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 3 completion"
```
