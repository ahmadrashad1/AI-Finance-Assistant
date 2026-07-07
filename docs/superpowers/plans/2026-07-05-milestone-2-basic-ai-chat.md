# Milestone 2 — Basic AI Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The assistant behaves like a general chat assistant — conversational,
streamed over SSE, with persisted per-session conversation history — with
no finance tools yet (those start Milestone 3).

**Architecture:** FastAPI stays a thin endpoint layer. A new reusable
`ai_platform` package (renamed from the Milestone-1 `platform/` scaffold,
which turned out to collide with Python's stdlib `platform` module) holds
the domain-agnostic AI runtime: `workflow` (lifecycle base class),
`memory` (Postgres-backed conversation storage + recency-window retrieval),
`llm` (provider-agnostic streaming interface + Anthropic adapter),
`prompts` (versioned system prompt), and `orchestration` (`PromptBuilder` +
`ChatWorkflow`). The Next.js frontend becomes a ChatGPT-style UI: sidebar,
streaming message list, markdown-lite rendering.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, `anthropic` Python
SDK (`claude-haiku-4-5`), Next.js App Router, TypeScript strict, SSE
(`fetch` + `ReadableStream`, no WebSocket).

## Global Constraints

- Python 3.12+, full type hints, `ruff` + `mypy --strict` clean (matches
  Milestone 1's bar — see `backend/pyproject.toml`).
- No finance tools, no tool registry population, no two-phase
  planning/response split this milestone (ADR-0002's split becomes
  meaningful in Milestone 3, when there's an actual tool registry to plan
  over — see `docs/superpowers/specs/2026-07-05-milestone-2-basic-ai-chat-design.md`).
- Every error surfaces through the existing `app.core.errors` categories
  (Validation/Business/Infrastructure/AI/Unexpected) — no new categories.
- Structured JSON logs only, using the existing `request_id_ctx_var` /
  `conversation_id_ctx_var` / `workflow_ctx_var` from `app.core.logging`.
- `ai_platform` code may import from `app.core.errors` and `app.db.base`
  (the backend). This is a deliberate, documented coupling: there is only
  one backend consumer of `ai_platform` today, and building a fully
  provider-agnostic DB/error abstraction now would be premature (YAGNI).
  Do not "fix" this without discussing it first — it's a conscious choice,
  not an oversight.
- CI currently has no Postgres service even though the backend test job
  references `DATABASE_URL=...localhost:5432/ci_test` — this plan adds one
  (Task 1), since Milestone 2 is the first milestone whose tests need a
  real database connection to be meaningful.

---

### Task 1: Rename `platform/` → `ai_platform/`, make it an installable package, wire up tooling

**Files:**
- Rename (git mv): `platform/` → `ai_platform/` (carries `README.md`,
  `workflow/README.md`, `memory/README.md`, `orchestration/README.md`,
  `tool_registry/README.md`, `evaluation/README.md` with it)
- Create: `ai_platform/__init__.py`
- Create: `pyproject.toml` (repo root — see note below)
- Create: `ai_platform/workflow/__init__.py`
- Create: `ai_platform/memory/__init__.py`
- Create: `ai_platform/orchestration/__init__.py`
- Create: `ai_platform/llm/__init__.py`
- Create: `ai_platform/prompts/__init__.py`
- Modify: `ai_platform/README.md`
- Modify: `backend/README.md`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Test: `backend/tests/test_ai_platform_package.py`

**Interfaces:**
- Produces: an importable `ai_platform` package (installed editable into
  `backend/.venv` alongside `app`), with `ai_platform.__version__: str`.

- [ ] **Step 1: Rename the directory**

```bash
git mv platform ai_platform
```

- [ ] **Step 2: Create the package `__init__.py` files**

`ai_platform/__init__.py`:
```python
__version__ = "0.1.0"
```

`ai_platform/workflow/__init__.py`, `ai_platform/memory/__init__.py`,
`ai_platform/orchestration/__init__.py`, `ai_platform/llm/__init__.py`,
`ai_platform/prompts/__init__.py` — all empty files (0 bytes each).

- [ ] **Step 3: Add packaging metadata**

The `pyproject.toml` must live at the **repo root**, as a sibling of the
`ai_platform/` directory — mirroring exactly how `backend/pyproject.toml`
sits beside `backend/app/` with `packages = ["app"]`. Hatchling resolves
`packages` relative to the directory containing `pyproject.toml`, so a
`pyproject.toml` placed *inside* `ai_platform/` itself would tell it to
look for a nonexistent nested `ai_platform/ai_platform/` — do not put it
there.

`pyproject.toml` (repo root, new file — the repo has no root-level
`pyproject.toml` today):
```toml
[project]
name = "ai-platform"
version = "0.1.0"
description = "Reusable, domain-agnostic AI employee infrastructure"
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy[asyncio]>=2.0",
  "anthropic>=0.40",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["ai_platform"]
```

- [ ] **Step 4: Update `ai_platform/README.md`'s intro to name the import path**

Replace the first paragraph of `ai_platform/README.md` (currently starting
"Reusable, domain-agnostic AI employee infrastructure...") with:

```markdown
# AI Platform

Reusable, domain-agnostic AI employee infrastructure. Nothing here knows
about finance, invoices, or any specific business domain — that belongs
under `domains/`. Importable as the `ai_platform` Python package; installed
editable into the backend's virtualenv (see `backend/README.md`).
```

Leave the rest of the file (the `orchestration/`, `workflow/`,
`tool_registry/`, `evaluation/`, `memory/` bullet list) unchanged.

- [ ] **Step 5: Wire the editable install into backend setup**

In `backend/README.md`, change the "Local setup" code block from:
```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env           # adjust DATABASE_URL etc. if needed
uvicorn app.main:app --reload
```
to:
```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -e ..
pip install -e ".[dev]"
cp .env.example .env           # adjust DATABASE_URL etc. if needed
uvicorn app.main:app --reload
```

- [ ] **Step 6: Update the Makefile's `lint` target to also check `ai_platform`**

Change:
```makefile
lint:
	cd backend && python -m ruff check . && python -m mypy app alembic
	cd frontend && npm run lint && npm run typecheck
```
to:
```makefile
lint:
	cd backend && python -m ruff check . ../ai_platform && python -m mypy app alembic ../ai_platform
	cd frontend && npm run lint && npm run typecheck
```

- [ ] **Step 7: Add a Postgres service to CI and install `ai_platform` before the backend job runs**

Replace the `backend` job in `.github/workflows/ci.yml` with:
```yaml
  backend:
    name: Backend (lint + test)
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

      - name: Lint (ruff)
        run: ruff check . ../ai_platform

      - name: Type check (mypy)
        run: mypy app alembic ../ai_platform

      - name: Apply migrations
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ci_test
        run: alembic upgrade head

      - name: Test (pytest)
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ci_test
        run: pytest
```
(Leave the `frontend` job below it unchanged.)

- [ ] **Step 8: Write the failing test**

`backend/tests/test_ai_platform_package.py`:
```python
import ai_platform


def test_ai_platform_package_is_importable() -> None:
    assert ai_platform.__version__ == "0.1.0"
```

- [ ] **Step 9: Install `ai_platform` editable and run the test to verify it currently fails**

```bash
cd backend
pip install -e ..
pip install -e ".[dev]"
python -m pytest tests/test_ai_platform_package.py -v
```
Expected: PASS immediately (the package content from Steps 1-3 already
exists) — this step is really "confirm the install worked", since there is
no red-then-green cycle for a pure packaging change. If it fails with
`ModuleNotFoundError: No module named 'ai_platform'`, the editable install
didn't take — re-run `pip install -e ..` from inside the
activated `backend/.venv`.

- [ ] **Step 10: Commit**

```bash
git add ai_platform pyproject.toml Makefile .github/workflows/ci.yml backend/README.md backend/tests/test_ai_platform_package.py
git commit -m "chore: rename platform/ to ai_platform/, make it installable"
```

---

### Task 2: Workflow lifecycle base class

**Files:**
- Create: `ai_platform/workflow/base.py`
- Test: `backend/tests/test_workflow.py`

**Interfaces:**
- Consumes: nothing (pure framework).
- Produces: `WorkflowContext(request_id: str | None, conversation_id: str | None = None)`
  (mutable dataclass), `Workflow[InputT, EventT]` ABC with abstract
  `initialize`, `validate`, `execute`, `log`; hook methods `evaluate`,
  `complete`; template method `run(input_data: InputT) -> AsyncIterator[EventT]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_workflow.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ai_platform.workflow.base import Workflow, WorkflowContext


class RecordingWorkflow(Workflow[str, str]):
    name = "recording"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def initialize(self, input_data: str) -> WorkflowContext:
        self.calls.append("initialize")
        return WorkflowContext(request_id="req-1")

    def validate(self, input_data: str, context: WorkflowContext) -> None:
        self.calls.append("validate")
        if input_data == "":
            raise ValueError("empty input")

    async def execute(self, input_data: str, context: WorkflowContext) -> AsyncIterator[str]:
        self.calls.append("execute")
        yield "a"
        yield "b"

    def log(self, context: WorkflowContext, events: list[str]) -> None:
        self.calls.append(f"log:{events}")

    def evaluate(self, context: WorkflowContext, events: list[str]) -> None:
        self.calls.append("evaluate")

    def complete(self, events: list[str]) -> list[str]:
        self.calls.append("complete")
        return events


@pytest.mark.asyncio
async def test_run_yields_events_in_order() -> None:
    workflow = RecordingWorkflow()
    events = [event async for event in workflow.run("hello")]
    assert events == ["a", "b"]


@pytest.mark.asyncio
async def test_run_calls_lifecycle_steps_in_order() -> None:
    workflow = RecordingWorkflow()
    async for _ in workflow.run("hello"):
        pass
    assert workflow.calls == [
        "initialize",
        "validate",
        "execute",
        "log:['a', 'b']",
        "evaluate",
        "complete",
    ]


@pytest.mark.asyncio
async def test_validate_failure_prevents_execute() -> None:
    workflow = RecordingWorkflow()
    with pytest.raises(ValueError, match="empty input"):
        async for _ in workflow.run(""):
            pass
    assert "execute" not in workflow.calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.workflow.base'`

- [ ] **Step 3: Write the implementation**

`ai_platform/workflow/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
EventT = TypeVar("EventT")


@dataclass
class WorkflowContext:
    """Carries request-scoped identifiers through a workflow run."""

    request_id: str | None
    conversation_id: str | None = None


class Workflow(ABC, Generic[InputT, EventT]):
    """Base class enforcing the mandatory lifecycle: Initialize -> Validate
    -> Execute -> Log -> Evaluate -> Complete. No step may be skipped.
    """

    name: str

    @abstractmethod
    def initialize(self, input_data: InputT) -> WorkflowContext:
        """Build the request context for this run."""

    @abstractmethod
    def validate(self, input_data: InputT, context: WorkflowContext) -> None:
        """Raise if input_data is invalid. No return value on success."""

    @abstractmethod
    def execute(self, input_data: InputT, context: WorkflowContext) -> AsyncIterator[EventT]:
        """Do the work, yielding zero or more events as they become available."""

    @abstractmethod
    def log(self, context: WorkflowContext, events: list[EventT]) -> None:
        """Emit a structured log line summarizing this run."""

    def evaluate(self, context: WorkflowContext, events: list[EventT]) -> None:
        """Optional evaluation hook. No-op by default."""
        return None

    def complete(self, events: list[EventT]) -> list[EventT]:
        """Final hook. Returns the collected events by default."""
        return events

    async def run(self, input_data: InputT) -> AsyncIterator[EventT]:
        context = self.initialize(input_data)
        self.validate(input_data, context)
        collected: list[EventT] = []
        async for event in self.execute(input_data, context):
            collected.append(event)
            yield event
        self.log(context, collected)
        self.evaluate(context, collected)
        self.complete(collected)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_workflow.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/workflow/base.py backend/tests/test_workflow.py
git commit -m "feat: add Workflow lifecycle base class"
```

---

### Task 3: SQLAlchemy models for the `application` schema

**Files:**
- Create: `ai_platform/memory/models.py`
- Modify: `backend/app/db/base.py`
- Test: `backend/tests/test_memory_models.py`

**Interfaces:**
- Consumes: `app.db.base.Base` (existing `DeclarativeBase`).
- Produces: `SessionModel(id: str, created_at, last_seen_at)`,
  `ConversationModel(id: uuid.UUID, session_id: str, title: str | None, created_at)`,
  `MessageModel(id: uuid.UUID, conversation_id: uuid.UUID, role: str, content: str, created_at)`,
  all under Postgres schema `"application"`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_memory_models.py`:
```python
from ai_platform.memory.models import ConversationModel, MessageModel, SessionModel


def test_models_use_application_schema() -> None:
    assert SessionModel.__table__.schema == "application"
    assert ConversationModel.__table__.schema == "application"
    assert MessageModel.__table__.schema == "application"


def test_conversation_references_session() -> None:
    fk_targets = {fk.target_fullname for fk in ConversationModel.__table__.foreign_keys}
    assert "application.sessions.id" in fk_targets


def test_message_references_conversation() -> None:
    fk_targets = {fk.target_fullname for fk in MessageModel.__table__.foreign_keys}
    assert "application.conversations.id" in fk_targets


def test_message_has_role_and_content_columns() -> None:
    columns = {c.name for c in MessageModel.__table__.columns}
    assert {"id", "conversation_id", "role", "content", "created_at"} <= columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_memory_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.memory.models'`

- [ ] **Step 3: Write the implementation**

`ai_platform/memory/models.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "application"


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationModel(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sessions.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Update `backend/app/db/base.py`'s docstring**

Change:
```python
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (none yet — infrastructure only)."""
```
to:
```python
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Models live in `ai_platform.memory.models` (conversation storage) and,
    from Milestone 4 onward, `domains.finance.*` — this class is the one
    place both depend on.
    """
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_memory_models.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add ai_platform/memory/models.py backend/app/db/base.py backend/tests/test_memory_models.py
git commit -m "feat: add Session/Conversation/Message models under the application schema"
```

---

### Task 4: Alembic migration for the `application` schema + DB test fixtures

**Files:**
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/<generated>_create_application_schema.py`
- Modify: `backend/tests/conftest.py`
- Modify: `docker-compose.yml` (none — see note below)

**Interfaces:**
- Produces: Postgres schema `application` with tables `sessions`,
  `conversations`, `messages`; pytest fixtures `db_session` (an
  `AsyncSession`) and `clean_db` (truncates the three tables) usable by
  later tasks' tests.

- [ ] **Step 1: Register the models on `Base.metadata` for Alembic**

In `backend/alembic/env.py`, change:
```python
# Models register themselves on Base.metadata by being imported somewhere on the
# import path before Alembic runs; there are none yet (infrastructure only).
target_metadata = Base.metadata
```
to:
```python
# Models register themselves on Base.metadata by being imported here before
# Alembic runs.
from ai_platform.memory import models as _memory_models  # noqa: F401

target_metadata = Base.metadata
```

- [ ] **Step 2: Fix the test-database name mismatch**

`backend/tests/conftest.py` currently defaults `DATABASE_URL` to a database
named `test`, but `docker-compose.yml` only creates `ai_employee_platform`.
Change:
```python
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test"
)
```
to:
```python
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_employee_platform",
)
```

- [ ] **Step 3: Generate the migration file**

```bash
cd backend
alembic revision -m "create application schema"
```
This prints the created file path, e.g.
`alembic/versions/a1b2c3d4e5f6_create_application_schema.py` — note the
generated revision id for the next step.

- [ ] **Step 4: Fill in the migration**

Open the generated file and replace its `upgrade()`/`downgrade()` bodies
(keep the auto-generated `revision`, `down_revision = None`,
`branch_labels = None`, `depends_on = None`, and the docstring/`Create Date`
Alembic already wrote):

```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS application")

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="application",
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=64),
            sa.ForeignKey("application.sessions.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="application",
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="application",
    )


def downgrade() -> None:
    op.drop_table("messages", schema="application")
    op.drop_table("conversations", schema="application")
    op.drop_table("sessions", schema="application")
    op.execute("DROP SCHEMA IF EXISTS application CASCADE")
```

- [ ] **Step 5: Apply the migration against the local dev database**

```bash
docker compose up -d
cd backend
alembic upgrade head
```
Expected: no errors; the command prints the applied revision id.

- [ ] **Step 6: Add DB fixtures for later tests**

Append to `backend/tests/conftest.py`:
```python
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine, get_sessionmaker


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@pytest.fixture
async def clean_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE application.messages, "
                "application.conversations, application.sessions CASCADE"
            )
        )
```

- [ ] **Step 7: Verify the fixtures work against the migrated database**

Create a throwaway check (do not commit this file — it's just to confirm
the migration + fixtures are wired correctly before later tasks depend on
them):
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
Expected output: `['conversations', 'messages', 'sessions']`

- [ ] **Step 8: Commit**

```bash
git add backend/alembic backend/tests/conftest.py
git commit -m "feat: add application schema migration and DB test fixtures"
```

---

### Task 5: `ConversationRepository`

**Files:**
- Create: `ai_platform/memory/repository.py`
- Test: `backend/tests/test_conversation_repository.py`

**Interfaces:**
- Consumes: `SessionModel`, `ConversationModel`, `MessageModel` (Task 3),
  `sqlalchemy.ext.asyncio.AsyncSession`, `clean_db`/`db_session` fixtures
  (Task 4).
- Produces:
  `ConversationRepository(db: AsyncSession)` with
  `get_or_create_session(session_id: str) -> SessionModel`,
  `create_conversation(session_id: str) -> ConversationModel`,
  `list_conversations(session_id: str) -> list[ConversationModel]`,
  `get_conversation(conversation_id: uuid.UUID) -> ConversationModel | None`,
  `add_message(conversation_id: uuid.UUID, role: str, content: str) -> MessageModel`,
  `get_messages(conversation_id: uuid.UUID) -> list[MessageModel]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_conversation_repository.py`:
```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_get_or_create_session_is_idempotent(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    first = await repo.get_or_create_session("session-1")
    second = await repo.get_or_create_session("session-1")
    await db_session.commit()
    assert first.id == second.id == "session-1"


@pytest.mark.asyncio
async def test_create_conversation_and_list_by_session(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-2")
    conversation = await repo.create_conversation("session-2")
    await db_session.commit()

    conversations = await repo.list_conversations("session-2")
    assert [c.id for c in conversations] == [conversation.id]


@pytest.mark.asyncio
async def test_add_message_sets_title_from_first_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-3")
    conversation = await repo.create_conversation("session-3")
    await repo.add_message(conversation.id, "user", "What invoices are overdue?")
    await db_session.commit()

    reloaded = await repo.get_conversation(conversation.id)
    assert reloaded is not None
    assert reloaded.title == "What invoices are overdue?"


@pytest.mark.asyncio
async def test_add_message_truncates_long_title(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-4")
    conversation = await repo.create_conversation("session-4")
    long_message = "x" * 80
    await repo.add_message(conversation.id, "user", long_message)
    await db_session.commit()

    reloaded = await repo.get_conversation(conversation.id)
    assert reloaded is not None
    assert reloaded.title == "x" * 50 + "…"


@pytest.mark.asyncio
async def test_get_messages_returns_oldest_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-5")
    conversation = await repo.create_conversation("session-5")
    await repo.add_message(conversation.id, "user", "first")
    await repo.add_message(conversation.id, "assistant", "second")
    await db_session.commit()

    messages = await repo.get_messages(conversation.id)
    assert [m.content for m in messages] == ["first", "second"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_conversation_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.memory.repository'`

- [ ] **Step 3: Write the implementation**

`ai_platform/memory/repository.py`:
```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.models import ConversationModel, MessageModel, SessionModel

TITLE_MAX_LENGTH = 50


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_session(self, session_id: str) -> SessionModel:
        existing = await self._db.get(SessionModel, session_id)
        if existing is not None:
            return existing
        session = SessionModel(id=session_id)
        self._db.add(session)
        await self._db.flush()
        return session

    async def create_conversation(self, session_id: str) -> ConversationModel:
        conversation = ConversationModel(id=uuid.uuid4(), session_id=session_id)
        self._db.add(conversation)
        await self._db.flush()
        return conversation

    async def list_conversations(self, session_id: str) -> list[ConversationModel]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.session_id == session_id)
            .order_by(ConversationModel.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation(self, conversation_id: uuid.UUID) -> ConversationModel | None:
        return await self._db.get(ConversationModel, conversation_id)

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> MessageModel:
        conversation = await self._db.get(ConversationModel, conversation_id)
        if conversation is not None and conversation.title is None and role == "user":
            if len(content) > TITLE_MAX_LENGTH:
                conversation.title = content[:TITLE_MAX_LENGTH] + "…"
            else:
                conversation.title = content
        message = MessageModel(
            id=uuid.uuid4(), conversation_id=conversation_id, role=role, content=content
        )
        self._db.add(message)
        await self._db.flush()
        return message

    async def get_messages(self, conversation_id: uuid.UUID) -> list[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_conversation_repository.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/memory/repository.py backend/tests/test_conversation_repository.py
git commit -m "feat: add ConversationRepository"
```

---

### Task 6: `ConversationMemory`

**Files:**
- Create: `ai_platform/memory/conversation_memory.py`
- Test: `backend/tests/test_conversation_memory.py`

**Interfaces:**
- Consumes: `ConversationRepository` (Task 5).
- Produces: `HistoryMessage(role: str, content: str)` (frozen dataclass),
  `ConversationMemory(repository: ConversationRepository)` with
  `get_context_window(conversation_id: uuid.UUID) -> list[HistoryMessage]`
  (last 10 messages, oldest first).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_conversation_memory.py`:
```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory, HistoryMessage
from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_empty_conversation_returns_empty_window(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-mem-1")
    conversation = await repo.create_conversation("session-mem-1")
    await db_session.commit()

    memory = ConversationMemory(repo)
    window = await memory.get_context_window(conversation.id)
    assert window == []


@pytest.mark.asyncio
async def test_window_is_bounded_to_last_ten_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-mem-2")
    conversation = await repo.create_conversation("session-mem-2")
    for i in range(12):
        role = "user" if i % 2 == 0 else "assistant"
        await repo.add_message(conversation.id, role, f"message-{i}")
    await db_session.commit()

    memory = ConversationMemory(repo)
    window = await memory.get_context_window(conversation.id)

    assert len(window) == 10
    assert window[0] == HistoryMessage(role="user", content="message-2")
    assert window[-1] == HistoryMessage(role="assistant", content="message-11")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_conversation_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.memory.conversation_memory'`

- [ ] **Step 3: Write the implementation**

`ai_platform/memory/conversation_memory.py`:
```python
from __future__ import annotations

import uuid
from dataclasses import dataclass

from ai_platform.memory.repository import ConversationRepository

MAX_HISTORY_MESSAGES = 10


@dataclass(frozen=True)
class HistoryMessage:
    """A (role, content) pair ready to hand to an LLM prompt.

    This is the seam a future milestone can use to swap recency-based
    retrieval for something smarter (embeddings, relevance ranking)
    without changing `PromptBuilder` or `ChatWorkflow`.
    """

    role: str
    content: str


class ConversationMemory:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def get_context_window(self, conversation_id: uuid.UUID) -> list[HistoryMessage]:
        messages = await self._repository.get_messages(conversation_id)
        recent = messages[-MAX_HISTORY_MESSAGES:]
        return [HistoryMessage(role=m.role, content=m.content) for m in recent]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_conversation_memory.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/memory/conversation_memory.py backend/tests/test_conversation_memory.py
git commit -m "feat: add ConversationMemory recency-window retrieval"
```

---

### Task 7: Versioned system prompt

**Files:**
- Create: `ai_platform/prompts/system_prompt.py`
- Test: `backend/tests/test_system_prompt.py`

**Interfaces:**
- Produces: `VERSION: str`, `AUTHOR: str`, `CHANGELOG: list[str]`,
  `SYSTEM_PROMPT: str`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_system_prompt.py`:
```python
from ai_platform.prompts.system_prompt import AUTHOR, CHANGELOG, SYSTEM_PROMPT, VERSION


def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.0.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 1


def test_system_prompt_never_invents_finance_data() -> None:
    assert "never invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_has_no_business_rules() -> None:
    # Ch.8: system prompts define behavior, not business rules (dollar
    # thresholds, approval policies, etc. belong in code, not the prompt).
    assert "$" not in SYSTEM_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_system_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.prompts.system_prompt'`

- [ ] **Step 3: Write the implementation**

`ai_platform/prompts/system_prompt.py`:
```python
"""Versioned system prompt for the general chat assistant.

Version: 1.0.0
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-05): Initial version. General-purpose finance-assistant
    persona, no business rules, no tool-use instructions (Milestone 2 has
    no tools yet).
"""

from __future__ import annotations

VERSION = "1.0.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
]

SYSTEM_PROMPT = (
    "You are an AI Finance Assistant. Be concise and friendly. "
    "You do not yet have access to any finance tools or company data. "
    "If asked for specific financial figures, invoices, or reports, "
    "explain that this capability is coming soon rather than guessing. "
    "Never invent finance data."
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_system_prompt.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/prompts/system_prompt.py backend/tests/test_system_prompt.py
git commit -m "feat: add versioned system prompt"
```

---

### Task 8: `LLMService` protocol, `AnthropicLLMService`, `FakeLLMService`, Settings update

**Files:**
- Create: `ai_platform/llm/service.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `pyproject.toml` (repo root — already lists `anthropic` from
  Task 1 — no change needed; noted here for traceability)
- Create: `backend/tests/fakes.py`
- Test: `backend/tests/test_anthropic_llm_service.py`

**Interfaces:**
- Consumes: `app.core.errors.AIError` (existing, from Milestone 1).
- Produces: `LLMService` (Protocol) with
  `stream_reply(system: str, history: list[dict[str, str]], message: str) -> AsyncIterator[str]`;
  `AnthropicLLMService(api_key: str, model: str)` implementing it via the
  `anthropic` SDK, translating `anthropic.APIConnectionError` /
  `anthropic.RateLimitError` / `anthropic.APIStatusError` into `AIError`;
  `FakeLLMService(tokens: list[str])` (test double) implementing the same
  protocol and recording the last call's arguments as
  `last_system` / `last_history` / `last_message`.

- [ ] **Step 1: Update Settings defaults**

In `backend/app/core/config.py`, change:
```python
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
```
to:
```python
    llm_provider: str = "anthropic"
    llm_api_key: str | None = None
    llm_model: str = "claude-haiku-4-5"
```

- [ ] **Step 2: Update `.env.example`**

In `backend/.env.example`, change:
```
# LLM provider configuration. Not used yet (Milestone 1 is infrastructure only)
# but wired up now so later milestones don't need a config redesign.
LLM_PROVIDER=openai
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
```
to:
```
# LLM provider configuration. Milestone 2 wires up chat against Anthropic;
# claude-haiku-4-5 is the cheapest current Claude model, used deliberately
# to keep pre-revenue development costs low.
LLM_PROVIDER=anthropic
LLM_API_KEY=
LLM_MODEL=claude-haiku-4-5
```

- [ ] **Step 3: Write the failing test for the Anthropic adapter's error mapping**

`backend/tests/test_anthropic_llm_service.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anthropic
import httpx
import pytest

from ai_platform.llm.service import AnthropicLLMService
from app.core.errors import AIError


class _FakeStream:
    def __init__(self, tokens: list[str], error: Exception | None = None) -> None:
        self._tokens = tokens
        self._error = error

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    @property
    async def text_stream(self) -> AsyncIterator[str]:  # type: ignore[override]
        if self._error is not None:
            raise self._error
        for token in self._tokens:
            yield token


def _fake_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.asyncio
async def test_stream_reply_yields_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    def fake_stream(**kwargs: Any) -> _FakeStream:
        return _FakeStream(tokens=["Hel", "lo"])

    monkeypatch.setattr(service._client.messages, "stream", fake_stream)

    tokens = [t async for t in service.stream_reply("system", [], "hi")]
    assert tokens == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_rate_limit_error_becomes_ai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AnthropicLLMService(api_key="test-key", model="claude-haiku-4-5")

    def fake_stream(**kwargs: Any) -> _FakeStream:
        return _FakeStream(
            tokens=[],
            error=anthropic.RateLimitError(
                message="rate limited", response=httpx.Response(429, request=_fake_request()), body=None
            ),
        )

    monkeypatch.setattr(service._client.messages, "stream", fake_stream)

    with pytest.raises(AIError):
        async for _ in service.stream_reply("system", [], "hi"):
            pass
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_anthropic_llm_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.llm.service'`

- [ ] **Step 5: Write the implementation**

`ai_platform/llm/service.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

import anthropic
from anthropic import AsyncAnthropic

from app.core.errors import AIError

CHAT_MAX_TOKENS = 1024


class LLMService(Protocol):
    def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]: ...


class AnthropicLLMService:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        messages = [*history, {"role": "user", "content": message}]
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=CHAT_MAX_TOKENS,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as exc:
            raise AIError("I couldn't reach the assistant right now. Please try again.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("The assistant is busy right now. Please try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise AIError("I couldn't process that right now. Please try again.") from exc
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_anthropic_llm_service.py -v`
Expected: 2 passed

- [ ] **Step 7: Add the `FakeLLMService` test double**

`backend/tests/fakes.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator


class FakeLLMService:
    """Test double for LLMService. Records the last call's arguments so
    tests can assert on prompt assembly (system prompt, conversation
    history) without hitting the real Anthropic API.
    """

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.last_system: str | None = None
        self.last_history: list[dict[str, str]] | None = None
        self.last_message: str | None = None

    async def stream_reply(
        self, system: str, history: list[dict[str, str]], message: str
    ) -> AsyncIterator[str]:
        self.last_system = system
        self.last_history = history
        self.last_message = message
        for token in self._tokens:
            yield token
```

- [ ] **Step 8: Commit**

```bash
git add ai_platform/llm/service.py backend/app/core/config.py backend/.env.example backend/tests/fakes.py backend/tests/test_anthropic_llm_service.py
git commit -m "feat: add LLMService protocol, Anthropic adapter, and fake test double"
```

---

### Task 9: `PromptBuilder`

**Files:**
- Create: `ai_platform/orchestration/prompt_builder.py`
- Test: `backend/tests/test_prompt_builder.py`

**Interfaces:**
- Consumes: `HistoryMessage` (Task 6).
- Produces: `BuiltPrompt(system: str, messages: list[dict[str, str]])`,
  `PromptBuilder.build(system_prompt: str, history: list[HistoryMessage]) -> BuiltPrompt`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_prompt_builder.py`:
```python
from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.prompt_builder import PromptBuilder


def test_build_includes_system_prompt_verbatim() -> None:
    builder = PromptBuilder()
    result = builder.build("You are helpful.", [])
    assert result.system == "You are helpful."
    assert result.messages == []


def test_build_converts_history_to_role_content_dicts() -> None:
    builder = PromptBuilder()
    history = [
        HistoryMessage(role="user", content="Hello"),
        HistoryMessage(role="assistant", content="Hi there"),
    ]
    result = builder.build("system prompt", history)
    assert result.messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_prompt_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.orchestration.prompt_builder'`

- [ ] **Step 3: Write the implementation**

`ai_platform/orchestration/prompt_builder.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from ai_platform.memory.conversation_memory import HistoryMessage


@dataclass
class BuiltPrompt:
    system: str
    messages: list[dict[str, str]]


class PromptBuilder:
    """Assembles the system prompt + conversation memory + new user message
    into the shape an LLMService expects. Pure logic, no I/O.
    """

    def build(self, system_prompt: str, history: list[HistoryMessage]) -> BuiltPrompt:
        return BuiltPrompt(
            system=system_prompt,
            messages=[{"role": h.role, "content": h.content} for h in history],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_prompt_builder.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/orchestration/prompt_builder.py backend/tests/test_prompt_builder.py
git commit -m "feat: add PromptBuilder"
```

---

### Task 10: `ChatWorkflow`

**Files:**
- Create: `ai_platform/orchestration/chat_workflow.py`
- Test: `backend/tests/test_chat_workflow.py`

**Interfaces:**
- Consumes: `Workflow[InputT, EventT]`, `WorkflowContext` (Task 2);
  `ConversationRepository` (Task 5); `ConversationMemory`, `HistoryMessage`
  (Task 6); `SYSTEM_PROMPT` (Task 7); `LLMService`, `FakeLLMService`
  (Task 8); `PromptBuilder` (Task 9); `app.core.errors.ValidationError`
  (existing).
- Produces: `ChatRequest(session_id: str, message: str, conversation_id: str | None = None)`,
  `ChatEvent(type: str, content: str | None = None, conversation_id: str | None = None, message: str | None = None)`,
  `ChatWorkflow(repository, memory, prompt_builder, llm_service, request_id)`
  implementing `Workflow[ChatRequest, ChatEvent]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chat_workflow.py`:
```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from app.core.errors import ValidationError
from tests.fakes import FakeLLMService


def _make_workflow(
    db_session: AsyncSession, llm_service: FakeLLMService
) -> tuple[ChatWorkflow, ConversationRepository]:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="req-test",
    )
    return workflow, repository


@pytest.mark.asyncio
async def test_new_conversation_streams_tokens_and_persists_both_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(tokens=["Hel", "lo!"])
    workflow, repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-1", message="Hi there")
    events = [event async for event in workflow.run(request)]
    await db_session.commit()

    token_events = [e for e in events if e.type == "token"]
    done_events = [e for e in events if e.type == "done"]
    assert [e.content for e in token_events] == ["Hel", "lo!"]
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
    workflow, repository = _make_workflow(db_session, llm_service)

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
    workflow, _repository = _make_workflow(db_session, llm_service)

    request = ChatRequest(session_id="session-wf-3", message="   ")
    with pytest.raises(ValidationError):
        async for _ in workflow.run(request):
            pass

    assert llm_service.last_message is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_platform.orchestration.chat_workflow'`

- [ ] **Step 3: Write the implementation**

`ai_platform/orchestration/chat_workflow.py`:
```python
from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.system_prompt import SYSTEM_PROMPT
from ai_platform.workflow.base import Workflow, WorkflowContext
from app.core.errors import ValidationError

logger = logging.getLogger("ai_platform.chat")


@dataclass
class ChatRequest:
    session_id: str
    message: str
    conversation_id: str | None = None


@dataclass
class ChatEvent:
    type: str  # "token" | "done" | "error"
    content: str | None = None
    conversation_id: str | None = None
    message: str | None = None


class ChatWorkflow(Workflow[ChatRequest, ChatEvent]):
    name = "chat"

    def __init__(
        self,
        repository: ConversationRepository,
        memory: ConversationMemory,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        request_id: str | None,
    ) -> None:
        self._repository = repository
        self._memory = memory
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service
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
        await self._repository.get_or_create_session(input_data.session_id)

        if input_data.conversation_id is None:
            conversation = await self._repository.create_conversation(input_data.session_id)
            conversation_id = conversation.id
        else:
            conversation_id = uuid.UUID(input_data.conversation_id)
        context.conversation_id = str(conversation_id)

        await self._repository.add_message(conversation_id, "user", input_data.message)
        history = await self._memory.get_context_window(conversation_id)
        prompt = self._prompt_builder.build(SYSTEM_PROMPT, history)

        assistant_reply: list[str] = []
        async for token in self._llm_service.stream_reply(
            prompt.system, prompt.messages, input_data.message
        ):
            assistant_reply.append(token)
            yield ChatEvent(type="token", content=token)

        await self._repository.add_message(
            conversation_id, "assistant", "".join(assistant_reply)
        )
        yield ChatEvent(type="done", conversation_id=str(conversation_id))

    def log(self, context: WorkflowContext, events: list[ChatEvent]) -> None:
        token_count = sum(1 for e in events if e.type == "token")
        logger.info(
            "chat turn complete",
            extra={"conversation_id": context.conversation_id, "token_count": token_count},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_workflow.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ai_platform/orchestration/chat_workflow.py backend/tests/test_chat_workflow.py
git commit -m "feat: add ChatWorkflow"
```

---

### Task 11: FastAPI chat endpoints

**Files:**
- Create: `backend/app/api/chat.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `ChatWorkflow`, `ChatRequest`, `ChatEvent` (Task 10);
  `ConversationRepository` (Task 5); `ConversationMemory` (Task 6);
  `PromptBuilder` (Task 9); `AnthropicLLMService`, `LLMService` (Task 8);
  `app.db.session.get_db_session` (existing); `app.core.logging.request_id_ctx_var`
  (existing); `app.core.errors.AppError` (existing).
- Produces: `POST /api/chat` (SSE), `GET /api/chat/conversations`,
  `GET /api/chat/conversations/{conversation_id}/messages`.

- [ ] **Step 1: Write the endpoint module**

`backend/app/api/chat.py`:
```python
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from ai_platform.llm.service import AnthropicLLMService, LLMService
from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx_var
from app.db.session import get_db_session

router = APIRouter()


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    conversation_id: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    created_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


def get_llm_service() -> LLMService:
    settings = get_settings()
    return AnthropicLLMService(api_key=settings.llm_api_key or "", model=settings.llm_model)


def _format_event(event: ChatEvent) -> str:
    payload: dict[str, str | None] = {"type": event.type}
    if event.content is not None:
        payload["content"] = event.content
    if event.conversation_id is not None:
        payload["conversation_id"] = event.conversation_id
    if event.message is not None:
        payload["message"] = event.message
    return f"data: {json.dumps(payload)}\n\n"


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
    chat_request = ChatRequest(
        session_id=body.session_id,
        message=body.message,
        conversation_id=body.conversation_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in workflow.run(chat_request):
                yield _format_event(event)
            await db.commit()
        except AppError as exc:
            await db.rollback()
            yield _format_event(ChatEvent(type="error", message=exc.user_message))
        except Exception:
            await db.rollback()
            yield _format_event(
                ChatEvent(
                    type="error",
                    message="I couldn't process that right now. Please try again.",
                )
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chat/conversations")
async def list_conversations(
    session_id: str, db: AsyncSession = Depends(get_db_session)
) -> list[ConversationSummary]:
    repository = ConversationRepository(db)
    conversations = await repository.list_conversations(session_id)
    return [
        ConversationSummary(
            id=str(c.id), title=c.title, created_at=c.created_at.isoformat()
        )
        for c in conversations
    ]


@router.get("/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)
) -> list[MessageOut]:
    repository = ConversationRepository(db)
    messages = await repository.get_messages(conversation_id)
    return [
        MessageOut(role=m.role, content=m.content, created_at=m.created_at.isoformat())
        for m in messages
    ]
```

- [ ] **Step 2: Wire the router into the app**

In `backend/app/main.py`, add the import and router registration:
```python
from app.api.chat import router as chat_router
from app.api.health import router as health_router
```
(replacing the existing single `from app.api.health import router as health_router`
line), and add, right after `application.include_router(health_router, prefix="/api")`:
```python
    application.include_router(chat_router, prefix="/api")
```

- [ ] **Step 3: Start the backend and smoke-test manually**

```bash
docker compose up -d
cd backend
uvicorn app.main:app --reload
```
In another terminal:
```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test", "message": "Hello"}'
```
Expected: without a real `ANTHROPIC_API_KEY` set in `.env`, you should see
an SSE `error` event (since `AnthropicLLMService` will raise an
authentication error from the real Anthropic API) — that confirms the
endpoint, workflow, and error-mapping path all wire together correctly.
With a real key set, expect streamed `token` events followed by a `done`
event carrying a `conversation_id`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/chat.py backend/app/main.py
git commit -m "feat: add POST /api/chat and conversation-history endpoints"
```

---

### Task 12: Integration tests + AI evaluation cases

**Files:**
- Test: `backend/tests/test_chat_api.py`
- Test: `backend/tests/test_chat_eval.py`

**Interfaces:**
- Consumes: FastAPI `app` (existing, `app.main`), `httpx.AsyncClient` +
  `ASGITransport` (existing pattern from `test_health.py`),
  `get_llm_service` dependency (Task 11, overridden), `FakeLLMService`
  (Task 8), `ChatWorkflow` (Task 10).

- [ ] **Step 1: Write the integration test**

`backend/tests/test_chat_api.py`:
```python
from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.chat import get_llm_service
from app.main import app
from tests.fakes import FakeLLMService


def _parse_sse(body: str) -> list[dict[str, str]]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            events.append(json.loads(block[len("data:") :].strip()))
    return events


@pytest.mark.asyncio
async def test_post_chat_creates_conversation_and_streams_tokens(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(
        tokens=["Hi", " there!"]
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"session_id": "api-session-1", "message": "Hello"},
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)
        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]
        assert [e["content"] for e in token_events] == ["Hi", " there!"]
        assert len(done_events) == 1

        conversation_id = done_events[0]["conversation_id"]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            history_response = await client.get(
                f"/api/chat/conversations/{conversation_id}/messages"
            )
        assert history_response.status_code == 200
        history = history_response.json()
        assert [(m["role"], m["content"]) for m in history] == [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
        ]
    finally:
        app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_list_conversations_scoped_to_session(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(tokens=["ok"])
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/chat",
                json={"session_id": "api-session-2", "message": "First conversation"},
            )
            response = await client.get(
                "/api/chat/conversations", params={"session_id": "api-session-2"}
            )
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 1
        assert conversations[0]["title"] == "First conversation"
    finally:
        app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_empty_message_returns_error_event_not_a_crash(clean_db: None) -> None:
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(tokens=["unused"])
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat", json={"session_id": "api-session-3", "message": "   "}
            )
        assert response.status_code == 200
        events = _parse_sse(response.text)
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["message"] == "Please enter a message."
    finally:
        app.dependency_overrides.pop(get_llm_service, None)
```

- [ ] **Step 2: Run test to verify it currently fails, then passes**

Run: `cd backend && python -m pytest tests/test_chat_api.py -v`
If Task 11 was completed correctly, this should already PASS (3 passed) —
if `ModuleNotFoundError` or `AttributeError` appears instead, re-check that
`get_llm_service` is exported from `app.api.chat` (it is, as a module-level
function) and that Task 11's Step 2 wiring was completed.
Expected: 3 passed

- [ ] **Step 3: Write the AI evaluation cases**

Per `docs/CLAUDE.md`'s "every feature ships with ... AI evaluation cases",
these three cases check AI-behavior properties (not HTTP plumbing, which
Step 1 already covers) directly against `ChatWorkflow`. The full
Evaluation-Driven Development framework (datasets, ground truth, regression
tracking) lands in Milestone 8; this is intentionally lightweight.

`backend/tests/test_chat_eval.py`:
```python
"""Minimal AI evaluation cases for Milestone 2's chat behavior.

These are not a substitute for the full Evaluation-Driven Development
framework (Milestone 8) - they exist to satisfy CLAUDE.md's "every feature
ships with ... AI evaluation cases" for this milestone's scope, using
FakeLLMService so they run deterministically in CI without a live model.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.prompt_builder import PromptBuilder
from tests.fakes import FakeLLMService


@pytest.mark.asyncio
async def test_eval_greeting_produces_non_empty_reply(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A friendly greeting must produce a non-empty assistant reply."""
    llm_service = FakeLLMService(tokens=["Hello", "! How can I help?"])
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-1",
    )

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
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-2",
    )

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
    repository = ConversationRepository(db_session)
    workflow = ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=PromptBuilder(),
        llm_service=llm_service,
        request_id="eval-3",
    )

    with pytest.raises(ValidationError):
        async for _ in workflow.run(ChatRequest(session_id="eval-session-3", message="")):
            pass

    assert llm_service.last_message is None
```

- [ ] **Step 4: Run all new tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_api.py tests/test_chat_eval.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass (24 from Milestone 1 + all new ones from this
plan).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_chat_api.py backend/tests/test_chat_eval.py
git commit -m "test: add chat API integration tests and AI evaluation cases"
```

---

### Task 13: Frontend API client additions

**Files:**
- Modify: `frontend/lib/api-client.ts`

**Interfaces:**
- Produces: `getSessionId(): string`, `ChatStreamEvent` (discriminated
  union: token/done/error), `streamChat(sessionId, message, conversationId): AsyncGenerator<ChatStreamEvent>`,
  `ConversationSummary`, `listConversations(sessionId): Promise<ConversationSummary[]>`,
  `ConversationMessage`, `getConversationMessages(conversationId): Promise<ConversationMessage[]>`.

- [ ] **Step 1: Append the chat API client functions**

Add to the end of `frontend/lib/api-client.ts` (the existing
`HealthResponse`/`getHealth`/`API_BASE_URL` content stays as-is above this):
```typescript
export interface ChatTokenEvent {
  type: "token";
  content: string;
}

export interface ChatDoneEvent {
  type: "done";
  conversation_id: string;
}

export interface ChatErrorEvent {
  type: "error";
  message: string;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent | ChatErrorEvent;

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
}

export interface ConversationMessage {
  role: string;
  content: string;
  created_at: string;
}

const SESSION_ID_STORAGE_KEY = "ai-finance-assistant-session-id";

export function getSessionId(): string {
  const existing = window.localStorage.getItem(SESSION_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const generated = crypto.randomUUID();
  window.localStorage.setItem(SESSION_ID_STORAGE_KEY, generated);
  return generated;
}

export async function* streamChat(
  sessionId: string,
  message: string,
  conversationId: string | null,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      conversation_id: conversationId,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (trimmed.startsWith("data:")) {
        yield JSON.parse(trimmed.slice("data:".length).trim()) as ChatStreamEvent;
      }
    }
  }
}

export async function listConversations(sessionId: string): Promise<ConversationSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/chat/conversations?session_id=${encodeURIComponent(sessionId)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to list conversations with status ${response.status}`);
  }
  return (await response.json()) as ConversationSummary[];
}

export async function getConversationMessages(
  conversationId: string,
): Promise<ConversationMessage[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/chat/conversations/${conversationId}/messages`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load messages with status ${response.status}`);
  }
  return (await response.json()) as ConversationMessage[];
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run typecheck`
Expected: no errors. (There is no frontend test runner configured yet —
per Milestone 1's HANDOFF, `tsc`/`eslint`/`build` are the verification bar
for frontend code; this is unchanged in Milestone 2.)

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api-client.ts
git commit -m "feat: add chat streaming and conversation-history API client functions"
```

---

### Task 14: Frontend chat UI

**Files:**
- Create: `frontend/components/chat/markdown.ts`
- Create: `frontend/components/chat/ConversationSidebar.tsx`
- Create: `frontend/components/chat/MessageBubble.tsx`
- Create: `frontend/components/chat/MessageList.tsx`
- Create: `frontend/components/chat/MessageInput.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `getSessionId`, `streamChat`, `listConversations`,
  `getConversationMessages`, `ConversationSummary`, `ConversationMessage`,
  `ChatStreamEvent` (Task 13).

- [ ] **Step 1: Add the minimal markdown renderer**

`frontend/components/chat/markdown.ts`:
```typescript
// Deliberately minimal: escapes HTML first, then applies a handful of
// markdown transforms. No new dependency, per the Milestone 2 design doc.
// Escaping before transforming is what makes this safe to render with
// dangerouslySetInnerHTML - raw "<script>" etc. in model output becomes
// inert text, not markup.
export function renderInlineMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}
```

- [ ] **Step 2: Add the message bubble component**

`frontend/components/chat/MessageBubble.tsx`:
```typescript
import { renderInlineMarkdown } from "./markdown";

export interface MessageBubbleProps {
  role: string;
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  return (
    <div data-role={role} style={{ margin: "0.5rem 0" }}>
      <strong>{role === "user" ? "You" : "Assistant"}:</strong>{" "}
      <span dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(content) }} />
    </div>
  );
}
```

- [ ] **Step 3: Add the message list component**

`frontend/components/chat/MessageList.tsx`:
```typescript
import { MessageBubble } from "./MessageBubble";

export interface DisplayMessage {
  role: string;
  content: string;
}

export interface MessageListProps {
  messages: DisplayMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div>
      {messages.map((message, index) => (
        <MessageBubble key={index} role={message.role} content={message.content} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Add the message input component**

`frontend/components/chat/MessageInput.tsx`:
```typescript
"use client";

import { useState } from "react";

export interface MessageInputProps {
  disabled: boolean;
  onSend: (message: string) => void;
}

export function MessageInput({ disabled, onSend }: MessageInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue("");
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask about your finances..."
        disabled={disabled}
        style={{ width: "80%" }}
      />
      <button type="submit" disabled={disabled}>
        Send
      </button>
    </form>
  );
}
```

- [ ] **Step 5: Add the conversation sidebar component**

`frontend/components/chat/ConversationSidebar.tsx`:
```typescript
import type { ConversationSummary } from "@/lib/api-client";

export interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onSelect: (conversationId: string) => void;
  onNewConversation: () => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNewConversation,
}: ConversationSidebarProps) {
  return (
    <aside style={{ width: "220px", borderRight: "1px solid #ccc", padding: "0.5rem" }}>
      <button onClick={onNewConversation} style={{ width: "100%", marginBottom: "0.5rem" }}>
        + New conversation
      </button>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              onClick={() => onSelect(conversation.id)}
              style={{
                width: "100%",
                textAlign: "left",
                fontWeight: conversation.id === activeConversationId ? "bold" : "normal",
              }}
            >
              {conversation.title ?? "New conversation"}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

- [ ] **Step 6: Rewrite the chat page to compose everything**

Replace the entire contents of `frontend/app/page.tsx`:
```typescript
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getConversationMessages,
  getSessionId,
  listConversations,
  streamChat,
  type ConversationSummary,
} from "@/lib/api-client";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { MessageInput } from "@/components/chat/MessageInput";
import { MessageList, type DisplayMessage } from "@/components/chat/MessageList";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    listConversations(sessionId)
      .then(setConversations)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load conversations.");
      });
  }, [sessionId]);

  const handleSelectConversation = useCallback((conversationId: string) => {
    setActiveConversationId(conversationId);
    setError(null);
    getConversationMessages(conversationId)
      .then((history) =>
        setMessages(history.map((m) => ({ role: m.role, content: m.content }))),
      )
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load messages.");
      });
  }, []);

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
  }, []);

  const handleSend = useCallback(
    async (message: string) => {
      if (!sessionId) {
        return;
      }
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setIsStreaming(true);

      let assistantContent = "";
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      try {
        for await (const event of streamChat(sessionId, message, activeConversationId)) {
          if (event.type === "token") {
            assistantContent += event.content;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent },
            ]);
          } else if (event.type === "done") {
            setActiveConversationId(event.conversation_id);
            const updated = await listConversations(sessionId);
            setConversations(updated);
          } else if (event.type === "error") {
            setError(event.message);
          }
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, activeConversationId],
  );

  return (
    <main style={{ display: "flex", height: "100vh" }}>
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <section style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1rem" }}>
        <h1>AI Finance Assistant</h1>
        <div style={{ flex: 1, overflowY: "auto" }}>
          <MessageList messages={messages} />
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <MessageInput disabled={isStreaming || !sessionId} onSend={handleSend} />
      </section>
    </main>
  );
}
```

- [ ] **Step 7: Lint, type-check, and build**

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```
Expected: all three succeed with no errors.

- [ ] **Step 8: Manual verification in the browser**

```bash
docker compose up -d
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev
```
Open `http://localhost:3000`. Type "Hello" and send it.
- With a real `ANTHROPIC_API_KEY` set in `backend/.env`: confirm a reply
  streams in token-by-token, refreshing the page keeps the conversation
  (same `conversation_id` reloaded via `getConversationMessages`), and
  clicking "+ New conversation" then sending a second message creates a
  second sidebar entry.
- Without a real key: confirm the friendly error banner appears instead of
  a raw stack trace or "Internal Server Error" text.

- [ ] **Step 9: Commit**

```bash
git add frontend/components frontend/app/page.tsx
git commit -m "feat: add ChatGPT-style chat UI with conversation sidebar"
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

- [ ] **Step 3: Re-verify Milestone 1's acceptance criteria still hold**

```bash
docker compose up -d
cd backend && uvicorn app.main:app --reload
```
In another terminal: `curl http://localhost:8000/api/health` still returns
`{"status":"healthy","app":"ok","database":"ok"}`.

- [ ] **Step 4: Update `HANDOFF.md`**

Rewrite `HANDOFF.md` following the same structure as the current one
(sections: Current State, Work Completed This Session, In-Progress Work,
Decisions Made, Known Issues / Failing Tests, Do NOT Do, Next Steps),
updating:
- Header line 2: `Last updated: <today's date> | Current milestone: 2 —
  Basic AI Chat | Status: complete`
- §1 Current State: add the chat verification steps (POST /api/chat
  streams a reply given a real `ANTHROPIC_API_KEY`; refreshing the page
  preserves history; `pytest` passes without a real key thanks to
  `FakeLLMService`).
- §2 Work Completed This Session: list the `ai_platform` rename, the new
  `application` schema + migration, `ConversationRepository`/
  `ConversationMemory`/`PromptBuilder`/`ChatWorkflow`/`AnthropicLLMService`,
  the chat endpoints, and the frontend chat UI.
- §4 Decisions Made: record the `platform` → `ai_platform` rename (stdlib
  collision) and the `ai_platform` → `app.db.base` / `app.core.errors`
  coupling as deliberate, documented choices.
- §6 Do NOT Do: carry forward Milestone 1's items, and add "Don't add tool
  calling or the two-phase planning/response split yet — Milestone 3."
- §7 Next Steps: `Milestone 3 — Tool Calling` per `docs/PRD.md` Chapter 16.

- [ ] **Step 5: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 2 completion"
```
