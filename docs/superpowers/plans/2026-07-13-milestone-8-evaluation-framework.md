# Milestone 8 — Automated AI Evaluation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship PRD Ch.16's Milestone 8 — a framework that drives the real
chat pipeline (real `Planner`, `ExecutionPlanner`, `ToolExecutor`,
`PromptBuilder`) against the seeded simulator for a suite of authored
cases, scores tool-selection accuracy, parameter accuracy, memory usage,
and hallucination rate, persists results to a new `evaluation` schema, and
prints a scorecard from one command.

**Architecture:** A new `ai_platform/evaluation/` package that is a pure
bolt-on consumer of existing production code — it changes nothing in
`ChatWorkflow`/`Planner`/`ChatEvent`/`ToolExecutor`. Determinism in CI
comes from LLM-response cassettes (recorded from a real model once, keyed
by a hash of the current prompt versions, replayed via a new
`ScriptedLLMService`) rather than hand-scripted mocks, so the suite
actually measures NLU/prompt regressions. `evals/core/*.yaml` holds 30
seed cases authored against the live seed=42 database.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest +
pytest-asyncio, Postgres 16, PyYAML (new dependency, for case files).

## Global Constraints

- The LLM never accesses PostgreSQL, generates SQL, or knows table/schema
  names (CLAUDE.md, "Data access") — unchanged; the evaluation framework's
  LLM doubles only ever produce planner/responder text, exactly like the
  real `AnthropicLLMService`/`GroqLLMService`.
- No keyword matching — expectation checks in `scoring.py` are explicit,
  deterministic comparisons against an authored case's `expectations`
  block, never NLP or `if "..." in message` guessing.
- This milestone changes **zero** lines in `ai_platform/orchestration/
  chat_workflow.py`, `planner.py`, or `ai_platform/tool_registry/
  executor.py` — the runner is a read-only consumer of
  `application.tool_executions` and drives the real `ChatWorkflow`
  exactly as `app/api/chat.py`'s `post_chat` does, swapping only the
  `LLMService` implementation passed in.
- Every new/edited Python file starts with `from __future__ import
  annotations`. Line length 100 (ruff), `mypy --strict` clean.
- Datetime columns use `DateTime(timezone=True)` with a client-side
  `datetime.now(UTC)` default alongside `server_default=func.now()` —
  the `func.now()` transaction-scoping fix from Milestone 7 — never a
  naive `datetime.now()`.
- `ScriptedLLMService` and `RecordingLLMService` (new, `ai_platform/
  evaluation/cassette.py`) implement the existing `LLMService` Protocol
  (`ai_platform/llm/service.py`) exactly as written today — no protocol
  changes. They are production code (used by `run.py` in every mode),
  not test doubles — do not import `backend/tests/fakes.py`'s
  `FakeLLMService` from any file under `ai_platform/`.
- This milestone does not bump `planning_prompt.VERSION` or
  `system_prompt.VERSION` — no prompt content changes. It only *reads*
  both constants (`ai_platform/prompts/planning_prompt.py`,
  `ai_platform/prompts/system_prompt.py`) to compute the cassette hash.
- `evals/core/*.yaml` and `evals/cassettes/*.json` are both committed to
  git (the cassettes are what let CI run without a real LLM key) — never
  add either path to `.gitignore`.
- Real seeded values referenced in `evals/core/*.yaml` (customer/vendor
  names, invoice numbers, amounts, dates) were queried directly from the
  live seed=42 database on 2026-07-13 via `docker compose exec postgres
  psql ...` — reproducible any time from a freshly reseeded database,
  never invented.
- `ai_platform/evaluation/run.py` imports from `app.core.tool_registry`,
  `app.api.chat`, and `app.db.session` — matching the codebase's existing
  precedent (`ai_platform/orchestration/chat_workflow.py` already imports
  `app.core.errors`/`app.core.logging`) — so, like `domains.finance.
  simulator.seed`, it must always be invoked as `cd backend &&
  .venv/Scripts/python -m ai_platform.evaluation.run ...`, never from the
  repo root.
- Names reflect business meaning (`EvaluationRunner`, `EvaluationRepository`
  — never `Manager`/`Helper`/`Utils`/`Processor`).
- Don't touch any Milestone 6/7 HANDOFF open item (`PaymentRepository`
  validation gap, `search_invoices` sort, customer-id-vs-name
  inconsistency, Domain Adapters, parallel tool execution) — unrelated to
  evaluation, out of scope here.

---

## Phase A — Data Model & Case Loading

### Task 1: `evaluation` schema tables — migration and ORM models

**Files:**
- Create: `backend/alembic/versions/<REV1>_create_evaluation_tables.py`
- Create: `ai_platform/evaluation/models.py`
- Create: `ai_platform/evaluation/__init__.py`
- Modify: `pyproject.toml` (root)
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: `EvaluationCaseModel` (`__tablename__ = "evaluation_cases"`),
  `EvaluationRunModel` (`__tablename__ = "evaluation_runs"`),
  `EvaluationResultModel` (`__tablename__ = "evaluation_results"`) — all
  schema `evaluation` (already created by migration `51417db8e8b6`, no
  tables yet).

- [ ] **Step 1: Add the `pyyaml` dependency**

Modify `pyproject.toml` (root) — add `pyyaml` to `dependencies`:

```toml
[project]
name = "ai-platform"
version = "0.1.0"
description = "Reusable, domain-agnostic AI employee infrastructure"
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy[asyncio]>=2.0",
  "anthropic>=0.40",
  "groq>=0.11",
  "pyyaml>=6.0",
]
```

(only the `"pyyaml>=6.0",` line is new)

Modify `backend/pyproject.toml` — add `types-PyYAML` to the `dev` extra
(needed for `mypy --strict` to type-check `yaml.safe_load` calls):

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.7",
  "mypy>=1.12",
  "types-PyYAML>=6.0",
]
```

(only the `"types-PyYAML>=6.0",` line is new)

Run: `cd backend && .venv/Scripts/python -m pip install -e .. && .venv/Scripts/python -m pip install -e ".[dev]"`
Expected: installs cleanly, no errors.

- [ ] **Step 2: Write the migration**

Run `cd backend && .venv/Scripts/python -m alembic revision -m "create evaluation_cases evaluation_runs evaluation_results tables"`
to get a fresh revision id (call it `<REV1>` below — copy the exact id
alembic prints into the file this generates; its `down_revision` must be
`948c5fd90c8b`, the current head). Replace the generated file's body
with:

```python
"""create evaluation_cases evaluation_runs evaluation_results tables

Revision ID: <REV1>
Revises: 948c5fd90c8b
Create Date: <alembic's own timestamp>

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '<REV1>'
down_revision: str | Sequence[str] | None = '948c5fd90c8b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evaluation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.String(length=200), nullable=False, unique=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("suite", sa.String(length=100), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="evaluation",
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("planning_prompt_version", sa.String(length=20), nullable=False),
        sa.Column("system_prompt_version", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="evaluation",
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation.evaluation_runs.id"), nullable=False,
        ),
        sa.Column(
            "case_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation.evaluation_cases.id"), nullable=False,
        ),
        sa.Column("expected", postgresql.JSONB(), nullable=False),
        sa.Column("actual", postgresql.JSONB(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_evaluation_results_run_id", "run_id"),
        schema="evaluation",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("evaluation_results", schema="evaluation")
    op.drop_table("evaluation_runs", schema="evaluation")
    op.drop_table("evaluation_cases", schema="evaluation")
```

- [ ] **Step 3: Write the ORM models**

Create `ai_platform/evaluation/__init__.py` (empty file).

Create `ai_platform/evaluation/models.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "evaluation"


class EvaluationCaseModel(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    suite: Mapped[str] = mapped_column(String(100), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    planning_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    system_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )


class EvaluationResultModel(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.evaluation_runs.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.evaluation_cases.id"), nullable=False
    )
    expected: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actual: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 4: Apply the migration**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: no errors; `alembic current` shows `<REV1> (head)`.

Round-trip check: `.venv/Scripts/python -m alembic downgrade -1` then
`.venv/Scripts/python -m alembic upgrade head` — both succeed, ends back
on `<REV1>`.

- [ ] **Step 5: Confirm import and mypy**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.models import EvaluationCaseModel, EvaluationRunModel, EvaluationResultModel; print(EvaluationCaseModel.__tablename__, EvaluationRunModel.__tablename__, EvaluationResultModel.__tablename__)"`
Expected: prints `evaluation_cases evaluation_runs evaluation_results`.

Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: `Success: no issues found in N source files`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml backend/pyproject.toml backend/alembic/versions/ ai_platform/evaluation/
git commit -m "feat: add evaluation schema tables and pyyaml dependency

EvaluationCaseModel/EvaluationRunModel/EvaluationResultModel in the
evaluation schema (already created empty by migration 51417db8e8b6) -
the persistence layer for Milestone 8's evaluation framework."
```

---

### Task 2: `EvaluationRepository`

**Files:**
- Create: `ai_platform/evaluation/repository.py`
- Create: `backend/tests/test_evaluation_repository.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `EvaluationCaseModel`, `EvaluationRunModel`,
  `EvaluationResultModel` (Task 1).
- Produces: `EvaluationRepository(db: AsyncSession)` with
  `upsert_case(*, case_id: str, category: str, suite: str, definition:
  dict[str, Any]) -> EvaluationCaseModel`, `create_run(*, suite: str,
  mode: str, planning_prompt_version: str, system_prompt_version: str) ->
  EvaluationRunModel`, `record_result(*, run_id: uuid.UUID, case_id:
  uuid.UUID, expected: dict, actual: dict, passed: bool, score: float,
  metrics: dict, failure_reason: str | None) -> EvaluationResultModel`,
  `finish_run(*, run_id: uuid.UUID, total_cases: int, passed_cases: int,
  overall_score: Decimal, metrics: dict) -> None`.

- [ ] **Step 1: Extend `clean_db` for the three new tables**

Modify `backend/tests/conftest.py` — add the three evaluation tables to
the `TRUNCATE` statement (children before parents):

```python
@pytest.fixture
async def clean_db() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE evaluation.evaluation_results, evaluation.evaluation_runs, "
                "evaluation.evaluation_cases, "
                "application.tool_executions, application.messages, "
                "application.conversations, application.sessions, "
                "finance.vendor_payments, finance.vendor_invoices, "
                "finance.payments, finance.cash_transactions, finance.invoice_items, "
                "finance.invoices, finance.purchase_order_items, finance.purchase_orders, "
                "finance.expense_claims, finance.employees, finance.departments, "
                "finance.products, finance.customers, finance.vendors, finance.bank_accounts "
                "CASCADE"
            )
        )
    try:
        yield
    finally:
        await _dispose_and_reset_engine()
```

(only the first `TRUNCATE TABLE evaluation....,` line is new; every
other table in the list is unchanged)

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_evaluation_repository.py`:

```python
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.repository import EvaluationRepository


@pytest.mark.asyncio
async def test_upsert_case_creates_then_updates(clean_db: None, db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    created = await repo.upsert_case(
        case_id="case-1", category="unpaid_invoices", suite="core",
        definition={"user_message": "Show unpaid invoices"},
    )
    await db_session.commit()

    updated = await repo.upsert_case(
        case_id="case-1", category="unpaid_invoices", suite="core",
        definition={"user_message": "Show me unpaid invoices please"},
    )
    await db_session.commit()

    assert updated.id == created.id
    assert updated.definition == {"user_message": "Show me unpaid invoices please"}


@pytest.mark.asyncio
async def test_create_run_defaults_to_zero_totals(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = EvaluationRepository(db_session)
    run = await repo.create_run(
        suite="core", mode="recorded",
        planning_prompt_version="1.3.0", system_prompt_version="1.4.0",
    )
    await db_session.commit()

    assert run.total_cases == 0
    assert run.passed_cases == 0
    assert run.overall_score == Decimal("0")
    assert run.finished_at is None


@pytest.mark.asyncio
async def test_record_result_and_finish_run(clean_db: None, db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    case = await repo.upsert_case(
        case_id="case-2", category="hallucination", suite="core", definition={},
    )
    run = await repo.create_run(
        suite="core", mode="recorded",
        planning_prompt_version="1.3.0", system_prompt_version="1.4.0",
    )
    await db_session.commit()

    result = await repo.record_result(
        run_id=run.id, case_id=case.id,
        expected={"expected_tools": [{"tool": "search_invoices", "parameters": {}}]},
        actual={"tool_calls": [{"tool": "search_invoices", "parameters": {}}]},
        passed=True, score=1.0,
        metrics={"tool_selection_correct": True},
        failure_reason=None,
    )
    await repo.finish_run(
        run_id=run.id, total_cases=1, passed_cases=1,
        overall_score=Decimal("1.0000"),
        metrics={"tool_selection_accuracy": 1.0},
    )
    await db_session.commit()

    assert result.passed is True
    assert result.score == Decimal("1.0000")

    refreshed = await db_session.get(type(run), run.id)
    assert refreshed is not None
    assert refreshed.total_cases == 1
    assert refreshed.passed_cases == 1
    assert refreshed.finished_at is None  # finish_run doesn't set it - see note below


@pytest.mark.asyncio
async def test_finish_run_raises_for_unknown_run_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = EvaluationRepository(db_session)
    with pytest.raises(ValueError, match="does not exist"):
        await repo.finish_run(
            run_id=uuid.uuid4(), total_cases=0, passed_cases=0,
            overall_score=Decimal("0"), metrics={},
        )
```

Note on `finished_at`: `finish_run` sets `total_cases`/`passed_cases`/
`overall_score`/`metrics` and **also** `finished_at` — the test above
documents this incorrectly (asserts `is None`) so it fails first; Step 3
implements `finished_at = datetime.now(UTC)` inside `finish_run`, and
Step 4 fixes the test's own assertion to `is not None` once you see the
mismatch. This mirrors TDD's normal "write the test, watch it fail,
notice the test itself was wrong, fix the test" loop — don't skip
running Step 2 before writing Step 3's implementation just because the
answer is given away here.

- [ ] **Step 3: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.repository'`.

- [ ] **Step 4: Implement**

Create `ai_platform/evaluation/repository.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.models import (
    EvaluationCaseModel,
    EvaluationResultModel,
    EvaluationRunModel,
)


class EvaluationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_case(
        self, *, case_id: str, category: str, suite: str, definition: dict[str, Any]
    ) -> EvaluationCaseModel:
        stmt = select(EvaluationCaseModel).where(EvaluationCaseModel.case_id == case_id)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.category = category
            existing.suite = suite
            existing.definition = definition
            await self._db.flush()
            return existing
        row = EvaluationCaseModel(
            id=uuid.uuid4(), case_id=case_id, category=category, suite=suite,
            definition=definition,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def create_run(
        self, *, suite: str, mode: str, planning_prompt_version: str, system_prompt_version: str
    ) -> EvaluationRunModel:
        run = EvaluationRunModel(
            id=uuid.uuid4(),
            suite=suite,
            mode=mode,
            planning_prompt_version=planning_prompt_version,
            system_prompt_version=system_prompt_version,
            total_cases=0,
            passed_cases=0,
            overall_score=Decimal("0"),
            metrics={},
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def record_result(
        self,
        *,
        run_id: uuid.UUID,
        case_id: uuid.UUID,
        expected: dict[str, Any],
        actual: dict[str, Any],
        passed: bool,
        score: float,
        metrics: dict[str, Any],
        failure_reason: str | None,
    ) -> EvaluationResultModel:
        result_row = EvaluationResultModel(
            id=uuid.uuid4(),
            run_id=run_id,
            case_id=case_id,
            expected=expected,
            actual=actual,
            passed=passed,
            score=Decimal(str(score)),
            metrics=metrics,
            failure_reason=failure_reason,
        )
        self._db.add(result_row)
        await self._db.flush()
        return result_row

    async def finish_run(
        self,
        *,
        run_id: uuid.UUID,
        total_cases: int,
        passed_cases: int,
        overall_score: Decimal,
        metrics: dict[str, Any],
    ) -> None:
        run = await self._db.get(EvaluationRunModel, run_id)
        if run is None:
            raise ValueError(f"Evaluation run {run_id} does not exist")
        run.total_cases = total_cases
        run.passed_cases = passed_cases
        run.overall_score = overall_score
        run.metrics = metrics
        run.finished_at = datetime.now(UTC)
        await self._db.flush()
```

- [ ] **Step 5: Fix the test's `finished_at` assertion and confirm all pass**

In `backend/tests/test_evaluation_repository.py`, change:

```python
    assert refreshed.finished_at is None  # finish_run doesn't set it - see note below
```

to:

```python
    assert refreshed.finished_at is not None
```

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_repository.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 6: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add ai_platform/evaluation/repository.py backend/tests/test_evaluation_repository.py backend/tests/conftest.py
git commit -m "feat: add EvaluationRepository

upsert_case/create_run/record_result/finish_run - the data-access layer
over the evaluation schema; clean_db now truncates all three new tables
so evaluation tests don't leak rows across runs."
```

---

### Task 3: Case file schema (`case_schema.py`)

**Files:**
- Create: `ai_platform/evaluation/case_schema.py`
- Create: `backend/tests/test_evaluation_case_schema.py`

**Interfaces:**
- Produces: `ConversationSetupTurn(BaseModel)` (`user_message: str`),
  `ExpectedTool(BaseModel)` (`tool: str, parameters: dict[str, Any]`),
  `Expectations(BaseModel)` (`expected_tools: list[ExpectedTool],
  expected_clarification: bool | str, forbidden_content: list[str],
  required_facts: list[str]`), `EvalCase(BaseModel)` (`id: str, category:
  str, tests_memory: bool, conversation_setup:
  list[ConversationSetupTurn], user_message: str, expectations:
  Expectations`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evaluation_case_schema.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_platform.evaluation.case_schema import EvalCase


def test_minimal_case_parses_with_defaults() -> None:
    case = EvalCase.model_validate(
        {
            "id": "unpaid_invoices_show",
            "category": "unpaid_invoices",
            "user_message": "Show me all unpaid invoices",
            "expectations": {
                "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}]
            },
        }
    )
    assert case.tests_memory is False
    assert case.conversation_setup == []
    assert case.expectations.expected_clarification is False
    assert case.expectations.forbidden_content == []
    assert case.expectations.required_facts == []
    assert case.expectations.expected_tools[0].tool == "get_unpaid_invoices"


def test_full_case_with_conversation_setup_and_all_expectation_fields() -> None:
    case = EvalCase.model_validate(
        {
            "id": "followup_those_anchor",
            "category": "follow_up",
            "tests_memory": True,
            "conversation_setup": [{"user_message": "Show overdue invoices"}],
            "user_message": "Which of those belong to Anchor Components?",
            "expectations": {
                "expected_tools": [
                    {"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}},
                    {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
                ],
                "forbidden_content": ["INV-99999"],
                "required_facts": ["6534.00"],
            },
        }
    )
    assert case.tests_memory is True
    assert case.conversation_setup[0].user_message == "Show overdue invoices"
    assert len(case.expectations.expected_tools) == 2
    assert case.expectations.expected_tools[1].parameters["customer_id"] == "<piped>"


def test_expected_clarification_accepts_bool_or_string() -> None:
    bool_case = EvalCase.model_validate(
        {
            "id": "ambiguous-1", "category": "ambiguity", "user_message": "Show invoices",
            "expectations": {"expected_clarification": True},
        }
    )
    assert bool_case.expectations.expected_clarification is True

    string_case = EvalCase.model_validate(
        {
            "id": "ambiguous-2", "category": "ambiguity", "user_message": "Show payments",
            "expectations": {"expected_clarification": "which"},
        }
    )
    assert string_case.expectations.expected_clarification == "which"


def test_expected_clarification_and_expected_tools_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        EvalCase.model_validate(
            {
                "id": "bad-case", "category": "ambiguity", "user_message": "Show invoices",
                "expectations": {
                    "expected_clarification": True,
                    "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}],
                },
            }
        )


def test_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        EvalCase.model_validate({"category": "unpaid_invoices", "user_message": "x"})
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_case_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.case_schema'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/case_schema.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConversationSetupTurn(BaseModel):
    user_message: str


class ExpectedTool(BaseModel):
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Expectations(BaseModel):
    expected_tools: list[ExpectedTool] = Field(default_factory=list)
    expected_clarification: bool | str = False
    forbidden_content: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _clarification_and_tools_are_mutually_exclusive(self) -> Expectations:
        expects_clarification = self.expected_clarification is not False
        if expects_clarification and self.expected_tools:
            raise ValueError(
                "expected_clarification and expected_tools are mutually exclusive"
            )
        return self


class EvalCase(BaseModel):
    id: str
    category: str
    tests_memory: bool = False
    conversation_setup: list[ConversationSetupTurn] = Field(default_factory=list)
    user_message: str
    expectations: Expectations
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_case_schema.py -v`
Expected: PASS, all 5 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/case_schema.py backend/tests/test_evaluation_case_schema.py
git commit -m "feat: add EvalCase/Expectations Pydantic schema for eval case files

expected_clarification and expected_tools are mutually exclusive - a
case either expects a clarifying question or a specific tool sequence,
never both."
```

---

### Task 4: Suite loader (`loader.py`)

**Files:**
- Create: `ai_platform/evaluation/loader.py`
- Create: `backend/tests/test_evaluation_loader.py`

**Interfaces:**
- Consumes: `EvalCase` (Task 3).
- Produces: `DEFAULT_EVALS_ROOT: Path`, `load_suite(suite: str, *,
  evals_root: Path | None = None) -> list[EvalCase]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evaluation_loader.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_platform.evaluation.loader import load_suite


def _write_case(directory: Path, filename: str, case_id: str, user_message: str) -> None:
    (directory / filename).write_text(
        yaml.safe_dump(
            {
                "id": case_id,
                "category": "test_category",
                "user_message": user_message,
                "expectations": {
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}]
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_suite_reads_every_yaml_file_sorted_by_filename(tmp_path: Path) -> None:
    suite_dir = tmp_path / "core"
    suite_dir.mkdir()
    _write_case(suite_dir, "b_case.yaml", "case-b", "second")
    _write_case(suite_dir, "a_case.yaml", "case-a", "first")

    cases = load_suite("core", evals_root=tmp_path)

    assert [c.id for c in cases] == ["case-a", "case-b"]


def test_load_suite_raises_for_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="core"):
        load_suite("core", evals_root=tmp_path)


def test_load_suite_raises_for_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "core").mkdir()
    with pytest.raises(ValueError, match="no case files"):
        load_suite("core", evals_root=tmp_path)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.loader'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/loader.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from ai_platform.evaluation.case_schema import EvalCase

DEFAULT_EVALS_ROOT = Path(__file__).resolve().parents[2] / "evals"


def load_suite(suite: str, *, evals_root: Path | None = None) -> list[EvalCase]:
    root = evals_root if evals_root is not None else DEFAULT_EVALS_ROOT
    suite_dir = root / suite
    if not suite_dir.is_dir():
        raise FileNotFoundError(f"No such eval suite directory: {suite_dir}")

    cases: list[EvalCase] = []
    for path in sorted(suite_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        cases.append(EvalCase.model_validate(raw))

    if not cases:
        raise ValueError(f"Eval suite '{suite}' has no case files under {suite_dir}")
    return cases
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_loader.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/loader.py backend/tests/test_evaluation_loader.py
git commit -m "feat: add load_suite for reading eval case YAML files

evals_root is injectable (defaults to the real repo evals/ directory)
so tests never have to write into the real evals/ tree."
```

---

## Phase B — Cassette Mechanism

### Task 5: Cassette hashing and file I/O

**Files:**
- Create: `ai_platform/evaluation/cassette.py`
- Create: `backend/tests/test_evaluation_cassette.py`

**Interfaces:**
- Consumes: `planning_prompt.VERSION`, `system_prompt.VERSION`
  (existing).
- Produces: `DEFAULT_CASSETTES_ROOT: Path`, `prompt_version_hash() ->
  str`, `cassette_path(case_id: str, turn: int, *, cassettes_root: Path
  | None = None) -> Path`, `load_cassette(case_id: str, turn: int, *,
  cassettes_root: Path | None = None) -> dict[str, str] | None`,
  `save_cassette(case_id: str, turn: int, *, plan_response: str,
  response_text: str, cassettes_root: Path | None = None) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evaluation_cassette.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ai_platform.evaluation.cassette import (
    cassette_path,
    load_cassette,
    prompt_version_hash,
    save_cassette,
)


def test_prompt_version_hash_is_stable_and_twelve_hex_chars() -> None:
    first = prompt_version_hash()
    second = prompt_version_hash()
    assert first == second
    assert len(first) == 12
    assert all(c in "0123456789abcdef" for c in first)


def test_prompt_version_hash_changes_when_a_version_changes() -> None:
    with patch("ai_platform.evaluation.cassette.PLANNING_PROMPT_VERSION", "9.9.9"):
        changed = prompt_version_hash()
    assert changed != prompt_version_hash()


def test_load_cassette_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert load_cassette("no-such-case", 0, cassettes_root=tmp_path) is None


def test_save_then_load_cassette_round_trips(tmp_path: Path) -> None:
    save_cassette(
        "case-1", 0,
        plan_response='{"tool_calls": []}', response_text="Here you go.",
        cassettes_root=tmp_path,
    )

    loaded = load_cassette("case-1", 0, cassettes_root=tmp_path)

    assert loaded == {"plan_response": '{"tool_calls": []}', "response_text": "Here you go."}


def test_cassette_path_includes_case_id_turn_and_hash(tmp_path: Path) -> None:
    path = cassette_path("case-1", 2, cassettes_root=tmp_path)
    assert path.parent == tmp_path
    assert path.name == f"case-1__turn2__{prompt_version_hash()}.json"
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cassette.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.cassette'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/cassette.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ai_platform.prompts.planning_prompt import VERSION as PLANNING_PROMPT_VERSION
from ai_platform.prompts.system_prompt import VERSION as SYSTEM_PROMPT_VERSION

DEFAULT_CASSETTES_ROOT = Path(__file__).resolve().parents[2] / "evals" / "cassettes"


def prompt_version_hash() -> str:
    raw = f"{PLANNING_PROMPT_VERSION}:{SYSTEM_PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def cassette_path(case_id: str, turn: int, *, cassettes_root: Path | None = None) -> Path:
    root = cassettes_root if cassettes_root is not None else DEFAULT_CASSETTES_ROOT
    return root / f"{case_id}__turn{turn}__{prompt_version_hash()}.json"


def load_cassette(
    case_id: str, turn: int, *, cassettes_root: Path | None = None
) -> dict[str, str] | None:
    path = cassette_path(case_id, turn, cassettes_root=cassettes_root)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data: dict[str, str] = json.load(handle)
    return data


def save_cassette(
    case_id: str,
    turn: int,
    *,
    plan_response: str,
    response_text: str,
    cassettes_root: Path | None = None,
) -> None:
    root = cassettes_root if cassettes_root is not None else DEFAULT_CASSETTES_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = cassette_path(case_id, turn, cassettes_root=cassettes_root)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {"plan_response": plan_response, "response_text": response_text}, handle, indent=2
        )
```

Note: `test_prompt_version_hash_changes_when_a_version_changes` patches
the module-level `PLANNING_PROMPT_VERSION` name inside
`ai_platform.evaluation.cassette` (not
`ai_platform.prompts.planning_prompt.VERSION`) — this only works because
`cassette.py` imports the constant with `from ... import VERSION as
PLANNING_PROMPT_VERSION` (a module-level name binding `unittest.mock.patch`
can target directly), which is why Step 3's import is written exactly
that way rather than `from ai_platform.prompts import planning_prompt`
plus `planning_prompt.VERSION` everywhere.

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cassette.py -v`
Expected: PASS, all 5 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/cassette.py backend/tests/test_evaluation_cassette.py
git commit -m "feat: add cassette hashing and file I/O

prompt_version_hash() hashes both prompt VERSIONs together; a cassette
filename embeds it, so bumping either prompt makes every existing
cassette stop matching - the mechanism behind flagging prompt changes
that haven't been re-verified by the suite."
```

---

### Task 6: `ScriptedLLMService` and `RecordingLLMService`

**Files:**
- Modify: `ai_platform/evaluation/cassette.py`
- Modify: `backend/tests/test_evaluation_cassette.py`

**Interfaces:**
- Consumes: `LLMService` Protocol (`ai_platform/llm/service.py`,
  unchanged).
- Produces: `ScriptedLLMService(plan_response: str, response_text: str)`
  — a production `LLMService` implementation that replays fixed text;
  `RecordingLLMService(wrapped: LLMService)` — wraps a real `LLMService`,
  delegating both calls unchanged while buffering what they returned.
  Both expose `stream_reply_called: bool` (only set once `stream_reply`
  is actually invoked — never set by `complete()` alone), so callers can
  tell a clarification turn (Phase 2 never runs) from a normal turn
  without inspecting `ChatEvent`s.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_evaluation_cassette.py`:

```python
import pytest

from ai_platform.evaluation.cassette import RecordingLLMService, ScriptedLLMService


@pytest.mark.asyncio
async def test_scripted_llm_service_replays_fixed_content() -> None:
    service = ScriptedLLMService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
    )

    assert service.stream_reply_called is False
    plan_raw = await service.complete("system", [], "What's today?")
    assert plan_raw == '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'

    chunks = [chunk async for chunk in service.stream_reply("system", [], "What's today?")]
    assert chunks == ["Today is Tuesday."]
    assert service.stream_reply_called is True


@pytest.mark.asyncio
async def test_scripted_llm_service_stream_reply_called_stays_false_if_never_invoked() -> None:
    service = ScriptedLLMService(
        plan_response='{"clarification_needed": "Which invoices - all, unpaid, or overdue?"}',
        response_text="",
    )
    await service.complete("system", [], "Show invoices")
    assert service.stream_reply_called is False


class _FakeRealService:
    def __init__(self, plan_response: str, tokens: list[str]) -> None:
        self._plan_response = plan_response
        self._tokens = tokens

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response

    async def stream_reply(self, system: str, history: list[dict[str, str]], message: str):
        for token in self._tokens:
            yield token


@pytest.mark.asyncio
async def test_recording_llm_service_delegates_and_buffers() -> None:
    wrapped = _FakeRealService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        tokens=["Today ", "is ", "Tuesday."],
    )
    recorder = RecordingLLMService(wrapped)

    raw = await recorder.complete("system", [], "What's today?")
    assert raw == '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    assert recorder.last_plan_response == raw

    chunks = [chunk async for chunk in recorder.stream_reply("system", [], "What's today?")]
    assert chunks == ["Today ", "is ", "Tuesday."]
    assert recorder.last_response_text == "Today is Tuesday."
    assert recorder.stream_reply_called is True


@pytest.mark.asyncio
async def test_recording_llm_service_stream_reply_called_false_until_invoked() -> None:
    wrapped = _FakeRealService(plan_response='{"clarification_needed": "which?"}', tokens=[])
    recorder = RecordingLLMService(wrapped)
    await recorder.complete("system", [], "Show invoices")
    assert recorder.stream_reply_called is False
    assert recorder.last_response_text is None
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cassette.py -v`
Expected: FAIL — `ImportError: cannot import name 'RecordingLLMService'`.

- [ ] **Step 3: Implement**

Append to `ai_platform/evaluation/cassette.py` (after `save_cassette`):

```python
from collections.abc import AsyncIterator

from ai_platform.llm.service import LLMService


class ScriptedLLMService:
    """Production LLMService implementation that replays fixed text
    instead of calling a real model - the third LLMService alongside
    AnthropicLLMService/GroqLLMService, used only by the evaluation
    runner's `recorded` mode. Distinct from `backend/tests/fakes.py`'s
    FakeLLMService, which is test-only and never imported from
    ai_platform.
    """

    def __init__(self, plan_response: str, response_text: str) -> None:
        self._plan_response = plan_response
        self._response_text = response_text
        self.stream_reply_called = False

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.stream_reply_called = True
        yield self._response_text

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response


class RecordingLLMService:
    """Wraps a real LLMService, delegating every call unchanged while
    buffering the exact strings returned, so `--record` can persist them
    to a cassette after the turn completes.
    """

    def __init__(self, wrapped: LLMService) -> None:
        self._wrapped = wrapped
        self.stream_reply_called = False
        self.last_plan_response: str | None = None
        self.last_response_text: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.stream_reply_called = True
        chunks: list[str] = []
        async for chunk in self._wrapped.stream_reply(system, history, message):
            chunks.append(chunk)
            yield chunk
        self.last_response_text = "".join(chunks)

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        raw = await self._wrapped.complete(system, history, message)
        self.last_plan_response = raw
        return raw
```

Move the `from collections.abc import AsyncIterator` and `from
ai_platform.llm.service import LLMService` imports up to the top of the
file alongside the existing `hashlib`/`json`/`Path` imports, in the
project's standard import-ordering (stdlib, then blank line, then
first-party) — don't leave them as a second import block partway through
the file.

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cassette.py -v`
Expected: PASS, all 9 tests.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/cassette.py backend/tests/test_evaluation_cassette.py
git commit -m "feat: add ScriptedLLMService and RecordingLLMService

Both are production LLMService implementations (not test doubles) -
ScriptedLLMService replays cassette content in recorded mode,
RecordingLLMService wraps the real LLMService in live mode to capture
what it returns. stream_reply_called lets the runner distinguish a
clarification turn (Phase 2 never invoked) from a normal one without
inspecting ChatEvents."
```

---

## Phase C — Scoring

### Task 7: Per-case scoring (`scoring.py`)

**Files:**
- Create: `ai_platform/evaluation/scoring.py`
- Create: `backend/tests/test_evaluation_scoring.py`

**Interfaces:**
- Consumes: `EvalCase`, `ExpectedTool` (Task 3).
- Produces: `PIPED_SENTINEL = "<piped>"`, `ActualToolCall(tool: str,
  parameters: dict[str, Any])` (dataclass), `CaseOutcome(tool_calls:
  list[ActualToolCall], response_text: str, clarification: str | None)`
  (dataclass), `CaseScore(passed: bool, score: float, metrics: dict[str,
  bool], parameter_pairs_matched: int, parameter_pairs_total: int,
  failure_reason: str | None)` (dataclass), `score_case(case: EvalCase,
  outcome: CaseOutcome) -> CaseScore`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evaluation_scoring.py`:

```python
from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.scoring import ActualToolCall, CaseOutcome, score_case


def _case(**expectations_kwargs: object) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": "test-case",
            "category": "test",
            "user_message": "irrelevant",
            "expectations": expectations_kwargs,
        }
    )


def test_full_pass_when_everything_matches() -> None:
    case = _case(
        expected_tools=[{"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}],
        required_facts=["Acme"],
        forbidden_content=["INV-99999"],
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer_balance", parameters={"customer_name": "Acme"})
        ],
        response_text="Acme owes $1,000.00.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is True
    assert score.score == 1.0
    assert score.failure_reason is None


def test_fails_when_tool_sequence_is_wrong() -> None:
    case = _case(expected_tools=[{"tool": "get_customer_balance", "parameters": {}}])
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_vendor_balance", parameters={})],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False
    assert score.failure_reason is not None


def test_fails_when_tool_sequence_has_wrong_length() -> None:
    case = _case(
        expected_tools=[
            {"tool": "get_customer", "parameters": {}},
            {"tool": "get_overdue_invoices", "parameters": {}},
        ]
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_customer", parameters={})],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False


def test_fails_when_a_parameter_value_is_wrong() -> None:
    case = _case(
        expected_tools=[{"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}]
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer_balance", parameters={"customer_name": "Wrong Co"})
        ],
        response_text="", clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["parameters_correct"] is False
    assert score.parameter_pairs_matched == 0
    assert score.parameter_pairs_total == 1


def test_piped_sentinel_accepts_any_resolved_value_but_not_the_placeholder() -> None:
    case = _case(
        expected_tools=[
            {"tool": "get_customer", "parameters": {"customer_name": "Acme"}},
            {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
        ]
    )
    resolved = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer", parameters={"customer_name": "Acme"}),
            ActualToolCall(tool="get_overdue_invoices", parameters={"customer_id": "CUST-0003"}),
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, resolved).metrics["parameters_correct"] is True

    unresolved = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="get_customer", parameters={"customer_name": "Acme"}),
            ActualToolCall(
                tool="get_overdue_invoices", parameters={"customer_id": "$step0.customer_code"}
            ),
        ],
        response_text="", clarification=None,
    )
    assert score_case(case, unresolved).metrics["parameters_correct"] is False


def test_fails_when_clarification_expected_but_none_happened() -> None:
    case = _case(expected_clarification=True)
    outcome = CaseOutcome(
        tool_calls=[], response_text="Here are your invoices.", clarification=None
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["clarification_correct"] is False


def test_fails_when_clarification_happened_but_none_expected() -> None:
    case = _case(expected_tools=[{"tool": "get_unpaid_invoices", "parameters": {}}])
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_unpaid_invoices", parameters={})],
        response_text="Which invoices - all, unpaid, or overdue?",
        clarification="Which invoices - all, unpaid, or overdue?",
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["clarification_correct"] is False


def test_expected_clarification_string_is_treated_as_a_regex() -> None:
    case = _case(expected_clarification="all.*unpaid.*overdue")
    matching = CaseOutcome(
        tool_calls=[], response_text="", clarification="Do you want all, unpaid, or overdue?",
    )
    assert score_case(case, matching).metrics["clarification_correct"] is True

    non_matching = CaseOutcome(tool_calls=[], response_text="", clarification="Which customer?")
    assert score_case(case, non_matching).metrics["clarification_correct"] is False


def test_fails_when_forbidden_content_appears_in_response() -> None:
    case = _case(
        expected_tools=[{"tool": "search_invoices", "parameters": {"invoice_number": "INV-99999"}}],
        forbidden_content=["INV-7051"],
    )
    outcome = CaseOutcome(
        tool_calls=[
            ActualToolCall(tool="search_invoices", parameters={"invoice_number": "INV-99999"})
        ],
        response_text="I couldn't find INV-99999, but INV-7051 is similar.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["hallucinated"] is True


def test_forbidden_content_check_ignores_comma_and_dollar_formatting() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        forbidden_content=["999999.99"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Balance is $999,999.99 today.",
        clarification=None,
    )
    assert score_case(case, outcome).metrics["hallucinated"] is True


def test_fails_when_a_required_fact_is_missing() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        required_facts=["918201.30"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Your balance is healthy.",
        clarification=None,
    )
    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["required_facts_present"] is False


def test_required_fact_check_ignores_comma_and_dollar_formatting() -> None:
    case = _case(
        expected_tools=[{"tool": "get_cash_position", "parameters": {}}],
        required_facts=["918201.30"],
    )
    outcome = CaseOutcome(
        tool_calls=[ActualToolCall(tool="get_cash_position", parameters={})],
        response_text="Your balance is $918,201.30 today.",
        clarification=None,
    )
    assert score_case(case, outcome).metrics["required_facts_present"] is True
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.scoring'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/scoring.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_platform.evaluation.case_schema import EvalCase, ExpectedTool

PIPED_SENTINEL = "<piped>"
_PLACEHOLDER_PREFIX = "$step"


@dataclass
class ActualToolCall:
    tool: str
    parameters: dict[str, Any]


@dataclass
class CaseOutcome:
    tool_calls: list[ActualToolCall]
    response_text: str
    clarification: str | None


@dataclass
class CaseScore:
    passed: bool
    score: float
    metrics: dict[str, bool]
    parameter_pairs_matched: int
    parameter_pairs_total: int
    failure_reason: str | None = None


def _normalize(text: str) -> str:
    return text.replace(",", "").replace("$", "")


def _tool_sequence_matches(expected: list[ExpectedTool], actual: list[ActualToolCall]) -> bool:
    if len(expected) != len(actual):
        return False
    return all(e.tool == a.tool for e, a in zip(expected, actual, strict=True))


def _parameters_match(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, int, int]:
    total = len(expected)
    matched = 0
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if expected_value == PIPED_SENTINEL:
            resolved = actual_value is not None and not (
                isinstance(actual_value, str) and actual_value.startswith(_PLACEHOLDER_PREFIX)
            )
            if resolved:
                matched += 1
        elif actual_value == expected_value:
            matched += 1
    return matched == total, matched, total


def _clarification_matches(expected: bool | str, actual: str | None) -> bool:
    if expected is False:
        return actual is None
    if actual is None:
        return False
    if expected is True:
        return True
    return re.search(expected, actual) is not None


def _contains_none(haystack: str, needles: list[str]) -> bool:
    normalized_haystack = _normalize(haystack)
    return not any(_normalize(needle) in normalized_haystack for needle in needles)


def _contains_all(haystack: str, needles: list[str]) -> bool:
    normalized_haystack = _normalize(haystack)
    return all(_normalize(needle) in normalized_haystack for needle in needles)


def score_case(case: EvalCase, outcome: CaseOutcome) -> CaseScore:
    expectations = case.expectations
    reasons: list[str] = []

    tool_sequence_ok = True
    parameter_pairs_matched = 0
    parameter_pairs_total = 0
    if expectations.expected_tools:
        tool_sequence_ok = _tool_sequence_matches(expectations.expected_tools, outcome.tool_calls)
        if not tool_sequence_ok:
            reasons.append(
                f"expected tool sequence {[e.tool for e in expectations.expected_tools]}, "
                f"got {[a.tool for a in outcome.tool_calls]}"
            )
        else:
            for expected_tool, actual_call in zip(
                expectations.expected_tools, outcome.tool_calls, strict=True
            ):
                ok, matched, total = _parameters_match(
                    expected_tool.parameters, actual_call.parameters
                )
                parameter_pairs_matched += matched
                parameter_pairs_total += total
                if not ok:
                    reasons.append(
                        f"{expected_tool.tool}: expected parameters "
                        f"{expected_tool.parameters}, got {actual_call.parameters}"
                    )

    clarification_ok = _clarification_matches(
        expectations.expected_clarification, outcome.clarification
    )
    if not clarification_ok:
        reasons.append(
            f"expected_clarification={expectations.expected_clarification!r}, "
            f"got clarification={outcome.clarification!r}"
        )

    hallucinated = False
    if expectations.forbidden_content:
        hallucinated = not _contains_none(outcome.response_text, expectations.forbidden_content)
        if hallucinated:
            reasons.append(f"response contains forbidden content: {expectations.forbidden_content}")

    required_facts_ok = True
    if expectations.required_facts:
        required_facts_ok = _contains_all(outcome.response_text, expectations.required_facts)
        if not required_facts_ok:
            reasons.append(f"response missing required facts: {expectations.required_facts}")

    all_parameters_ok = parameter_pairs_matched == parameter_pairs_total
    passed = (
        tool_sequence_ok
        and all_parameters_ok
        and clarification_ok
        and not hallucinated
        and required_facts_ok
    )
    return CaseScore(
        passed=passed,
        score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": tool_sequence_ok,
            "parameters_correct": all_parameters_ok,
            "clarification_correct": clarification_ok,
            "hallucinated": hallucinated,
            "required_facts_present": required_facts_ok,
        },
        parameter_pairs_matched=parameter_pairs_matched,
        parameter_pairs_total=parameter_pairs_total,
        failure_reason="; ".join(reasons) if reasons else None,
    )
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_scoring.py -v`
Expected: PASS, all 12 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/scoring.py backend/tests/test_evaluation_scoring.py
git commit -m "feat: add score_case with five independently-tested checks

Tool sequence, parameter subset match (with a <piped> sentinel for
resolved-but-unpredictable values), clarification match (bool or
regex), forbidden-content (hallucination), and required-facts checks.
Each has a dedicated failing-path test, not just a happy-path one."
```

---

### Task 8: Aggregate metrics (`aggregate_metrics`)

**Files:**
- Modify: `ai_platform/evaluation/scoring.py`
- Modify: `backend/tests/test_evaluation_scoring.py`

**Interfaces:**
- Consumes: `EvalCase`, `CaseScore` (this file).
- Produces: `aggregate_metrics(cases: list[EvalCase], scores:
  list[CaseScore]) -> dict[str, float]` with keys
  `tool_selection_accuracy`, `parameter_accuracy`,
  `memory_usage_accuracy`, `hallucination_rate`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_evaluation_scoring.py`:

```python
from ai_platform.evaluation.scoring import CaseScore, aggregate_metrics


def _score(
    passed: bool, *, tool_selection_correct: bool = True, hallucinated: bool = False,
    matched: int = 0, total: int = 0,
) -> CaseScore:
    return CaseScore(
        passed=passed, score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": tool_selection_correct, "parameters_correct": True,
            "clarification_correct": True, "hallucinated": hallucinated,
            "required_facts_present": True,
        },
        parameter_pairs_matched=matched, parameter_pairs_total=total,
    )


def test_tool_selection_accuracy_only_counts_cases_with_expected_tools() -> None:
    with_tools = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    without_tools = _case(expected_clarification=True)
    metrics = aggregate_metrics(
        [with_tools, without_tools],
        [_score(True, tool_selection_correct=True), _score(True, tool_selection_correct=False)],
    )
    assert metrics["tool_selection_accuracy"] == 1.0


def test_memory_usage_accuracy_only_counts_tests_memory_cases() -> None:
    memory_case = EvalCase.model_validate(
        {
            "id": "m1", "category": "follow_up", "tests_memory": True, "user_message": "x",
            "expectations": {"expected_tools": [{"tool": "get_customer", "parameters": {}}]},
        }
    )
    non_memory_case = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    metrics = aggregate_metrics(
        [memory_case, non_memory_case],
        [_score(False, tool_selection_correct=False), _score(True, tool_selection_correct=True)],
    )
    assert metrics["memory_usage_accuracy"] == 0.0


def test_hallucination_rate_only_counts_cases_with_forbidden_content() -> None:
    trap_case = _case(
        expected_tools=[{"tool": "search_invoices", "parameters": {}}],
        forbidden_content=["INV-99999"],
    )
    plain_case = _case(expected_tools=[{"tool": "get_current_date", "parameters": {}}])
    metrics = aggregate_metrics(
        [trap_case, plain_case],
        [_score(False, hallucinated=True), _score(True, hallucinated=False)],
    )
    assert metrics["hallucination_rate"] == 1.0


def test_parameter_accuracy_sums_matched_pairs_across_all_cases() -> None:
    case_a = _case(
        expected_tools=[
            {"tool": "get_customer_balance", "parameters": {"customer_name": "Acme"}}
        ]
    )
    case_b = _case(
        expected_tools=[{"tool": "get_vendor_balance", "parameters": {"vendor_name": "Acme"}}]
    )
    metrics = aggregate_metrics(
        [case_a, case_b], [_score(True, matched=1, total=1), _score(False, matched=0, total=1)]
    )
    assert metrics["parameter_accuracy"] == 0.5


def test_aggregate_metrics_defaults_to_1_0_when_no_applicable_cases() -> None:
    plain_case = _case(expected_clarification=True)
    metrics = aggregate_metrics([plain_case], [_score(True)])
    assert metrics["tool_selection_accuracy"] == 1.0
    assert metrics["memory_usage_accuracy"] == 1.0
    assert metrics["hallucination_rate"] == 1.0
    assert metrics["parameter_accuracy"] == 1.0
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_scoring.py -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_metrics'`.

- [ ] **Step 3: Implement**

Append to `ai_platform/evaluation/scoring.py`:

```python
def _rate(pairs: list[tuple[EvalCase, CaseScore]], metric_key: str) -> float:
    if not pairs:
        return 1.0
    return sum(1 for _, score in pairs if score.metrics[metric_key]) / len(pairs)


def aggregate_metrics(cases: list[EvalCase], scores: list[CaseScore]) -> dict[str, float]:
    paired = list(zip(cases, scores, strict=True))
    tool_selection_pairs = [(c, s) for c, s in paired if c.expectations.expected_tools]
    memory_pairs = [(c, s) for c, s in tool_selection_pairs if c.tests_memory]
    hallucination_pairs = [(c, s) for c, s in paired if c.expectations.forbidden_content]

    total_pairs = sum(s.parameter_pairs_total for s in scores)
    matched_pairs = sum(s.parameter_pairs_matched for s in scores)

    return {
        "tool_selection_accuracy": _rate(tool_selection_pairs, "tool_selection_correct"),
        "parameter_accuracy": (matched_pairs / total_pairs) if total_pairs else 1.0,
        "memory_usage_accuracy": _rate(memory_pairs, "tool_selection_correct"),
        "hallucination_rate": _rate(hallucination_pairs, "hallucinated"),
    }
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_scoring.py -v`
Expected: PASS, all 17 tests.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/scoring.py backend/tests/test_evaluation_scoring.py
git commit -m "feat: add aggregate_metrics for suite-level scorecards

Each of the four named metrics only counts cases where it's applicable
(tool_selection_accuracy skips clarification-only cases, memory_usage
restricts to tests_memory cases, hallucination_rate restricts to cases
with forbidden_content) - an empty denominator defaults to 1.0 rather
than dividing by zero."
```

---

## Phase D — Runner

### Task 9: `ToolExecutionRepository.list_by_request_id`

**Files:**
- Modify: `ai_platform/tool_registry/repository.py`
- Modify: `backend/tests/test_tool_execution_repository.py`

**Interfaces:**
- Produces: `ToolExecutionRepository.list_by_request_id(request_id: str)
  -> list[ToolExecutionModel]`, ordered by `created_at` ascending — how
  the evaluation runner reconstructs a turn's real, resolved tool calls
  without touching `ChatEvent`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_tool_execution_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_by_request_id_returns_only_that_requests_executions_in_order(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-2")
    conversation = await conversation_repo.create_conversation("session-tool-2")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    await repo.record_execution(
        request_id="req-a", conversation_id=conversation.id, tool="get_customer",
        parameters={"customer_name": "Acme"}, result={"customer_code": "CUST-0001"},
        duration_ms=3, status="success", error_message=None,
    )
    await repo.record_execution(
        request_id="req-a", conversation_id=conversation.id, tool="get_overdue_invoices",
        parameters={"customer_id": "CUST-0001"}, result={"invoices": [], "summary": {}},
        duration_ms=4, status="success", error_message=None,
    )
    await repo.record_execution(
        request_id="req-b", conversation_id=conversation.id, tool="get_current_date",
        parameters={}, result={"date": "2026-07-13"}, duration_ms=1, status="success",
        error_message=None,
    )
    await db_session.commit()

    executions = await repo.list_by_request_id("req-a")
    assert [e.tool for e in executions] == ["get_customer", "get_overdue_invoices"]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_tool_execution_repository.py -v`
Expected: FAIL — `AttributeError: 'ToolExecutionRepository' object has no
attribute 'list_by_request_id'`.

- [ ] **Step 3: Implement**

Modify `ai_platform/tool_registry/repository.py` — add the method after
`list_for_conversation`:

```python
    async def list_by_request_id(self, request_id: str) -> list[ToolExecutionModel]:
        stmt = (
            select(ToolExecutionModel)
            .where(ToolExecutionModel.request_id == request_id)
            .order_by(ToolExecutionModel.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

(only this method is new; `list_for_conversation` and `record_execution`
above it are unchanged)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_tool_execution_repository.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/tool_registry/repository.py backend/tests/test_tool_execution_repository.py
git commit -m "feat: add ToolExecutionRepository.list_by_request_id

Lets the evaluation runner reconstruct a turn's actual, resolved tool
calls from the audit trail ToolExecutor already writes, instead of
adding a parameters field to ChatEvent."
```

---

### Task 10: `EvaluationRunner` — drives the real pipeline

**Files:**
- Create: `ai_platform/evaluation/runner.py`
- Create: `backend/tests/test_evaluation_runner.py`

**Interfaces:**
- Consumes: `ScriptedLLMService`, `RecordingLLMService`, `load_cassette`,
  `save_cassette` (Tasks 5-6); `EvalCase` (Task 3); `ActualToolCall`,
  `CaseOutcome` (Task 7); `ToolExecutionRepository.list_by_request_id`
  (Task 9); `ChatWorkflow`, `ChatRequest`, `ChatEvent`,
  `ExecutionPlanner`, `Planner`, `PromptBuilder`, `ConversationMemory`,
  `ConversationRepository`, `ToolExecutor` (all existing, unchanged).
- Produces: `class CaseStale(Exception)`; `async def run_case(db:
  AsyncSession, registry: ToolRegistry, case: EvalCase, *, mode: str =
  "recorded", record: bool = False, real_llm_service: LLMService | None
  = None, cassettes_root: Path | None = None) -> CaseOutcome` — this is
  what `run.py` (Task 13) calls once per case.

This task builds the whole runner (both `recorded` and `live`/`record`
modes) since the two modes are two branches of the same `_run_turn`
helper and can't be meaningfully reviewed as half a function; it proves
the default (`recorded`) path end-to-end with a real integration test.
Task 11 adds integration tests for the harder paths (live/record wiring,
multi-turn continuity) against this same, already-complete
implementation.

- [ ] **Step 1: Write the failing integration test (real pipeline, recorded mode)**

Create `backend/tests/test_evaluation_runner.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.cassette import save_cassette
from ai_platform.evaluation.runner import CaseStale, run_case
from ai_platform.evaluation.scoring import score_case
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    return registry


def _current_date_case(case_id: str) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id,
            "category": "current_date",
            "user_message": "What's today's date?",
            "expectations": {
                "expected_tools": [{"tool": "get_current_date", "parameters": {}}],
                "required_facts": ["Tuesday"],
            },
        }
    )


@pytest.mark.asyncio
async def test_run_case_drives_the_real_pipeline_in_recorded_mode(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_integration")
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday, July 14, 2026.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in outcome.tool_calls] == ["get_current_date"]
    assert outcome.tool_calls[0].parameters == {}
    assert outcome.response_text == "Today is Tuesday, July 14, 2026."
    assert outcome.clarification is None

    score = score_case(case, outcome)
    assert score.passed is True


@pytest.mark.asyncio
async def test_run_case_raises_case_stale_when_cassette_is_missing(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_no_cassette")

    with pytest.raises(CaseStale, match="current_date_no_cassette"):
        await run_case(db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path)


@pytest.mark.asyncio
async def test_run_case_result_fails_a_deliberately_wrong_expectation(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    """Negative control: proves score_case + run_case together produce a
    genuine failure, not a scorer that's silently always green."""
    case = EvalCase.model_validate(
        {
            "id": "wrong-expectation-case", "category": "current_date",
            "user_message": "What's today's date?",
            "expectations": {
                "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}]
            },
        }
    )
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path
    )
    await db_session.commit()

    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False
    assert "get_unpaid_invoices" in (score.failure_reason or "")
    assert "get_current_date" in (score.failure_reason or "")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.runner'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/runner.py`:

```python
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.cassette import (
    RecordingLLMService,
    ScriptedLLMService,
    load_cassette,
    save_cassette,
)
from ai_platform.evaluation.scoring import ActualToolCall, CaseOutcome
from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository


class CaseStale(Exception):
    """Raised in `recorded` mode when a turn's cassette is missing -
    either the prompt versions changed since it was recorded, or it was
    never recorded at all. Run with `--record` to (re)generate it.
    """


def _build_workflow(
    db: AsyncSession, registry: ToolRegistry, llm_service: LLMService, request_id: str
) -> ChatWorkflow:
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    prompt_builder = PromptBuilder()
    execution_repository = ToolExecutionRepository(db)
    tool_executor = ToolExecutor(registry, execution_repository, db)
    planner = Planner(llm_service, registry, prompt_builder)
    return ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id=request_id,
    )


async def _run_turn(
    db: AsyncSession,
    registry: ToolRegistry,
    *,
    case_id: str,
    turn: int,
    user_message: str,
    conversation_id: str | None,
    mode: str,
    real_llm_service: LLMService | None,
    record: bool,
    cassettes_root: Path | None,
) -> tuple[str, list[ChatEvent], bool]:
    request_id = f"eval-{case_id}-turn{turn}"
    recorder: RecordingLLMService | None = None

    if mode == "live":
        if real_llm_service is None:
            raise ValueError("live mode requires a real_llm_service")
        recorder = RecordingLLMService(real_llm_service)
        llm_service: LLMService = recorder
    else:
        cassette = load_cassette(case_id, turn, cassettes_root=cassettes_root)
        if cassette is None:
            raise CaseStale(
                f"{case_id} turn {turn}: no cassette for the current prompt version - "
                "run with --record"
            )
        llm_service = ScriptedLLMService(
            plan_response=cassette["plan_response"], response_text=cassette["response_text"]
        )

    workflow = _build_workflow(db, registry, llm_service, request_id)
    events = [
        e
        async for e in workflow.run(
            ChatRequest(
                session_id=f"eval-{case_id}", message=user_message, conversation_id=conversation_id
            )
        )
    ]
    await db.commit()

    stream_reply_called = getattr(llm_service, "stream_reply_called", False)

    if record and recorder is not None:
        if recorder.last_plan_response is None:
            raise RuntimeError(f"{case_id} turn {turn}: planner was never called while recording")
        save_cassette(
            case_id, turn,
            plan_response=recorder.last_plan_response,
            response_text=recorder.last_response_text or "",
            cassettes_root=cassettes_root,
        )

    new_conversation_id = conversation_id
    for event in events:
        if event.type == "done" and event.conversation_id is not None:
            new_conversation_id = event.conversation_id
    if new_conversation_id is None:
        raise RuntimeError(f"{case_id} turn {turn}: workflow never completed")
    return new_conversation_id, events, stream_reply_called


async def run_case(
    db: AsyncSession,
    registry: ToolRegistry,
    case: EvalCase,
    *,
    mode: str = "recorded",
    record: bool = False,
    real_llm_service: LLMService | None = None,
    cassettes_root: Path | None = None,
) -> CaseOutcome:
    conversation_id: str | None = None
    turn = 0
    for setup_turn in case.conversation_setup:
        conversation_id, _, _ = await _run_turn(
            db, registry, case_id=case.id, turn=turn, user_message=setup_turn.user_message,
            conversation_id=conversation_id, mode=mode, real_llm_service=real_llm_service,
            record=record, cassettes_root=cassettes_root,
        )
        turn += 1

    conversation_id, events, stream_reply_called = await _run_turn(
        db, registry, case_id=case.id, turn=turn, user_message=case.user_message,
        conversation_id=conversation_id, mode=mode, real_llm_service=real_llm_service,
        record=record, cassettes_root=cassettes_root,
    )

    response_text = "".join(
        e.content for e in events if e.type == "token" and e.content is not None
    )
    clarification = None if stream_reply_called else (response_text or None)

    execution_repository = ToolExecutionRepository(db)
    executions = await execution_repository.list_by_request_id(f"eval-{case.id}-turn{turn}")
    tool_calls = [ActualToolCall(tool=e.tool, parameters=e.parameters) for e in executions]

    return CaseOutcome(
        tool_calls=tool_calls, response_text=response_text, clarification=clarification
    )
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_runner.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/runner.py backend/tests/test_evaluation_runner.py
git commit -m "feat: add EvaluationRunner.run_case driving the real chat pipeline

Builds a real ChatWorkflow per turn (real Planner/ExecutionPlanner/
ToolExecutor/PromptBuilder, only the LLMService swapped), reads actual
tool calls back from application.tool_executions, and returns a
CaseOutcome for scoring. Includes the milestone's required real-pipeline
integration test and a negative-control test proving a wrong expectation
fails non-vacuously."
```

---

### Task 11: Runner integration tests — live/record wiring and multi-turn replay

**Files:**
- Modify: `backend/tests/test_evaluation_runner.py`

**Interfaces:**
- Consumes: `run_case`, `CaseStale` (Task 10) — no production code
  changes in this task, only deeper test coverage of the already-shipped
  implementation.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_evaluation_runner.py`:

```python
from datetime import date
from decimal import Decimal

from ai_platform.evaluation.cassette import load_cassette
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL


def _followup_registry() -> ToolRegistry:
    registry = _registry()
    registry.register(GET_CUSTOMER_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    return registry


class _FakeRealLLMService:
    def __init__(self, plan_response: str, response_text: str) -> None:
        self._plan_response = plan_response
        self._response_text = response_text

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response

    async def stream_reply(self, system: str, history: list[dict[str, str]], message: str):
        yield self._response_text


@pytest.mark.asyncio
async def test_run_case_live_mode_with_record_writes_a_replayable_cassette(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_record_roundtrip")
    fake_real_service = _FakeRealLLMService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday, July 14, 2026.",
    )

    live_outcome = await run_case(
        db_session, _registry(), case, mode="live", record=True,
        real_llm_service=fake_real_service, cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in live_outcome.tool_calls] == ["get_current_date"]

    cassette = load_cassette(case.id, 0, cassettes_root=tmp_path)
    assert cassette is not None
    expected_plan = '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    assert cassette["plan_response"] == expected_plan
    assert cassette["response_text"] == "Today is Tuesday, July 14, 2026."

    replayed_outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()
    assert replayed_outcome.response_text == live_outcome.response_text
    replayed_tools = [tc.tool for tc in replayed_outcome.tool_calls]
    live_tools = [tc.tool for tc in live_outcome.tool_calls]
    assert replayed_tools == live_tools


@pytest.mark.asyncio
async def test_run_case_replays_a_two_turn_piped_follow_up_case(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9001", company_name="Anchor Components", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-9001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("6534.00"), tax=Decimal("0"), total=Decimal("6534.00"),
    )
    await db_session.commit()

    case = EvalCase.model_validate(
        {
            "id": "followup_replay_test", "category": "follow_up", "tests_memory": True,
            "conversation_setup": [{"user_message": "Show overdue invoices"}],
            "user_message": "Which of those belong to Anchor Components?",
            "expectations": {
                "expected_tools": [
                    {"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}},
                    {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
                ],
                "required_facts": ["6534.00"],
            },
        }
    )
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
        response_text="Here are the overdue invoices.",
        cassettes_root=tmp_path,
    )
    save_cassette(
        case.id, 1,
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
        response_text="Anchor Components has one overdue invoice for $6,534.00.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _followup_registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in outcome.tool_calls] == ["get_customer", "get_overdue_invoices"]
    assert outcome.tool_calls[1].parameters["customer_id"] == "CUST-9001"

    score = score_case(case, outcome)
    assert score.passed is True
```

- [ ] **Step 2: Run it to confirm it fails, then passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_runner.py -v`
Expected: since `run_case`/`load_cassette` already exist from Tasks 5/10,
this should run and PASS immediately with no implementation change
needed — if anything fails, it's a genuine bug in the existing
`runner.py`/`cassette.py`, not a missing feature; fix `runner.py` (not
the test) until all tests pass. All 5 tests in the file should be green.

- [ ] **Step 3: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_evaluation_runner.py
git commit -m "test: cover live/record cassette round-trip and two-turn replay

Proves --record writes a cassette that recorded mode can then replay
identically, and that a hand-authored two-cassette follow-up case
replays with genuine conversation continuity and $stepN.field piping
resolved to a real customer_code across turns."
```

---

## Phase E — Report, CLI, and CI

### Task 12: Scorecard rendering (`report.py`)

**Files:**
- Create: `ai_platform/evaluation/report.py`
- Create: `backend/tests/test_evaluation_report.py`

**Interfaces:**
- Consumes: `EvalCase` (Task 3), `CaseScore` (Task 7).
- Produces: `render_scorecard(*, suite: str, mode: str, cases:
  list[EvalCase], scores: list[CaseScore], metrics: dict[str, float],
  stale_case_ids: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evaluation_report.py`:

```python
from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.report import render_scorecard
from ai_platform.evaluation.scoring import CaseScore


def _case(case_id: str, category: str) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id, "category": category, "user_message": "x",
            "expectations": {"expected_tools": [{"tool": "get_current_date", "parameters": {}}]},
        }
    )


def _score(passed: bool, reason: str | None = None) -> CaseScore:
    return CaseScore(
        passed=passed, score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": passed, "parameters_correct": True,
            "clarification_correct": True, "hallucinated": False,
            "required_facts_present": True,
        },
        parameter_pairs_matched=0, parameter_pairs_total=0, failure_reason=reason,
    )


def test_scorecard_includes_suite_mode_categories_and_totals() -> None:
    cases = [_case("case-1", "unpaid_invoices"), _case("case-2", "unpaid_invoices")]
    scores = [_score(True), _score(False, "expected get_current_date, got get_unpaid_invoices")]
    metrics = {
        "tool_selection_accuracy": 0.5, "parameter_accuracy": 1.0,
        "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
    }

    report = render_scorecard(
        suite="core", mode="recorded", cases=cases, scores=scores, metrics=metrics,
        stale_case_ids=[],
    )

    assert "core" in report
    assert "recorded" in report
    assert "unpaid_invoices" in report
    assert "case-1" in report and "PASS" in report
    assert "case-2" in report and "FAIL" in report
    assert "expected get_current_date, got get_unpaid_invoices" in report
    assert "1/2 passed" in report
    assert "Tool-selection accuracy: 50.0%" in report


def test_scorecard_lists_stale_cases() -> None:
    report = render_scorecard(
        suite="core", mode="recorded", cases=[], scores=[],
        metrics={
            "tool_selection_accuracy": 1.0, "parameter_accuracy": 1.0,
            "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
        },
        stale_case_ids=["current_date_basic"],
    )
    assert "STALE" in report
    assert "current_date_basic" in report
    assert "--record" in report


def test_scorecard_with_no_stale_cases_omits_the_stale_section() -> None:
    report = render_scorecard(
        suite="core", mode="recorded", cases=[], scores=[],
        metrics={
            "tool_selection_accuracy": 1.0, "parameter_accuracy": 1.0,
            "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
        },
        stale_case_ids=[],
    )
    assert "STALE" not in report
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.report'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/report.py`:

```python
from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.scoring import CaseScore


def render_scorecard(
    *,
    suite: str,
    mode: str,
    cases: list[EvalCase],
    scores: list[CaseScore],
    metrics: dict[str, float],
    stale_case_ids: list[str],
) -> str:
    lines: list[str] = [f"Evaluation suite: {suite} (mode={mode})", "=" * 60]

    by_category: dict[str, list[tuple[EvalCase, CaseScore]]] = {}
    for case, score in zip(cases, scores, strict=True):
        by_category.setdefault(case.category, []).append((case, score))

    for category, pairs in sorted(by_category.items()):
        passed = sum(1 for _, score in pairs if score.passed)
        lines.append(f"{category}: {passed}/{len(pairs)} passed")
        for case, score in pairs:
            marker = "PASS" if score.passed else "FAIL"
            suffix = f" - {score.failure_reason}" if score.failure_reason else ""
            lines.append(f"  [{marker}] {case.id}{suffix}")

    lines.append("-" * 60)
    total_passed = sum(1 for score in scores if score.passed)
    lines.append(f"Total: {total_passed}/{len(scores)} passed")
    lines.append(f"Tool-selection accuracy: {metrics['tool_selection_accuracy']:.1%}")
    lines.append(f"Parameter accuracy: {metrics['parameter_accuracy']:.1%}")
    lines.append(f"Memory usage accuracy: {metrics['memory_usage_accuracy']:.1%}")
    lines.append(f"Hallucination rate: {metrics['hallucination_rate']:.1%}")

    if stale_case_ids:
        lines.append("-" * 60)
        lines.append(
            f"STALE ({len(stale_case_ids)}) - prompt changed or never recorded, "
            "run with --record:"
        )
        for case_id in stale_case_ids:
            lines.append(f"  ! {case_id}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_report.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/evaluation/report.py backend/tests/test_evaluation_report.py
git commit -m "feat: add render_scorecard for the evaluation CLI's stdout report

Per-category pass/fail breakdown, the four named aggregate metrics, and
a STALE section listing cases whose cassette no longer matches the
current prompt versions."
```

---

### Task 13: CLI (`run.py`)

**Files:**
- Create: `ai_platform/evaluation/run.py`
- Create: `backend/tests/test_evaluation_cli.py`

**Interfaces:**
- Consumes: `load_suite` (Task 4), `EvaluationRepository` (Task 2),
  `run_case`, `CaseStale` (Task 10), `score_case`, `aggregate_metrics`
  (Tasks 7-8), `render_scorecard` (Task 12), `app.core.tool_registry.
  get_tool_registry`, `app.api.chat.get_llm_service`,
  `app.db.session.get_sessionmaker` (all existing).
- Produces: `async def run_suite(*, suite: str, mode: str, record: bool,
  case_filter: str | None, registry: ToolRegistry, real_llm_service:
  LLMService | None, evals_root: Path | None = None, cassettes_root:
  Path | None = None) -> tuple[str, bool]` (report text, all_passed) —
  the CLI's testable core; `def main() -> None` — the `python -m
  ai_platform.evaluation.run` entrypoint, which calls `run_suite` with
  the real paths and `sys.exit`s with the right code.

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/test_evaluation_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.cassette import save_cassette
from ai_platform.evaluation.models import EvaluationResultModel, EvaluationRunModel
from ai_platform.evaluation.run import run_suite
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL


def _write_suite(evals_root: Path, suite: str, case_id: str) -> None:
    suite_dir = evals_root / suite
    suite_dir.mkdir(parents=True)
    (suite_dir / f"{case_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": case_id, "category": "current_date", "user_message": "What's today's date?",
                "expectations": {
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}]
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_run_suite_passes_persists_results_and_reports_pass(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_cli_case")
    save_cassette(
        "current_date_cli_case", 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    report, all_passed = await run_suite(
        suite="smoke", mode="recorded", record=False, case_filter=None,
        registry=registry, real_llm_service=None,
        evals_root=evals_root, cassettes_root=cassettes_root,
    )

    assert all_passed is True
    assert "PASS" in report
    assert "current_date_cli_case" in report
    assert "Total: 1/1 passed" in report

    runs = (await db_session.execute(select(EvaluationRunModel))).scalars().all()
    assert len(runs) == 1
    assert runs[0].total_cases == 1
    assert runs[0].passed_cases == 1

    results = (await db_session.execute(select(EvaluationResultModel))).scalars().all()
    assert len(results) == 1
    assert results[0].passed is True


@pytest.mark.asyncio
async def test_run_suite_reports_failure_when_cassette_is_stale(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_stale_case")
    # deliberately no cassette written

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    report, all_passed = await run_suite(
        suite="smoke", mode="recorded", record=False, case_filter=None,
        registry=registry, real_llm_service=None,
        evals_root=evals_root, cassettes_root=cassettes_root,
    )

    assert all_passed is False
    assert "STALE" in report
    assert "current_date_stale_case" in report


@pytest.mark.asyncio
async def test_run_suite_case_filter_runs_only_that_case(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_cli_case")
    save_cassette(
        "current_date_cli_case", 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    with pytest.raises(ValueError, match="No case 'missing-case'"):
        await run_suite(
            suite="smoke", mode="recorded", record=False, case_filter="missing-case",
            registry=registry, real_llm_service=None,
            evals_root=evals_root, cassettes_root=cassettes_root,
        )
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.evaluation.run'`.

- [ ] **Step 3: Implement**

Create `ai_platform/evaluation/run.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from ai_platform.evaluation.loader import load_suite
from ai_platform.evaluation.repository import EvaluationRepository
from ai_platform.evaluation.report import render_scorecard
from ai_platform.evaluation.runner import CaseStale, run_case
from ai_platform.evaluation.scoring import CaseScore, aggregate_metrics, score_case
from ai_platform.llm.service import LLMService
from ai_platform.prompts.planning_prompt import VERSION as PLANNING_PROMPT_VERSION
from ai_platform.prompts.system_prompt import VERSION as SYSTEM_PROMPT_VERSION
from ai_platform.tool_registry.registry import ToolRegistry
from app.api.chat import get_llm_service
from app.core.tool_registry import get_tool_registry
from app.db.session import get_sessionmaker

_STALE_METRICS = {
    "tool_selection_correct": False, "parameters_correct": False,
    "clarification_correct": False, "hallucinated": False,
    "required_facts_present": False,
}


def _stale_score() -> CaseScore:
    return CaseScore(
        passed=False, score=0.0, metrics=dict(_STALE_METRICS),
        parameter_pairs_matched=0, parameter_pairs_total=0,
        failure_reason="stale cassette - run with --record",
    )


async def run_suite(
    *,
    suite: str,
    mode: str,
    record: bool,
    case_filter: str | None,
    registry: ToolRegistry,
    real_llm_service: LLMService | None,
    evals_root: Path | None = None,
    cassettes_root: Path | None = None,
) -> tuple[str, bool]:
    cases = load_suite(suite, evals_root=evals_root)
    if case_filter is not None:
        cases = [c for c in cases if c.id == case_filter]
        if not cases:
            raise ValueError(f"No case '{case_filter}' in suite '{suite}'")

    sessionmaker = get_sessionmaker()
    scores: list[CaseScore] = []
    stale_case_ids: list[str] = []

    async with sessionmaker() as db:
        evaluation_repository = EvaluationRepository(db)
        run_row = await evaluation_repository.create_run(
            suite=suite, mode=mode,
            planning_prompt_version=PLANNING_PROMPT_VERSION,
            system_prompt_version=SYSTEM_PROMPT_VERSION,
        )
        await db.commit()

        for case in cases:
            case_row = await evaluation_repository.upsert_case(
                case_id=case.id, category=case.category, suite=suite,
                definition=case.model_dump(mode="json"),
            )
            await db.commit()

            try:
                outcome = await run_case(
                    db, registry, case, mode=mode, record=record,
                    real_llm_service=real_llm_service, cassettes_root=cassettes_root,
                )
            except CaseStale:
                stale_case_ids.append(case.id)
                scores.append(_stale_score())
                continue

            score = score_case(case, outcome)
            await evaluation_repository.record_result(
                run_id=run_row.id, case_id=case_row.id,
                expected=case.expectations.model_dump(mode="json"),
                actual={
                    "tool_calls": [
                        {"tool": tc.tool, "parameters": tc.parameters} for tc in outcome.tool_calls
                    ],
                    "response_text": outcome.response_text,
                    "clarification": outcome.clarification,
                },
                passed=score.passed, score=score.score, metrics=score.metrics,
                failure_reason=score.failure_reason,
            )
            await db.commit()
            scores.append(score)

        metrics = aggregate_metrics(cases, scores)
        overall_score = (
            Decimal(str(sum(s.score for s in scores) / len(scores))) if scores else Decimal("0")
        )
        await evaluation_repository.finish_run(
            run_id=run_row.id, total_cases=len(cases),
            passed_cases=sum(1 for s in scores if s.passed),
            overall_score=overall_score, metrics=metrics,
        )
        await db.commit()

    report = render_scorecard(
        suite=suite, mode=mode, cases=cases, scores=scores, metrics=metrics,
        stale_case_ids=stale_case_ids,
    )
    all_passed = all(s.passed for s in scores) and not stale_case_ids
    return report, all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI evaluation suite.")
    parser.add_argument("--suite", required=True, help="Suite name under evals/, e.g. 'core'.")
    parser.add_argument(
        "--mode", choices=["recorded", "live"], default="recorded",
        help="'recorded' replays cassettes (default, deterministic); 'live' calls the real LLM.",
    )
    parser.add_argument(
        "--record", action="store_true",
        help="Call the real LLM and (re)write cassettes. Implies --mode live.",
    )
    parser.add_argument("--case", default=None, help="Run only this case id.")
    args = parser.parse_args()

    mode = "live" if args.record else args.mode
    registry = get_tool_registry()
    real_llm_service = get_llm_service() if mode == "live" else None

    try:
        report, all_passed = asyncio.run(
            run_suite(
                suite=args.suite, mode=mode, record=args.record, case_filter=args.case,
                registry=registry, real_llm_service=real_llm_service,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(report)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_evaluation_cli.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Manually confirm the real CLI entrypoint imports cleanly**

Run: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --help`
Expected: prints the argparse help text (`--suite`, `--mode`, `--record`,
`--case`) with no import errors — this only proves the module and its
`app.*` imports load correctly; it does not run any suite (no `--suite`
given, so argparse exits after printing help).

- [ ] **Step 6: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add ai_platform/evaluation/run.py backend/tests/test_evaluation_cli.py
git commit -m "feat: add the evaluation CLI entrypoint

python -m ai_platform.evaluation.run --suite core [--mode recorded|live]
[--record] [--case ID] - loads the suite, runs every case through the
real pipeline, persists an evaluation_runs/evaluation_results row per
case, prints a scorecard, and exits non-zero on any failure or STALE
case so it gates CI."
```

---

### Task 14: CI job for the deterministic subset

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `python -m ai_platform.evaluation.run` (Task 13), the seed
  suite under `evals/core/` and its cassettes under `evals/cassettes/`
  (Tasks 15-21 — this task can be implemented before those exist, but
  the job won't pass CI until Task 21 commits a full, passing `core`
  suite; that's expected and is what Task 21 verifies).

- [ ] **Step 1: Add the job**

Modify `.github/workflows/ci.yml` — add a new job after `backend` (same
file, same indentation level as `backend`/`frontend`):

```yaml
  evaluation:
    name: Evaluation (deterministic subset)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: ci_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -e ..
          pip install -e ".[dev]"

      - name: Apply migrations
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ci_test
        run: alembic upgrade head

      - name: Run deterministic evaluation suite
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ci_test
        run: python -m ai_platform.evaluation.run --suite core --mode recorded
```

(this job needs no `LLM_API_KEY` at all — `recorded` mode never
constructs a real `LLMService`; every case replays from the committed
`evals/cassettes/*.json` files)

- [ ] **Step 2: Confirm the workflow file is valid YAML**

Run: `cd "D:/New-Automation/AI-FinanceAssistant" && python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"`
Expected: prints `valid`.

(this only checks the file parses; the job itself can't run green until
Task 21 commits a full, passing `core` suite with cassettes — that's
expected at this point in the plan)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run the deterministic evaluation subset on every PR

New evaluation job replays evals/core's committed cassettes (mode=
recorded) - no LLM_API_KEY needed in CI. Won't go green until Task 21
commits a full, passing core suite with cassettes."
```

---

## Phase F — The Seed Suite

Tasks 15-20 author the 30 `evals/core/*.yaml` cases. Every seeded value
below (customer/vendor names, invoice numbers, amounts, dates) was
queried directly from the live seed=42 database on 2026-07-13:

```
docker compose exec postgres psql -U postgres -d ai_employee_platform -c "
SELECT c.company_name, c.customer_code, i.invoice_number, i.total, i.balance, i.due_date, i.status
FROM finance.customers c JOIN finance.invoices i ON i.customer_id = c.id
WHERE i.status = 'overdue' ORDER BY i.due_date LIMIT 8;"
```
→ Granite Systems (CUST-0013) INV-7051 total=21060.00 due=2025-03-14;
Anchor Components (CUST-0003) INV-7014 total=6534.00 due=2025-03-25 and
INV-7154 total=72063.00 due=2025-03-31; Summit Systems (CUST-0012)
INV-7163 total=63234.00 due=2025-04-03.

```
SELECT c.company_name, c.customer_code, SUM(i.balance), COUNT(*), MIN(i.due_date)
FROM finance.customers c JOIN finance.invoices i ON i.customer_id = c.id
WHERE c.company_name = 'Anchor Components' AND i.status IN ('sent','partially_paid','overdue')
GROUP BY c.company_name, c.customer_code;"
```
→ Anchor Components total_outstanding=188446.50 (5 invoices).

```
SELECT ba.opening_balance + COALESCE(SUM(ct.amount),0)
FROM finance.bank_accounts ba LEFT JOIN finance.cash_transactions ct
  ON ct.bank_account_id = ba.id AND ct.transaction_date <= CURRENT_DATE
GROUP BY ba.opening_balance;"
```
→ current cash balance = 918201.30 (stable: the ledger's latest
transaction date is 2026-07-08, `SIMULATION_TODAY`, which is already in
the past relative to any real invocation of this suite).

```
SELECT v.company_name, v.vendor_code, vi.vendor_invoice_number, vi.total, vi.balance, vi.due_date
FROM finance.vendors v JOIN finance.vendor_invoices vi ON vi.vendor_id = v.id
WHERE vi.status IN ('sent','partially_paid','overdue') ORDER BY vi.due_date LIMIT 6;"
```
→ Cascade Industries (VEND-0013) VINV-4008 total=92700.00 balance=64890.00
due=2025-04-14; Pioneer Manufacturing (VEND-0011) VINV-4003
total=balance=203600.00 due=2025-04-29.

```
SELECT COUNT(*) FROM finance.invoices WHERE invoice_number = 'INV-99999';
SELECT COUNT(*) FROM finance.customers WHERE company_name ILIKE '%Fictional%';
```
→ both `0` — confirmed nonexistent, safe hallucination-trap identifiers.

Every case file has this shape (Task 3's `EvalCase`/`Expectations`
schema) and is validated the same way (Step 2 of each task below).

### Task 15: Seed cases — the 5 unpaid-invoice phrasings

**Files:**
- Create: `evals/core/unpaid_invoices_show.yaml`
- Create: `evals/core/unpaid_invoices_outstanding.yaml`
- Create: `evals/core/unpaid_invoices_not_paid_for.yaml`
- Create: `evals/core/unpaid_invoices_open_right_now.yaml`
- Create: `evals/core/unpaid_invoices_not_settled.yaml`

- [ ] **Step 1: Write the five case files**

Create `evals/core/unpaid_invoices_show.yaml`:

```yaml
id: unpaid_invoices_show
category: unpaid_invoices
user_message: "Show me all unpaid invoices"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}
```

Create `evals/core/unpaid_invoices_outstanding.yaml`:

```yaml
id: unpaid_invoices_outstanding
category: unpaid_invoices
user_message: "What invoices are still outstanding?"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}
```

Create `evals/core/unpaid_invoices_not_paid_for.yaml`:

```yaml
id: unpaid_invoices_not_paid_for
category: unpaid_invoices
user_message: "List invoices we haven't been paid for yet"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}
```

Create `evals/core/unpaid_invoices_open_right_now.yaml`:

```yaml
id: unpaid_invoices_open_right_now
category: unpaid_invoices
user_message: "Which invoices are open right now?"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}
```

Create `evals/core/unpaid_invoices_not_settled.yaml`:

```yaml
id: unpaid_invoices_not_settled
category: unpaid_invoices
user_message: "Do we have any invoices that haven't been settled?"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters: {}
```

- [ ] **Step 2: Confirm the suite loads**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; cases = load_suite('core'); print(len(cases)); print([c.id for c in cases])"`
Expected: prints `5` and the five case ids listed above, in alphabetical
filename order.

- [ ] **Step 3: Run lint/type checks (unaffected, confirms no regression)**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: all still passing (YAML files aren't Python, nothing to lint).

- [ ] **Step 4: Commit**

```bash
git add evals/core/unpaid_invoices_show.yaml evals/core/unpaid_invoices_outstanding.yaml evals/core/unpaid_invoices_not_paid_for.yaml evals/core/unpaid_invoices_open_right_now.yaml evals/core/unpaid_invoices_not_settled.yaml
git commit -m "test: add the 5 unpaid-invoice phrasing eval cases

All five distinct natural phrasings must plan get_unpaid_invoices with
no parameters - the milestone's first named acceptance requirement."
```

---

### Task 16: Seed cases — overdue, search, balances, vendor invoices, cash, current date

**Files:**
- Create: `evals/core/overdue_invoices_basic.yaml`
- Create: `evals/core/search_invoices_due_before_and_min_amount.yaml`
- Create: `evals/core/search_invoices_by_number.yaml`
- Create: `evals/core/customer_balance_anchor.yaml`
- Create: `evals/core/customer_balance_granite.yaml`
- Create: `evals/core/vendor_balance_cascade.yaml`
- Create: `evals/core/vendor_balance_pioneer.yaml`
- Create: `evals/core/vendor_invoices_basic.yaml`
- Create: `evals/core/payment_prioritization.yaml`
- Create: `evals/core/cash_position_basic.yaml`
- Create: `evals/core/current_date_basic.yaml`
- Create: `evals/core/current_date_day_of_week.yaml`

- [ ] **Step 1: Write the twelve case files**

Create `evals/core/overdue_invoices_basic.yaml`:

```yaml
id: overdue_invoices_basic
category: overdue_invoices
user_message: "Which invoices are overdue?"
expectations:
  expected_tools:
    - tool: get_overdue_invoices
      parameters: {}
  required_facts:
    - "Granite Systems"
```

Create `evals/core/search_invoices_due_before_and_min_amount.yaml`:

```yaml
id: search_invoices_due_before_and_min_amount
category: parameter_extraction
user_message: "Find invoices due before June 1, 2025 for at least $40,000"
expectations:
  expected_tools:
    - tool: search_invoices
      parameters:
        due_before: "2025-06-01"
        minimum_amount: 40000
  required_facts:
    - "Anchor Components"
    - "72063.00"
```

Create `evals/core/search_invoices_by_number.yaml`:

```yaml
id: search_invoices_by_number
category: parameter_extraction
user_message: "Can you look up invoice INV-7051 for me?"
expectations:
  expected_tools:
    - tool: search_invoices
      parameters:
        invoice_number: "INV-7051"
  required_facts:
    - "Granite Systems"
    - "21060.00"
```

Create `evals/core/customer_balance_anchor.yaml`:

```yaml
id: customer_balance_anchor
category: parameter_extraction
user_message: "What does Anchor Components owe us?"
expectations:
  expected_tools:
    - tool: get_customer_balance
      parameters:
        customer_name: "Anchor Components"
  required_facts:
    - "188446.50"
```

Create `evals/core/customer_balance_granite.yaml`:

```yaml
id: customer_balance_granite
category: parameter_extraction
user_message: "How much does Granite Systems owe us?"
expectations:
  expected_tools:
    - tool: get_customer_balance
      parameters:
        customer_name: "Granite Systems"
  required_facts:
    - "Granite Systems"
```

Create `evals/core/vendor_balance_cascade.yaml`:

```yaml
id: vendor_balance_cascade
category: parameter_extraction
user_message: "What do we owe Cascade Industries?"
expectations:
  expected_tools:
    - tool: get_vendor_balance
      parameters:
        vendor_name: "Cascade Industries"
  required_facts:
    - "64890.00"
```

Create `evals/core/vendor_balance_pioneer.yaml`:

```yaml
id: vendor_balance_pioneer
category: parameter_extraction
user_message: "How much do we owe Pioneer Manufacturing?"
expectations:
  expected_tools:
    - tool: get_vendor_balance
      parameters:
        vendor_name: "Pioneer Manufacturing"
  required_facts:
    - "203600.00"
```

Create `evals/core/vendor_invoices_basic.yaml`:

```yaml
id: vendor_invoices_basic
category: vendor_invoices
user_message: "Show me our vendor invoices"
expectations:
  expected_tools:
    - tool: get_vendor_invoices
      parameters: {}
```

Create `evals/core/payment_prioritization.yaml`:

```yaml
id: payment_prioritization
category: reasoning
user_message: "Which invoices should I pay first?"
expectations:
  expected_tools:
    - tool: get_vendor_invoices
      parameters: {}
    - tool: get_cash_position
      parameters: {}
  required_facts:
    - "918201.30"
```

Create `evals/core/cash_position_basic.yaml`:

```yaml
id: cash_position_basic
category: cash_position
user_message: "What's our current cash position?"
expectations:
  expected_tools:
    - tool: get_cash_position
      parameters: {}
  required_facts:
    - "918201.30"
```

Create `evals/core/current_date_basic.yaml`:

```yaml
id: current_date_basic
category: current_date
user_message: "What's today's date?"
expectations:
  expected_tools:
    - tool: get_current_date
      parameters: {}
```

Create `evals/core/current_date_day_of_week.yaml`:

```yaml
id: current_date_day_of_week
category: current_date
user_message: "What day of the week is it?"
expectations:
  expected_tools:
    - tool: get_current_date
      parameters: {}
```

Note on `payment_prioritization`'s `expected_tools` order: the planning
prompt's own worked example (`ai_platform/prompts/planning_prompt.py`,
the reasoning-query pattern added in Milestone 7) lists
`get_vendor_invoices()` before `get_cash_position()`, so a real model is
expected to follow that order consistently — but if Task 21's recording
step shows the real model reliably emitting the other order instead,
swap this file's `expected_tools` order to match reality rather than
forcing the model to match the file (the file documents observed
correct behavior, it doesn't prescribe an arbitrary one).

- [ ] **Step 2: Confirm the suite loads with 17 cases total**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; print(len(load_suite('core')))"`
Expected: prints `17`.

- [ ] **Step 3: Commit**

```bash
git add evals/core/overdue_invoices_basic.yaml evals/core/search_invoices_due_before_and_min_amount.yaml evals/core/search_invoices_by_number.yaml evals/core/customer_balance_anchor.yaml evals/core/customer_balance_granite.yaml evals/core/vendor_balance_cascade.yaml evals/core/vendor_balance_pioneer.yaml evals/core/vendor_invoices_basic.yaml evals/core/payment_prioritization.yaml evals/core/cash_position_basic.yaml evals/core/current_date_basic.yaml evals/core/current_date_day_of_week.yaml
git commit -m "test: add overdue/search/balance/vendor/cash/date eval cases

Covers parameter extraction (dates, amounts, names), get_overdue_invoices,
search_invoices, get_customer_balance, get_vendor_balance,
get_vendor_invoices, get_cash_position, get_current_date, and the
payment-prioritization reasoning scenario - Milestone 7's second named
acceptance scenario, now under continuous measurement."
```

---

### Task 17: Seed cases — follow-up reference resolution (memory)

**Files:**
- Create: `evals/core/followup_those_anchor.yaml`
- Create: `evals/core/followup_total_for_granite.yaml`

- [ ] **Step 1: Write the two case files**

Create `evals/core/followup_those_anchor.yaml`:

```yaml
id: followup_those_anchor
category: follow_up
tests_memory: true
conversation_setup:
  - user_message: "Show overdue invoices"
user_message: "Which of those belong to Anchor Components?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Anchor Components"
    - tool: get_overdue_invoices
      parameters:
        customer_id: "<piped>"
  required_facts:
    - "6534.00"
```

Create `evals/core/followup_total_for_granite.yaml`:

```yaml
id: followup_total_for_granite
category: follow_up
tests_memory: true
conversation_setup:
  - user_message: "Show overdue invoices"
user_message: "Is Granite Systems one of those?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Granite Systems"
    - tool: get_overdue_invoices
      parameters:
        customer_id: "<piped>"
  required_facts:
    - "21060.00"
```

These are Milestone 7's own first named acceptance scenario (§`followup_those_anchor`
uses the exact PRD phrasing pattern, substituting the real seeded
"Anchor Components"), now measured continuously rather than only
covered by the one-off `test_eval_those_follow_up_resolves_customer_name_via_piping`
eval test from Milestone 7 Task 27. `followup_total_for_granite` proves
the pattern generalizes to a second customer, not just the one it was
first built for.

- [ ] **Step 2: Confirm the suite loads with 19 cases total**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; print(len(load_suite('core')))"`
Expected: prints `19`.

- [ ] **Step 3: Commit**

```bash
git add evals/core/followup_those_anchor.yaml evals/core/followup_total_for_granite.yaml
git commit -m "test: add two follow-up reference-resolution eval cases

Both tests_memory: true, both prove a two-step get_customer ->
get_overdue_invoices piped plan across a conversation turn boundary."
```

---

### Task 18: Seed cases — ambiguity requiring a clarifying question

**Files:**
- Create: `evals/core/ambiguous_show_invoices.yaml`
- Create: `evals/core/ambiguous_show_payments.yaml`
- Create: `evals/core/ambiguous_how_much_do_we_owe.yaml`

- [ ] **Step 1: Write the three case files**

Create `evals/core/ambiguous_show_invoices.yaml`:

```yaml
id: ambiguous_show_invoices
category: ambiguity
user_message: "Show invoices"
expectations:
  expected_clarification: true
```

Create `evals/core/ambiguous_show_payments.yaml`:

```yaml
id: ambiguous_show_payments
category: ambiguity
user_message: "Show payments"
expectations:
  expected_clarification: true
```

Create `evals/core/ambiguous_how_much_do_we_owe.yaml`:

```yaml
id: ambiguous_how_much_do_we_owe
category: ambiguity
user_message: "How much do we owe?"
expectations:
  expected_clarification: true
```

`ambiguous_show_invoices` is PRD's own worked example of an ambiguous
request. `ambiguous_show_payments` has no tool that cleanly matches a
raw, unqualified "payments" (customer payments vs. vendor payments vs.
the cash ledger). `ambiguous_how_much_do_we_owe` is missing the vendor
name `get_vendor_balance` strictly requires (`vendor_name: str`, no
default) — the planner should ask which vendor rather than guessing one.

- [ ] **Step 2: Confirm the suite loads with 22 cases total**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; print(len(load_suite('core')))"`
Expected: prints `22`.

- [ ] **Step 3: Commit**

```bash
git add evals/core/ambiguous_show_invoices.yaml evals/core/ambiguous_show_payments.yaml evals/core/ambiguous_how_much_do_we_owe.yaml
git commit -m "test: add three ambiguity eval cases requiring clarification

Each is genuinely ambiguous or missing a required parameter with no
sensible default - the planner must ask, not guess."
```

---

### Task 19: Seed cases — hallucination traps

**Files:**
- Create: `evals/core/hallucination_invoice_not_found.yaml`
- Create: `evals/core/hallucination_customer_not_found.yaml`
- Create: `evals/core/hallucination_vendor_not_found.yaml`

- [ ] **Step 1: Write the three case files**

Create `evals/core/hallucination_invoice_not_found.yaml`:

```yaml
id: hallucination_invoice_not_found
category: hallucination
user_message: "What's invoice INV-99999?"
expectations:
  expected_tools:
    - tool: search_invoices
      parameters:
        invoice_number: "INV-99999"
  forbidden_content:
    - "INV-7051"
    - "INV-7014"
```

Create `evals/core/hallucination_customer_not_found.yaml`:

```yaml
id: hallucination_customer_not_found
category: hallucination
user_message: "What does Fictional Nonexistent Co owe us?"
expectations:
  expected_tools:
    - tool: get_customer_balance
      parameters:
        customer_name: "Fictional Nonexistent Co"
  forbidden_content:
    - "188446.50"
```

Create `evals/core/hallucination_vendor_not_found.yaml`:

```yaml
id: hallucination_vendor_not_found
category: hallucination
user_message: "What do we owe Fictional Vendor Co?"
expectations:
  expected_tools:
    - tool: get_vendor_balance
      parameters:
        vendor_name: "Fictional Vendor Co"
  forbidden_content:
    - "64890.00"
```

`INV-99999`/`Fictional Nonexistent Co`/`Fictional Vendor Co` were all
confirmed absent from the seed=42 database (§ query at the top of Phase
F). Each `forbidden_content` value is a **real** figure belonging to a
*different*, unrelated entity (Granite Systems' `INV-7051`, Anchor
Components' `INV-7014`, Anchor's own outstanding balance, Cascade
Industries' vendor balance) — its appearance in a response about a
nonexistent identifier proves the model fabricated or conflated data,
since there is no correct reason for it to appear. None of these cases
assert `required_facts`, since the correct wording of "I couldn't find
that" varies and shouldn't be over-constrained.

- [ ] **Step 2: Confirm the suite loads with 25 cases total**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; print(len(load_suite('core')))"`
Expected: prints `25`.

- [ ] **Step 3: Commit**

```bash
git add evals/core/hallucination_invoice_not_found.yaml evals/core/hallucination_customer_not_found.yaml evals/core/hallucination_vendor_not_found.yaml
git commit -m "test: add three hallucination-trap eval cases

Nonexistent invoice/customer/vendor identifiers; forbidden_content
checks for real figures belonging to unrelated entities, proving the
model didn't invent or conflate data when the tool result is empty."
```

---

### Task 20: Seed cases — remaining parameter extraction, piping, and vendor-status coverage

**Files:**
- Create: `evals/core/unpaid_invoices_min_amount.yaml`
- Create: `evals/core/search_invoices_min_amount_only.yaml`
- Create: `evals/core/search_invoices_due_after.yaml`
- Create: `evals/core/overdue_invoices_for_anchor_piped.yaml`
- Create: `evals/core/vendor_invoices_overdue_status.yaml`

- [ ] **Step 1: Write the five case files**

Create `evals/core/unpaid_invoices_min_amount.yaml`:

```yaml
id: unpaid_invoices_min_amount
category: parameter_extraction
user_message: "Which unpaid invoices are over $10,000?"
expectations:
  expected_tools:
    - tool: get_unpaid_invoices
      parameters:
        minimum_amount: 10000
  required_facts:
    - "Granite Systems"
```

Create `evals/core/search_invoices_min_amount_only.yaml`:

```yaml
id: search_invoices_min_amount_only
category: parameter_extraction
user_message: "Show me invoices over $50,000"
expectations:
  expected_tools:
    - tool: search_invoices
      parameters:
        minimum_amount: 50000
  required_facts:
    - "Anchor Components"
```

Create `evals/core/search_invoices_due_after.yaml`:

```yaml
id: search_invoices_due_after
category: parameter_extraction
user_message: "What invoices are due after August 1, 2025?"
expectations:
  expected_tools:
    - tool: search_invoices
      parameters:
        due_after: "2025-08-01"
  required_facts:
    - "Granite Systems"
    - "Crestline Holdings"
```

Create `evals/core/overdue_invoices_for_anchor_piped.yaml`:

```yaml
id: overdue_invoices_for_anchor_piped
category: parameter_extraction
user_message: "Which of Anchor Components' invoices are overdue?"
expectations:
  expected_tools:
    - tool: get_customer
      parameters:
        customer_name: "Anchor Components"
    - tool: get_overdue_invoices
      parameters:
        customer_id: "<piped>"
  required_facts:
    - "6534.00"
```

Create `evals/core/vendor_invoices_overdue_status.yaml`:

```yaml
id: vendor_invoices_overdue_status
category: vendor_invoices
user_message: "Show overdue vendor invoices"
expectations:
  expected_tools:
    - tool: get_vendor_invoices
      parameters:
        status: "overdue"
  required_facts:
    - "Cascade Industries"
```

Note: `overdue_invoices_for_anchor_piped` exercises the same
`get_customer` -> `get_overdue_invoices` piping as Task 17's follow-up
cases, but in a **single turn** with no `conversation_setup` and
`tests_memory` left at its default `false` — it proves piping works when
triggered by a customer name in the request itself, independent of
conversation memory, so `aggregate_metrics`'s `memory_usage_accuracy`
(which filters to `tests_memory: true`) doesn't silently absorb this
case's signal.

- [ ] **Step 2: Confirm the full suite loads with all 30 cases**

Run: `cd backend && .venv/Scripts/python -c "from ai_platform.evaluation.loader import load_suite; cases = load_suite('core'); print(len(cases)); assert len(cases) == 30"`
Expected: prints `30`, no assertion error.

- [ ] **Step 3: Verify tool coverage — every one of the 9 tools appears at least twice**

Run:
```bash
cd backend && .venv/Scripts/python -c "
from collections import Counter
from ai_platform.evaluation.loader import load_suite
cases = load_suite('core')
counts = Counter(t.tool for c in cases for t in c.expectations.expected_tools)
for tool in ['get_unpaid_invoices', 'get_overdue_invoices', 'search_invoices', 'get_customer_balance', 'get_vendor_balance', 'get_vendor_invoices', 'get_cash_position', 'get_customer', 'get_current_date']:
    assert counts[tool] >= 2, f'{tool}: only {counts[tool]}'
print(dict(counts))
"
```
Expected: prints a dict with every one of the 9 tools present, each
count >= 2, no assertion error.

- [ ] **Step 4: Commit**

```bash
git add evals/core/unpaid_invoices_min_amount.yaml evals/core/search_invoices_min_amount_only.yaml evals/core/search_invoices_due_after.yaml evals/core/overdue_invoices_for_anchor_piped.yaml evals/core/vendor_invoices_overdue_status.yaml
git commit -m "test: add final 5 eval cases, completing the 30-case core suite

Rounds out parameter-extraction coverage (minimum_amount on two tools,
due_after), a single-turn (non-memory) piping case, and vendor-invoice
status filtering. Every one of the 9 registered tools now appears at
least twice across the suite."
```

---

### Task 21: Record cassettes for the full core suite

**Files:**
- Create: `evals/cassettes/*.json` (generated, one or two per case
  depending on `conversation_setup` length — 32 files total: 28
  single-turn cases x 1 + 2 follow-up cases x 2 turns)
- Modify (possibly): any `evals/core/*.yaml` file whose real recorded
  tool sequence or parameter values differ from what was guessed while
  authoring it (expected — this step is where guesses get corrected
  against real model behavior, not just replayed against them).

**Interfaces:**
- Consumes: `python -m ai_platform.evaluation.run` (Task 13), all 30
  case files (Tasks 15-20). Requires a real, working `LLM_API_KEY` in
  `backend/.env` (whichever provider `app.core.config.Settings` is
  already configured for — `groq` or `anthropic`).

- [ ] **Step 1: Reseed the simulator from a clean slate**

Run: `cd backend && .venv/Scripts/python -m domains.finance.simulator.seed --reset`
Expected: `Seeded Northwind Manufacturing Ltd. (seed=42).`

Run: `cd backend && .venv/Scripts/python -m domains.finance.simulator.consistency_check`
Expected: `Consistency check passed: 0 violations.`

- [ ] **Step 2: Record the whole suite against the real LLM**

Run: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --suite core --record`
Expected: every case executes against the real configured LLM, cassette
files are written under `evals/cassettes/`, and a scorecard prints.
**Some cases will genuinely fail on this first pass** — that's expected
and is exactly what this step is for; it is not a bug in the harness.

- [ ] **Step 3: Reconcile any failures**

For each case reported `[FAIL]` in the scorecard, read its
`failure_reason` and decide which side was wrong:

- If the real model's tool sequence/parameters were **reasonable but
  differently shaped** than the file guessed (e.g. `payment_prioritization`
  calling `get_cash_position` before `get_vendor_invoices` — see Task
  16's note), **fix the case file** to match the real, correct behavior,
  then re-record just that case: `cd backend &&
  .venv/Scripts/python -m ai_platform.evaluation.run --suite core
  --record --case <case_id>`.
- If the model's behavior is genuinely wrong (wrong tool, hallucinated
  content, failed to ask for clarification when it should have), that is
  a real finding about the current prompts — do **not** edit the case to
  paper over it; leave the case failing, and record the finding
  explicitly in Task 22's HANDOFF.md write-up instead. Fixing the actual
  prompt is out of scope for this milestone (Global Constraints: "This
  milestone does not bump `planning_prompt.VERSION` or
  `system_prompt.VERSION`").

Repeat Steps 2-3 (re-running only the cases you changed, via `--case`)
until every case that should reasonably pass does.

- [ ] **Step 4: Confirm the deterministic replay path is genuinely deterministic**

Run: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded`
Expected: the exact same pass/fail outcome as the reconciled `--record`
run in Step 3, with exit code `0` if every case that's expected to pass
does (any cases left deliberately failing per Step 3's second bullet
should fail identically here too — recorded mode must reproduce live
mode's outcome exactly, since it's replaying the same captured
responses).

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean (no Python files changed in this task, but this
confirms no regression from the DB state changes in Step 1).

- [ ] **Step 6: Commit**

```bash
git add evals/cassettes/ evals/core/
git commit -m "test: record cassettes for the full core suite against a real LLM

Deterministic replay (--mode recorded) reproduces the reconciled
--record run exactly - the CI job added in Task 14 can now go green."
```

---

### Task 22: Final verification, prompt-change-flagging proof, and `HANDOFF.md` rewrite

**Files:**
- Modify: `HANDOFF.md`

**Interfaces:** None — this is a verification and documentation task, no
code changes.

- [ ] **Step 1: Full clean-slate verification**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS, every test from Milestones 1-7 plus every new test in
this plan.

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: all clean (this milestone makes no frontend changes at all).

- [ ] **Step 2: The one-command acceptance run**

Reseed first (Task 21 Step 1's commands), then:

Run: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --suite core`
Expected: one command — no flags needed beyond `--suite core`, `--mode`
defaults to `recorded` — prints a full scorecard (per-category
breakdown, the four named aggregate metrics) and exits `0` if every
non-deliberately-failing case passes. Confirm directly against Postgres
that results were actually persisted, not just printed:

```bash
docker compose exec postgres psql -U postgres -d ai_employee_platform -c "
SELECT suite, mode, planning_prompt_version, system_prompt_version, total_cases, passed_cases, overall_score
FROM evaluation.evaluation_runs ORDER BY started_at DESC LIMIT 1;"
docker compose exec postgres psql -U postgres -d ai_employee_platform -c "
SELECT COUNT(*) FROM evaluation.evaluation_results;"
```
Expected: the most recent run row matches the just-printed scorecard's
totals; `evaluation_results` has one row per case in that run.

- [ ] **Step 3: Prove the prompt-change-flagging mechanism live**

This is the acceptance criterion "prompt changes without a passing eval
run are flagged in the report" — prove it actually fires, don't just
trust the design:

1. Temporarily bump `ai_platform/prompts/planning_prompt.py`'s
   `VERSION` (e.g. `"1.3.0"` -> `"1.3.0-test"`) — a throwaway edit, not a
   real prompt change.
2. Run: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded`
   Expected: **every** case now reports `STALE` (the hash changed, so no
   existing cassette matches), the scorecard's `STALE (30)` section lists
   every case id, and the command exits non-zero.
3. Revert the throwaway `VERSION` edit
   (`git checkout -- ai_platform/prompts/planning_prompt.py`).
4. Run the suite once more to confirm it's back to the reconciled,
   passing state from Task 21: `cd backend && .venv/Scripts/python -m ai_platform.evaluation.run --suite core --mode recorded`

Record the actual observed output of step 2 (the `STALE (30)` line) in
`HANDOFF.md` — this is the proof the mechanism works, not an assumption.

- [ ] **Step 4: Rewrite `HANDOFF.md`**

Update `HANDOFF.md` following the same structure as Milestone 6/7's
version: current milestone/status header, §1 verified current state
(commands + actual output from Steps 1-3), §2 work completed this
session, §3 in-progress work (should be "nothing"), §4 decisions made
(mirror this plan's key design points: LLM-response cassettes over
hand-scripted mocks as the determinism mechanism, cassette-hash staleness
as the sole prompt-change-flagging mechanism, reading actual tool calls
from `application.tool_executions` instead of adding a field to
`ChatEvent`, `ScriptedLLMService`/`RecordingLLMService` as production
LLMService implementations rather than reusing the test-only
`FakeLLMService`), §5 known issues (carry forward Milestone 6/7's still-
open items unchanged; add any case(s) left deliberately failing per Task
21 Step 3's second bullet, with the specific prompt behavior that's
wrong), §6 do-NOT-do list (don't hand-script cassette content instead of
recording it; don't add a `parameters` field to `ChatEvent`; don't bump
either prompt's `VERSION` as part of routine eval maintenance — that's
exactly what should make cassettes go stale), §7 next steps (Domain
Adapters and parallel tool execution remain queued from Milestone 6/7;
add: expanding `evals/` with a second suite beyond `core` once Milestone
9's new tools exist; consider surfacing `evaluation_runs` history in a
future read-only dashard once there's more than one recorded run to
compare).

- [ ] **Step 5: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 8 (Evaluation Framework) completion"
```

---

## Acceptance Criteria (from the milestone brief)

- One command (`python -m ai_platform.evaluation.run --suite core`) runs
  the suite, stores results in the `evaluation` schema, and prints a
  scorecard (Task 13, verified live in Task 22 Step 2).
- Prompt changes without a passing eval run are flagged in the report
  (cassette-hash staleness, Task 5; proved live in Task 22 Step 3).
- At least 30 seed cases (Tasks 15-20, exactly 30) covering all five
  unpaid-invoice phrasings, every tool at least twice, parameter
  extraction, ambiguity -> clarification, follow-up reference
  resolution, and hallucination traps.
- A CI job runs the deterministic (`recorded`) subset on every PR (Task
  14); the full (`live`) suite is runnable on demand (`--mode live`,
  Task 10).

