# Milestone 7 — Multi-Tool Reasoning & Contextual Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship PRD Ch.16's Milestone 7 — the planner can combine tools with
parameter piping between calls, conversation memory resolves follow-ups
that reference a prior result set, and the assistant reasons over multiple
tool outputs to answer questions no single tool covers ("Which invoices
should I pay first?").

**Architecture:** Two internal phases in this one plan. Phase A
(Tasks 1-16) builds a real Accounts Payable data foundation (vendor
invoices, vendor payments, a real cash ledger) mirroring the existing AR
model exactly, since Milestone 6's `get_vendor_balance` was an explicit,
documented approximation pending exactly this data. Phase B (Tasks 17-28)
builds the `ExecutionPlanner` (parameter piping, plan capping, graceful
invalid-plan fallback), structured per-turn conversation memory, and the
reasoning-query prompt work.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest +
pytest-asyncio, Postgres 16, Next.js/React (frontend — no changes needed;
Milestone 6's markdown-table renderer and flat-record rendering already
handle every new tool's result shape generically).

## Global Constraints

- The LLM never accesses PostgreSQL, generates SQL, or knows table/schema
  names (CLAUDE.md, "Data access").
- No keyword matching anywhere in the application — intent routing for
  every new tool, and the "$stepN.field" piping references, come from the
  planning prompt/LLM output, never from Python `if "..." in message`
  style code.
- Layering is one-directional and strict: `endpoints -> workflows ->
  services -> repositories -> PostgreSQL`. Tools never execute SQL, never
  generate prose, never hold state, never call other tools directly
  (composition is the `ExecutionPlanner`'s job).
- Every workflow lifecycle step (Initialize -> Validate -> Execute -> Log
  -> Evaluate -> Complete) already exists in `ChatWorkflow` — unchanged
  this milestone.
- Structured logging only; every tool execution persisted via
  `ToolExecutionRepository` (unchanged).
- Every feature ships with unit tests, integration tests, and an AI
  evaluation case. Every prompt version bump comes with an updated
  changelog header and updated tests.
- Names reflect business meaning (`VendorInvoiceRepository`,
  `ExecutionPlanner` — never `Manager`, `Helper`, `Utils`, `Processor`).
- Don't reimplement invoice-status derivation anywhere new —
  `compute_invoice_status` in `invoice_repository.py` stays the AR source
  of truth; `compute_vendor_invoice_status` (new, this milestone) is its
  AP mirror and is the *only* place vendor-invoice status is derived.
- Don't touch `PaymentRepository.record_payment`'s validation gap or its
  `date.today()` fallback (HANDOFF.md §5/Milestone 4 HANDOFF §5) — out of
  scope, no write tool exists yet and this milestone doesn't add one.
- `SIMULATION_TODAY = date(2026, 7, 8)` (`domains/finance/simulator/
  constants.py`) is the fixed anchor for all simulator generation — never
  `datetime.now()`/`date.today()` inside the seeder.
- Line length 100 (ruff), `mypy --strict` clean, `from __future__ import
  annotations` at the top of every new/edited Python file. A prior
  milestone's edit to `backend/app/core/tool_registry.py` accidentally
  dropped this exact line and needed a fix round — every task touching
  that file must double-check it survives the edit.
- `VendorService.get_vendor_balance`'s public signature
  (`get_vendor_balance(*, vendor_name: str) -> VendorBalance`) and its
  `ValueError(f"Vendor not found: {vendor_name}")` error path are
  unchanged this milestone — only its internal data source and
  `VendorBalance`'s field names change (Task 12).

---

## Phase A — Accounts Payable Data Foundation

### Task 1: Database schema — `vendor_invoices` and `vendor_payments`

**Files:**
- Create: `backend/alembic/versions/<new_revision>_create_vendor_invoices_and_vendor_payments.py`
- Create: `domains/finance/models/payables.py`
- Modify: `domains/finance/models/__init__.py`

**Interfaces:**
- Produces: `VendorInvoiceModel` (`__tablename__ = "vendor_invoices"`,
  schema `finance`), `VendorPaymentModel` (`__tablename__ =
  "vendor_payments"`, schema `finance`) — both re-exported from
  `domains.finance.models`.

- [ ] **Step 1: Write the migration**

Run `cd backend && .venv/Scripts/python -m alembic revision -m "create vendor_invoices and vendor_payments tables"`
to get a fresh revision id (call it `<REV1>` below — copy the exact id
alembic prints into the file this generates). Replace the generated
file's body with:

```python
"""create vendor_invoices and vendor_payments tables

Revision ID: <REV1>
Revises: 51417db8e8b6
Create Date: <alembic's own timestamp>

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '<REV1>'
down_revision: str | Sequence[str] | None = '51417db8e8b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "vendor_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_invoice_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.vendors.id"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled')",
            name="ck_vendor_invoices_status",
        ),
        sa.Index("ix_vendor_invoices_vendor_id", "vendor_id"),
        sa.Index("ix_vendor_invoices_due_date", "due_date"),
        sa.Index("ix_vendor_invoices_status", "status"),
        schema="finance",
    )

    op.create_table(
        "vendor_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendor_invoices.id"), nullable=False,
        ),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_method IN ('bank_transfer', 'check', 'credit_card', 'cash')",
            name="ck_vendor_payments_payment_method",
        ),
        sa.Index("ix_vendor_payments_vendor_invoice_id", "vendor_invoice_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("vendor_payments", schema="finance")
    op.drop_table("vendor_invoices", schema="finance")
```

- [ ] **Step 2: Write the ORM models**

Create `domains/finance/models/payables.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class VendorInvoiceModel(Base):
    __tablename__ = "vendor_invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled')",
            name="ck_vendor_invoices_status",
        ),
        Index("ix_vendor_invoices_vendor_id", "vendor_id"),
        Index("ix_vendor_invoices_due_date", "due_date"),
        Index("ix_vendor_invoices_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_invoice_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.purchase_orders.id"), nullable=True
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VendorPaymentModel(Base):
    __tablename__ = "vendor_payments"
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('bank_transfer', 'check', 'credit_card', 'cash')",
            name="ck_vendor_payments_payment_method",
        ),
        Index("ix_vendor_payments_vendor_invoice_id", "vendor_invoice_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendor_invoices.id"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: Re-export the new models**

Modify `domains/finance/models/__init__.py` — add the import and two
`__all__` entries:

```python
from domains.finance.models.billing import InvoiceItemModel, InvoiceModel, PaymentModel
from domains.finance.models.catalog import ProductModel
from domains.finance.models.expenses import ExpenseClaimModel
from domains.finance.models.organizations import CustomerModel, VendorModel
from domains.finance.models.payables import VendorInvoiceModel, VendorPaymentModel
from domains.finance.models.purchasing import PurchaseOrderItemModel, PurchaseOrderModel
from domains.finance.models.workforce import DepartmentModel, EmployeeModel

__all__ = [
    "CustomerModel",
    "VendorModel",
    "ProductModel",
    "DepartmentModel",
    "EmployeeModel",
    "PurchaseOrderModel",
    "PurchaseOrderItemModel",
    "InvoiceModel",
    "InvoiceItemModel",
    "PaymentModel",
    "ExpenseClaimModel",
    "VendorInvoiceModel",
    "VendorPaymentModel",
]
```

(only the `payables` import line and the two new `__all__` entries are
new; every existing line is unchanged)

- [ ] **Step 4: Apply the migration**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: no errors; `alembic current` now shows `<REV1> (head)`.

Run a manual round-trip to confirm `downgrade()` is correct too:
`cd backend && .venv/Scripts/python -m alembic downgrade -1` then
`.venv/Scripts/python -m alembic upgrade head` again. Expected: both
succeed with no errors, and `alembic current` ends back on `<REV1>`.

- [ ] **Step 5: Confirm the models import cleanly and mypy is clean**

Run: `cd backend && .venv/Scripts/python -c "from domains.finance.models import VendorInvoiceModel, VendorPaymentModel; print(VendorInvoiceModel.__tablename__, VendorPaymentModel.__tablename__)"`
Expected: prints `vendor_invoices vendor_payments`.

Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: `Success: no issues found in N source files`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/ domains/finance/models/payables.py domains/finance/models/__init__.py
git commit -m "feat: add vendor_invoices and vendor_payments tables

Mirrors the AR invoices/payments schema exactly (same status lifecycle,
balance/amount_paid tracking, PO linkage) - the first piece of the
Accounts Payable data foundation Milestone 7 needs for real due dates
and payment history, replacing Milestone 6's purchase-order
approximation."
```

---

### Task 2: Database schema — `bank_accounts` and `cash_transactions`

**Files:**
- Create: `backend/alembic/versions/<new_revision>_create_bank_accounts_and_cash_transactions.py`
- Create: `domains/finance/models/cash.py`
- Modify: `domains/finance/models/__init__.py`

**Interfaces:**
- Produces: `BankAccountModel` (`__tablename__ = "bank_accounts"`),
  `CashTransactionModel` (`__tablename__ = "cash_transactions"`) — both
  schema `finance`, re-exported from `domains.finance.models`.

- [ ] **Step 1: Write the migration**

Run `cd backend && .venv/Scripts/python -m alembic revision -m "create bank_accounts and cash_transactions tables"`
(call the printed id `<REV2>` — its `down_revision` must be `<REV1>` from
Task 1). Replace the generated file's body with:

```python
"""create bank_accounts and cash_transactions tables

Revision ID: <REV2>
Revises: <REV1>
Create Date: <alembic's own timestamp>

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '<REV2>'
down_revision: str | Sequence[str] | None = '<REV1>'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_name", sa.String(length=100), nullable=False),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "cash_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bank_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.bank_accounts.id"), nullable=False,
        ),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column(
            "payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.payments.id"),
            nullable=True,
        ),
        sa.Column(
            "vendor_payment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendor_payments.id"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "transaction_type IN ('customer_payment', 'vendor_payment')",
            name="ck_cash_transactions_type",
        ),
        sa.CheckConstraint(
            "(transaction_type = 'customer_payment' AND payment_id IS NOT NULL "
            "AND vendor_payment_id IS NULL) OR "
            "(transaction_type = 'vendor_payment' AND vendor_payment_id IS NOT NULL "
            "AND payment_id IS NULL)",
            name="ck_cash_transactions_reference_matches_type",
        ),
        sa.Index("ix_cash_transactions_bank_account_id", "bank_account_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("cash_transactions", schema="finance")
    op.drop_table("bank_accounts", schema="finance")
```

- [ ] **Step 2: Write the ORM models**

Create `domains/finance/models/cash.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class BankAccountModel(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CashTransactionModel(Base):
    __tablename__ = "cash_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('customer_payment', 'vendor_payment')",
            name="ck_cash_transactions_type",
        ),
        Index("ix_cash_transactions_bank_account_id", "bank_account_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.bank_accounts.id"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.payments.id"), nullable=True
    )
    vendor_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendor_payments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: Re-export the new models**

Modify `domains/finance/models/__init__.py`:

```python
from domains.finance.models.billing import InvoiceItemModel, InvoiceModel, PaymentModel
from domains.finance.models.cash import BankAccountModel, CashTransactionModel
from domains.finance.models.catalog import ProductModel
from domains.finance.models.expenses import ExpenseClaimModel
from domains.finance.models.organizations import CustomerModel, VendorModel
from domains.finance.models.payables import VendorInvoiceModel, VendorPaymentModel
from domains.finance.models.purchasing import PurchaseOrderItemModel, PurchaseOrderModel
from domains.finance.models.workforce import DepartmentModel, EmployeeModel

__all__ = [
    "CustomerModel",
    "VendorModel",
    "ProductModel",
    "DepartmentModel",
    "EmployeeModel",
    "PurchaseOrderModel",
    "PurchaseOrderItemModel",
    "InvoiceModel",
    "InvoiceItemModel",
    "PaymentModel",
    "ExpenseClaimModel",
    "VendorInvoiceModel",
    "VendorPaymentModel",
    "BankAccountModel",
    "CashTransactionModel",
]
```

(adds the `cash` import line and two more `__all__` entries on top of
Task 1's additions)

- [ ] **Step 4: Apply the migration**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: no errors; `alembic current` shows `<REV2> (head)`.

Round-trip check: `.venv/Scripts/python -m alembic downgrade -1` then
`.venv/Scripts/python -m alembic upgrade head` — both succeed, ends back
on `<REV2>`.

- [ ] **Step 5: Confirm import and mypy**

Run: `cd backend && .venv/Scripts/python -c "from domains.finance.models import BankAccountModel, CashTransactionModel; print(BankAccountModel.__tablename__, CashTransactionModel.__tablename__)"`
Expected: prints `bank_accounts cash_transactions`.

Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/ domains/finance/models/cash.py domains/finance/models/__init__.py
git commit -m "feat: add bank_accounts and cash_transactions tables

A real cash ledger: cash position as of any date is opening_balance
plus every transaction to that date, never itself stored, so it can't
drift from the payments that back it. A CHECK constraint enforces
exactly one of payment_id/vendor_payment_id is set, matching
transaction_type."
```

---

### Task 3: `compute_vendor_invoice_status` + `VendorInvoiceRepository`

**Files:**
- Create: `domains/finance/repositories/vendor_invoice_repository.py`
- Create: `backend/tests/test_vendor_invoice_repository.py`

**Interfaces:**
- Produces: `compute_vendor_invoice_status(*, total: Decimal,
  amount_paid: Decimal, due_date: date, as_of: date, current_status:
  str) -> str`, `VendorInvoiceRepository(db: AsyncSession)` with
  `create(...)`, `get_by_id`, `get_by_number`, `list_by_vendor`,
  `list_by_statuses(*, statuses: Sequence[str], vendor_id:
  uuid.UUID | None = None, minimum_balance: Decimal | None = None) ->
  list[VendorInvoiceModel]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vendor_invoice_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import (
    VendorInvoiceRepository,
    compute_vendor_invoice_status,
)
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


def test_compute_vendor_invoice_status_cancelled_and_draft_are_preserved() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="cancelled",
    ) == "cancelled"
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="draft",
    ) == "draft"


def test_compute_vendor_invoice_status_paid_beats_overdue() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("100"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "paid"


def test_compute_vendor_invoice_status_overdue_beats_partially_paid() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("40"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "overdue"


def test_compute_vendor_invoice_status_partially_paid_when_not_yet_due() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("40"), due_date=date(2026, 12, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "partially_paid"


def test_compute_vendor_invoice_status_sent_when_unpaid_and_not_due() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 12, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "sent"


@pytest.mark.asyncio
async def test_create_and_get_by_number(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    repo = VendorInvoiceRepository(db_session)
    invoice = await repo.create(
        vendor_invoice_number="VINV-0001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 1, 31), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    fetched = await repo.get_by_number("VINV-0001")
    assert fetched is not None
    assert fetched.id == invoice.id
    assert fetched.balance == Decimal("1000")
    assert fetched.amount_paid == Decimal("0")


@pytest.mark.asyncio
async def test_list_by_vendor_orders_by_issue_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-1101")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1102", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_vendor(vendor.id)
    assert [r.vendor_invoice_number for r in results] == ["VINV-1101", "VINV-1102"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_status_and_vendor(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-1201")
    vendor_b = await _make_vendor(db_session, "VEND-1202")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1201", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1202", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1203", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("overdue",), vendor_id=vendor_a.id)
    assert [r.vendor_invoice_number for r in results] == ["VINV-1201"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_minimum_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-1301")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1301", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1302", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), minimum_balance=Decimal("100"))
    assert [r.vendor_invoice_number for r in results] == ["VINV-1302"]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_invoice_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.repositories.vendor_invoice_repository'`.

- [ ] **Step 3: Implement**

Create `domains/finance/repositories/vendor_invoice_repository.py`:

```python
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import VendorInvoiceModel


def compute_vendor_invoice_status(
    *,
    total: Decimal,
    amount_paid: Decimal,
    due_date: date,
    as_of: date,
    current_status: str,
) -> str:
    """Derives a vendor invoice's status from its balance and due date.

    Identical priority rule to `compute_invoice_status` (the AR side):
    cancelled/draft preserved, then paid > overdue > partially_paid > sent.
    """
    if current_status in ("cancelled", "draft"):
        return current_status
    balance = total - amount_paid
    if balance <= 0:
        return "paid"
    if due_date < as_of:
        return "overdue"
    if amount_paid > 0:
        return "partially_paid"
    return "sent"


class VendorInvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        vendor_invoice_number: str,
        vendor_id: uuid.UUID,
        purchase_order_id: uuid.UUID | None,
        issue_date: date,
        due_date: date,
        status: str,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
    ) -> VendorInvoiceModel:
        invoice = VendorInvoiceModel(
            id=uuid.uuid4(),
            vendor_invoice_number=vendor_invoice_number,
            vendor_id=vendor_id,
            purchase_order_id=purchase_order_id,
            issue_date=issue_date,
            due_date=due_date,
            status=status,
            subtotal=subtotal,
            tax=tax,
            total=total,
            amount_paid=Decimal("0"),
            balance=total,
        )
        self._db.add(invoice)
        await self._db.flush()
        return invoice

    async def get_by_id(self, vendor_invoice_id: uuid.UUID) -> VendorInvoiceModel | None:
        return await self._db.get(VendorInvoiceModel, vendor_invoice_id)

    async def get_by_number(self, vendor_invoice_number: str) -> VendorInvoiceModel | None:
        stmt = select(VendorInvoiceModel).where(
            VendorInvoiceModel.vendor_invoice_number == vendor_invoice_number
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_id: uuid.UUID) -> list[VendorInvoiceModel]:
        stmt = (
            select(VendorInvoiceModel)
            .where(VendorInvoiceModel.vendor_id == vendor_id)
            .order_by(VendorInvoiceModel.issue_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_statuses(
        self,
        *,
        statuses: Sequence[str],
        vendor_id: uuid.UUID | None = None,
        minimum_balance: Decimal | None = None,
    ) -> list[VendorInvoiceModel]:
        conditions: list[ColumnElement[bool]] = [VendorInvoiceModel.status.in_(statuses)]
        if vendor_id is not None:
            conditions.append(VendorInvoiceModel.vendor_id == vendor_id)
        if minimum_balance is not None:
            conditions.append(VendorInvoiceModel.balance >= minimum_balance)
        stmt = (
            select(VendorInvoiceModel)
            .where(*conditions)
            .order_by(VendorInvoiceModel.due_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_invoice_repository.py -v`
Expected: PASS, all 10 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/repositories/vendor_invoice_repository.py backend/tests/test_vendor_invoice_repository.py
git commit -m "feat: add compute_vendor_invoice_status and VendorInvoiceRepository

Pure data access mirroring InvoiceRepository's list_by_statuses shape
exactly; compute_vendor_invoice_status uses the identical priority rule
as the AR side's compute_invoice_status (cancelled/draft preserved,
paid > overdue > partially_paid > sent)."
```

---

### Task 4: `VendorPaymentRepository`

**Files:**
- Create: `domains/finance/repositories/vendor_payment_repository.py`
- Create: `backend/tests/test_vendor_payment_repository.py`

**Interfaces:**
- Consumes: `compute_vendor_invoice_status` (Task 3).
- Produces: `VendorPaymentRepository(db: AsyncSession)` with
  `record_payment(*, vendor_invoice_id: uuid.UUID, payment_date: date,
  amount: Decimal, payment_method: str, reference_number: str | None =
  None, today: date | None = None) -> VendorPaymentModel`,
  `list_by_vendor_invoice(vendor_invoice_id: uuid.UUID) ->
  list[VendorPaymentModel]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vendor_payment_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_payment_repository import VendorPaymentRepository
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


async def _make_vendor_invoice(
    db_session: AsyncSession, vendor_id: object, number: str = "VINV-0001",
    total: Decimal = Decimal("1000"), due_date: date = date(2026, 6, 1),
) -> object:
    repo = VendorInvoiceRepository(db_session)
    return await repo.create(
        vendor_invoice_number=number, vendor_id=vendor_id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=due_date, status="sent",
        subtotal=total, tax=Decimal("0"), total=total,
    )


@pytest.mark.asyncio
async def test_full_payment_marks_invoice_paid(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    invoice = await _make_vendor_invoice(db_session, vendor.id)
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("1000"), payment_method="bank_transfer", today=date(2026, 5, 20),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.balance == Decimal("0")
    assert updated.status == "paid"


@pytest.mark.asyncio
async def test_partial_payment_before_due_date_is_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0002")
    invoice = await _make_vendor_invoice(db_session, vendor.id, "VINV-0002")
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("400"), payment_method="check", today=date(2026, 5, 20),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.balance == Decimal("600")
    assert updated.status == "partially_paid"


@pytest.mark.asyncio
async def test_partial_payment_after_due_date_is_overdue_not_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0003")
    invoice = await _make_vendor_invoice(
        db_session, vendor.id, "VINV-0003", due_date=date(2026, 1, 1)
    )
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 6, 1),
        amount=Decimal("400"), payment_method="check", today=date(2026, 6, 1),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.status == "overdue"


@pytest.mark.asyncio
async def test_list_by_vendor_invoice_returns_all_payments(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0004")
    invoice = await _make_vendor_invoice(db_session, vendor.id, "VINV-0004")
    repo = VendorPaymentRepository(db_session)
    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 10),
        amount=Decimal("300"), payment_method="check", today=date(2026, 5, 10),
    )
    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("700"), payment_method="bank_transfer", today=date(2026, 5, 20),
    )
    await db_session.commit()

    payments = await repo.list_by_vendor_invoice(invoice.id)
    assert len(payments) == 2
    assert sorted(p.amount for p in payments) == [Decimal("300"), Decimal("700")]


@pytest.mark.asyncio
async def test_record_payment_raises_for_nonexistent_vendor_invoice(
    clean_db: None, db_session: AsyncSession
) -> None:
    import uuid

    repo = VendorPaymentRepository(db_session)
    with pytest.raises(ValueError, match="does not exist"):
        await repo.record_payment(
            vendor_invoice_id=uuid.uuid4(), payment_date=date(2026, 5, 20),
            amount=Decimal("100"), payment_method="check",
        )
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_payment_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.repositories.vendor_payment_repository'`.

- [ ] **Step 3: Implement**

Create `domains/finance/repositories/vendor_payment_repository.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import VendorInvoiceModel, VendorPaymentModel
from domains.finance.repositories.vendor_invoice_repository import compute_vendor_invoice_status


class VendorPaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_payment(
        self,
        *,
        vendor_invoice_id: uuid.UUID,
        payment_date: date,
        amount: Decimal,
        payment_method: str,
        reference_number: str | None = None,
        today: date | None = None,
    ) -> VendorPaymentModel:
        invoice = await self._db.get(VendorInvoiceModel, vendor_invoice_id)
        if invoice is None:
            raise ValueError(f"Vendor invoice {vendor_invoice_id} does not exist")

        payment = VendorPaymentModel(
            id=uuid.uuid4(),
            vendor_invoice_id=vendor_invoice_id,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
        )
        self._db.add(payment)

        as_of = today if today is not None else date.today()
        invoice.amount_paid = invoice.amount_paid + amount
        invoice.balance = invoice.total - invoice.amount_paid
        invoice.status = compute_vendor_invoice_status(
            total=invoice.total,
            amount_paid=invoice.amount_paid,
            due_date=invoice.due_date,
            as_of=as_of,
            current_status=invoice.status,
        )

        await self._db.flush()
        return payment

    async def list_by_vendor_invoice(
        self, vendor_invoice_id: uuid.UUID
    ) -> list[VendorPaymentModel]:
        stmt = (
            select(VendorPaymentModel)
            .where(VendorPaymentModel.vendor_invoice_id == vendor_invoice_id)
            .order_by(VendorPaymentModel.payment_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_payment_repository.py -v`
Expected: PASS, all 5 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/repositories/vendor_payment_repository.py backend/tests/test_vendor_payment_repository.py
git commit -m "feat: add VendorPaymentRepository.record_payment

Mirrors PaymentRepository.record_payment exactly: the one place a
vendor invoice's amount_paid/balance/status are ever mutated."
```

---

### Task 5: `CashRepository`

**Files:**
- Create: `domains/finance/repositories/cash_repository.py`
- Create: `backend/tests/test_cash_repository.py`

**Interfaces:**
- Produces: `CashRepository(db: AsyncSession)` with `get_bank_account() ->
  BankAccountModel | None` (single row for the MVP), `get_balance_as_of(as_of:
  date) -> Decimal` (`opening_balance + sum(cash_transactions.amount WHERE
  transaction_date <= as_of)`, `Decimal("0")` contribution when there are no
  transactions — pure data access, no business meaning).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cash_repository.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel, CashTransactionModel, PaymentModel
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository


async def _make_bank_account(
    db_session: AsyncSession, opening_balance: Decimal = Decimal("100000.00")
) -> BankAccountModel:
    account = BankAccountModel(
        id=uuid.uuid4(),
        account_name="Operating Account",
        opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_customer_payment(db_session: AsyncSession) -> PaymentModel:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9901", company_name="Acme Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-9901", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=date(2026, 1, 15),
        amount=Decimal("500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    await db_session.flush()
    return payment


@pytest.mark.asyncio
async def test_get_bank_account_returns_the_single_seeded_account(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session)
    await db_session.commit()

    repo = CashRepository(db_session)
    fetched = await repo.get_bank_account()
    assert fetched is not None
    assert fetched.id == account.id


@pytest.mark.asyncio
async def test_get_bank_account_returns_none_when_no_account_exists(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CashRepository(db_session)
    assert await repo.get_bank_account() is None


@pytest.mark.asyncio
async def test_get_balance_as_of_with_no_transactions_returns_opening_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session, Decimal("50000.00"))
    await db_session.commit()

    repo = CashRepository(db_session)
    balance = await repo.get_balance_as_of(date(2026, 6, 1))
    assert balance == Decimal("50000.00")
    assert account.id is not None


@pytest.mark.asyncio
async def test_get_balance_as_of_sums_transactions_up_to_the_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = await _make_bank_account(db_session, Decimal("10000.00"))
    payment = await _make_customer_payment(db_session)
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=date(2026, 1, 15),
            amount=Decimal("500"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=date(2026, 7, 1),
            amount=Decimal("9000"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    await db_session.commit()

    repo = CashRepository(db_session)
    balance_mid_year = await repo.get_balance_as_of(date(2026, 2, 1))
    assert balance_mid_year == Decimal("10500.00")

    balance_after_both = await repo.get_balance_as_of(date(2026, 8, 1))
    assert balance_after_both == Decimal("19500.00")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cash_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.repositories.cash_repository'`.

- [ ] **Step 3: Implement**

Create `domains/finance/repositories/cash_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel, CashTransactionModel


class CashRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_bank_account(self) -> BankAccountModel | None:
        stmt = select(BankAccountModel).limit(1)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_balance_as_of(self, as_of: date) -> Decimal:
        account = await self.get_bank_account()
        if account is None:
            return Decimal("0")
        stmt = select(func.coalesce(func.sum(CashTransactionModel.amount), Decimal("0"))).where(
            CashTransactionModel.bank_account_id == account.id,
            CashTransactionModel.transaction_date <= as_of,
        )
        result = await self._db.execute(stmt)
        total_transactions = result.scalar_one()
        return account.opening_balance + total_transactions
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cash_repository.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/repositories/cash_repository.py backend/tests/test_cash_repository.py
git commit -m "feat: add CashRepository.get_bank_account and get_balance_as_of

Pure data access - cash position as of a date is opening_balance plus
every transaction up to that date, never itself stored, so it can't
drift from the ledger that backs it."
```

---

### Task 6: Simulator generation — vendor invoices and vendor payments

**Files:**
- Modify: `domains/finance/simulator/generator.py`
- Modify: `domains/finance/simulator/seed.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_seed_repeatability.py`

**Interfaces:**
- Consumes: `VendorInvoiceRepository`, `VendorPaymentRepository` (Tasks
  3-4), `PAYMENT_TERMS_DAYS` (already exists in `constants.py`).
- Produces: `SimulatorSeeder._seed_vendor_invoices(...)`,
  `SimulatorSeeder._seed_vendor_payments(...)`, wired into
  `SimulatorSeeder.seed()`.

This task also extends the `clean_db` fixture and both `FINANCE_TABLES`
truncate lists to include the four new tables — required before any test
using `clean_db` alongside these new models can be trusted not to leak
rows across test runs (Task 7 adds `bank_accounts`/`cash_transactions` to
the same three lists once those tables have data to truncate too).

- [ ] **Step 1: Extend `FINANCE_TABLES` and `clean_db` for the two new AP tables**

Modify `domains/finance/simulator/seed.py`:

```python
FINANCE_TABLES = (
    "finance.vendor_payments",
    "finance.vendor_invoices",
    "finance.payments",
    "finance.invoice_items",
    "finance.invoices",
    "finance.purchase_order_items",
    "finance.purchase_orders",
    "finance.expense_claims",
    "finance.employees",
    "finance.departments",
    "finance.products",
    "finance.customers",
    "finance.vendors",
)
```

(only the two new lines at the top are new; everything else unchanged)

Modify `backend/tests/conftest.py` — extend the `clean_db` fixture's
`TRUNCATE` statement:

```python
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE application.tool_executions, application.messages, "
                "application.conversations, application.sessions, "
                "finance.vendor_payments, finance.vendor_invoices, "
                "finance.payments, finance.invoice_items, finance.invoices, "
                "finance.purchase_order_items, finance.purchase_orders, "
                "finance.expense_claims, finance.employees, finance.departments, "
                "finance.products, finance.customers, finance.vendors CASCADE"
            )
        )
```

(only the `finance.vendor_payments, finance.vendor_invoices, ` clause is
new, inserted right after the `application.*` tables)

Modify `backend/tests/test_seed_repeatability.py`'s `FINANCE_TABLES`
tuple the same way:

```python
FINANCE_TABLES = (
    "finance.vendor_payments", "finance.vendor_invoices",
    "finance.payments", "finance.invoice_items", "finance.invoices",
    "finance.purchase_order_items", "finance.purchase_orders", "finance.expense_claims",
    "finance.employees", "finance.departments", "finance.products",
    "finance.customers", "finance.vendors",
)
```

- [ ] **Step 2: Run the full backend suite to confirm nothing broke**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS — this step is purely additive to truncate lists, no
behavior change yet.

- [ ] **Step 3: Write the failing generator test**

Add to `backend/tests/test_seed_repeatability.py` (extends the existing
`_snapshot` helper and adds vendor-invoice counts to the comparison so a
non-deterministic AP generation step would be caught the same way AR
already is):

```python
from domains.finance.models import VendorInvoiceModel, VendorPaymentModel
```

(add to the existing `from domains.finance.models import (...)` block,
alphabetically)

Modify `_snapshot`'s model tuple:

```python
    for model in (
        CustomerModel, VendorModel, ProductModel, EmployeeModel,
        PurchaseOrderModel, InvoiceModel, PaymentModel, ExpenseClaimModel,
        VendorInvoiceModel, VendorPaymentModel,
    ):
```

(only the last line, `VendorInvoiceModel, VendorPaymentModel,`, is new)

- [ ] **Step 4: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_repeatability.py -v`
Expected: FAIL — `AttributeError` or the snapshot counts for
`vendor_invoices`/`vendor_payments` are `0` in both runs today (not yet a
real failure, since both are 0 either way) — this step alone doesn't
prove much; the meaningful proof comes after Step 6 populates real data
and the test still passes with matching non-zero counts.

- [ ] **Step 5: Implement the two new generation steps**

Modify `domains/finance/simulator/generator.py` — extend the imports:

```python
from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceItemModel,
    InvoiceModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorModel,
)
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import (
    InvoiceRepository,
    compute_invoice_status,
)
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_invoice_repository import (
    VendorInvoiceRepository,
    compute_vendor_invoice_status,
)
from domains.finance.repositories.vendor_payment_repository import VendorPaymentRepository
from domains.finance.repositories.vendor_repository import VendorRepository
```

(adds the `vendor_invoice_repository`/`vendor_payment_repository` import
lines, alphabetically placed; every other import line unchanged)

Add two new constants near the top of `constants.py` (not
`generator.py`):

```python
NUM_VENDOR_INVOICES = 60
VENDOR_PAYMENT_COVERAGE = 0.70
```

(add these two lines to `domains/finance/simulator/constants.py`,
anywhere alongside the other `NUM_*`/`*_COVERAGE` constants — e.g. right
after `PAYMENT_COVERAGE = 0.70`)

Add the two new repository instances to `SimulatorSeeder.__init__`:

```python
    def __init__(self, db: AsyncSession, seed: int = DEFAULT_SEED) -> None:
        self._db = db
        self._rng = random.Random(seed)
        self._customers = CustomerRepository(db)
        self._vendors = VendorRepository(db)
        self._purchase_orders = PurchaseOrderRepository(db)
        self._invoices = InvoiceRepository(db)
        self._payments = PaymentRepository(db)
        self._vendor_invoices = VendorInvoiceRepository(db)
        self._vendor_payments = VendorPaymentRepository(db)
```

(only the last two lines are new)

Add the two new methods, and wire them into `seed()`, right after the
existing `_seed_payments` call:

```python
    async def seed(self) -> None:
        departments = await self._seed_departments()
        employees = await self._seed_employees(departments)
        customers, behavior_by_customer = await self._seed_customers()
        vendors = await self._seed_vendors()
        products = await self._seed_products()
        purchase_orders = await self._seed_purchase_orders(vendors, products, employees)
        invoices = await self._seed_invoices(customers, purchase_orders, products)
        await self._seed_duplicate_invoices(invoices)
        await self._seed_payments(invoices, behavior_by_customer)
        vendor_invoices = await self._seed_vendor_invoices(vendors, purchase_orders)
        await self._seed_vendor_payments(vendor_invoices)
        await self._seed_expense_claims(employees)
        await self._db.flush()
```

(only the `vendor_invoices = await self._seed_vendor_invoices(...)` and
`await self._seed_vendor_payments(...)` lines are new, inserted between
`_seed_payments` and `_seed_expense_claims`)

```python
    async def _seed_vendor_invoices(
        self,
        vendors: list[VendorModel],
        purchase_orders: list[PurchaseOrderModel],
    ) -> list[VendorInvoiceModel]:
        vendors_by_id = {vendor.id: vendor for vendor in vendors}
        eligible_pos = [po for po in purchase_orders if po.status in ("approved", "received")]
        sample_size = min(NUM_VENDOR_INVOICES, len(eligible_pos))
        chosen_pos = self._rng.sample(eligible_pos, k=sample_size)

        vendor_invoices = []
        for i, po in enumerate(chosen_pos, start=1):
            vendor = vendors_by_id[po.vendor_id]
            issue_date = po.order_date + timedelta(days=self._rng.randint(1, 5))
            due_date = issue_date + timedelta(days=PAYMENT_TERMS_DAYS[vendor.payment_terms])
            status = compute_vendor_invoice_status(
                total=po.total_amount,
                amount_paid=Decimal("0"),
                due_date=due_date,
                as_of=SIMULATION_TODAY,
                current_status="sent",
            )
            invoice = await self._vendor_invoices.create(
                vendor_invoice_number=f"VINV-{4000 + i}",
                vendor_id=vendor.id,
                purchase_order_id=po.id,
                issue_date=issue_date,
                due_date=due_date,
                status=status,
                subtotal=po.total_amount,
                tax=Decimal("0"),
                total=po.total_amount,
            )
            vendor_invoices.append(invoice)
        await self._db.flush()
        return vendor_invoices

    async def _seed_vendor_payments(self, vendor_invoices: list[VendorInvoiceModel]) -> None:
        payable = [invoice for invoice in vendor_invoices if invoice.status != "cancelled"]
        target_count = int(len(payable) * VENDOR_PAYMENT_COVERAGE)
        paid_candidates = self._rng.sample(payable, k=min(target_count, len(payable)))
        for invoice in paid_candidates:
            low, high = -5, 20
            payment_date = invoice.due_date + timedelta(days=self._rng.randint(low, high))
            if payment_date > SIMULATION_TODAY:
                payment_date = SIMULATION_TODAY
            full_payment = self._rng.random() < 0.8
            amount = (
                invoice.total
                if full_payment
                else (invoice.total * Decimal(self._rng.choice(["0.3", "0.5", "0.7"]))).quantize(
                    Decimal("0.01")
                )
            )
            await self._vendor_payments.record_payment(
                vendor_invoice_id=invoice.id,
                payment_date=payment_date,
                amount=amount,
                payment_method=self._rng.choice(PAYMENT_METHODS),
                reference_number=f"VPMT-{uuid.uuid4().hex[:10].upper()}",
                today=SIMULATION_TODAY,
            )
```

Add the two new constants to the `from domains.finance.simulator.constants
import (...)` block in `generator.py`:

```python
from domains.finance.simulator.constants import (
    BEHAVIOR_DAYS_OFFSET,
    BEHAVIOR_WEIGHTS,
    DEFAULT_SEED,
    EXPENSE_STATUSES,
    INVOICE_WINDOW_MONTHS,
    NUM_CUSTOMERS,
    NUM_DUPLICATE_INVOICES,
    NUM_EMPLOYEES,
    NUM_EXPENSE_CLAIMS_PER_EMPLOYEE,
    NUM_INVOICES,
    NUM_PURCHASE_ORDERS,
    NUM_VENDOR_INVOICES,
    NUM_VENDORS,
    PAYMENT_COVERAGE,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    PAYMENT_TERMS_DAYS,
    SIMULATION_TODAY,
    VENDOR_PAYMENT_COVERAGE,
)
```

(only `NUM_VENDOR_INVOICES` and `VENDOR_PAYMENT_COVERAGE` are new in this
list)

- [ ] **Step 6: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_repeatability.py -v`
Expected: PASS — the snapshot now includes non-zero, matching
`vendor_invoices`/`vendor_payments` counts across both seed runs.

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS.

- [ ] **Step 8: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 9: Commit**

```bash
git add domains/finance/simulator/generator.py domains/finance/simulator/seed.py \
  domains/finance/simulator/constants.py backend/tests/conftest.py \
  backend/tests/test_seed_repeatability.py
git commit -m "feat: generate vendor invoices and vendor payments in the simulator

Vendor invoice due_date is derived from order_date + the vendor's own
payment_terms (PAYMENT_TERMS_DAYS), not a new independent input.
FINANCE_TABLES and the clean_db fixture now truncate the two new AP
tables so tests using clean_db can't leak rows across runs."
```

---

### Task 7: Simulator generation — bank account and cash transactions

**Files:**
- Modify: `domains/finance/simulator/generator.py`
- Modify: `domains/finance/simulator/seed.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_seed_repeatability.py`

**Interfaces:**
- Consumes: every `PaymentModel` row (already seeded) and every
  `VendorPaymentModel` row (Task 6).
- Produces: `SimulatorSeeder._seed_cash_ledger(...)`, wired into
  `SimulatorSeeder.seed()` last (after both payment sets exist).

- [ ] **Step 1: Extend `FINANCE_TABLES` and `clean_db` for the two cash tables**

Modify `domains/finance/simulator/seed.py`:

```python
FINANCE_TABLES = (
    "finance.cash_transactions",
    "finance.bank_accounts",
    "finance.vendor_payments",
    "finance.vendor_invoices",
    "finance.payments",
    "finance.invoice_items",
    "finance.invoices",
    "finance.purchase_order_items",
    "finance.purchase_orders",
    "finance.expense_claims",
    "finance.employees",
    "finance.departments",
    "finance.products",
    "finance.customers",
    "finance.vendors",
)
```

Modify `backend/tests/conftest.py`'s `clean_db` `TRUNCATE` statement:

```python
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE application.tool_executions, application.messages, "
                "application.conversations, application.sessions, "
                "finance.cash_transactions, finance.bank_accounts, "
                "finance.vendor_payments, finance.vendor_invoices, "
                "finance.payments, finance.invoice_items, finance.invoices, "
                "finance.purchase_order_items, finance.purchase_orders, "
                "finance.expense_claims, finance.employees, finance.departments, "
                "finance.products, finance.customers, finance.vendors CASCADE"
            )
        )
```

Modify `backend/tests/test_seed_repeatability.py`'s `FINANCE_TABLES`:

```python
FINANCE_TABLES = (
    "finance.cash_transactions", "finance.bank_accounts",
    "finance.vendor_payments", "finance.vendor_invoices",
    "finance.payments", "finance.invoice_items", "finance.invoices",
    "finance.purchase_order_items", "finance.purchase_orders", "finance.expense_claims",
    "finance.employees", "finance.departments", "finance.products",
    "finance.customers", "finance.vendors",
)
```

- [ ] **Step 2: Write the failing generator test**

Add to `backend/tests/test_seed_repeatability.py`:

```python
from domains.finance.models import BankAccountModel, CashTransactionModel
```

(add to the existing `from domains.finance.models import (...)` block,
alphabetically)

Modify `_snapshot`'s model tuple once more:

```python
    for model in (
        CustomerModel, VendorModel, ProductModel, EmployeeModel,
        PurchaseOrderModel, InvoiceModel, PaymentModel, ExpenseClaimModel,
        VendorInvoiceModel, VendorPaymentModel, BankAccountModel, CashTransactionModel,
    ):
```

(only `BankAccountModel, CashTransactionModel,` is new)

- [ ] **Step 3: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_repeatability.py -v`
Expected: FAIL — both counts are `0` today (not yet a real assertion
failure, but proves the new models are wired into the snapshot before
Step 4 populates them).

- [ ] **Step 4: Implement the cash-ledger generation step**

Modify `domains/finance/simulator/generator.py` — extend the model
import:

```python
from domains.finance.models import (
    BankAccountModel,
    CashTransactionModel,
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
```

(adds `BankAccountModel`, `CashTransactionModel`, `PaymentModel`,
`VendorInvoiceModel`, `VendorPaymentModel` to the existing import list —
`PaymentModel` is needed here to type the new method's local query;
`VendorInvoiceModel` was already added in Task 6)

Add one constant to `constants.py`:

```python
OPENING_CASH_BALANCE = Decimal("750000.00")
```

(add near the other constants in `domains/finance/simulator/
constants.py`; add `from decimal import Decimal` to that file's imports
if not already present — it currently only imports `from datetime import
date`, so this import line is new)

Wire the new step into `seed()`, last:

```python
    async def seed(self) -> None:
        departments = await self._seed_departments()
        employees = await self._seed_employees(departments)
        customers, behavior_by_customer = await self._seed_customers()
        vendors = await self._seed_vendors()
        products = await self._seed_products()
        purchase_orders = await self._seed_purchase_orders(vendors, products, employees)
        invoices = await self._seed_invoices(customers, purchase_orders, products)
        await self._seed_duplicate_invoices(invoices)
        await self._seed_payments(invoices, behavior_by_customer)
        vendor_invoices = await self._seed_vendor_invoices(vendors, purchase_orders)
        await self._seed_vendor_payments(vendor_invoices)
        await self._seed_expense_claims(employees)
        await self._seed_cash_ledger()
        await self._db.flush()
```

(only the `await self._seed_cash_ledger()` line is new, added last)

Add the method:

```python
    async def _seed_cash_ledger(self) -> None:
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        account = BankAccountModel(
            id=uuid.uuid4(),
            account_name="Operating Account",
            opening_balance=OPENING_CASH_BALANCE,
            opening_date=window_start,
        )
        self._db.add(account)
        await self._db.flush()

        customer_payments = (await self._db.execute(select(PaymentModel))).scalars().all()
        for payment in customer_payments:
            self._db.add(
                CashTransactionModel(
                    id=uuid.uuid4(),
                    bank_account_id=account.id,
                    transaction_date=payment.payment_date,
                    amount=payment.amount,
                    transaction_type="customer_payment",
                    payment_id=payment.id,
                )
            )

        vendor_payments = (
            await self._db.execute(select(VendorPaymentModel))
        ).scalars().all()
        for vendor_payment in vendor_payments:
            self._db.add(
                CashTransactionModel(
                    id=uuid.uuid4(),
                    bank_account_id=account.id,
                    transaction_date=vendor_payment.payment_date,
                    amount=-vendor_payment.amount,
                    transaction_type="vendor_payment",
                    vendor_payment_id=vendor_payment.id,
                )
            )
        await self._db.flush()
```

Add `OPENING_CASH_BALANCE` to the `from domains.finance.simulator.
constants import (...)` block in `generator.py` (alongside
`NUM_VENDOR_INVOICES`).

- [ ] **Step 5: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_repeatability.py -v`
Expected: PASS — matching non-zero `bank_accounts`
(count 1) and `cash_transactions` counts across both seed runs.

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS.

- [ ] **Step 7: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 8: Manually verify the seeded cash position is sane**

Run: `cd backend && .venv/Scripts/python -m domains.finance.simulator.seed --reset`
Then: `.venv/Scripts/python -c "
import asyncio
from datetime import date
from app.db.session import get_sessionmaker
from domains.finance.repositories.cash_repository import CashRepository

async def main():
    async with get_sessionmaker()() as session:
        repo = CashRepository(session)
        balance = await repo.get_balance_as_of(date(2026, 7, 8))
        print(f'Cash position as of 2026-07-08: {balance}')

asyncio.run(main())
"`
Expected: a positive dollar figure, comfortably larger than the sum of
any handful of overdue vendor invoices (confirms the opening balance is
sized so the simulated company reads as a going concern, not a cash
crisis, per the design spec).

- [ ] **Step 9: Commit**

```bash
git add domains/finance/simulator/generator.py domains/finance/simulator/seed.py \
  domains/finance/simulator/constants.py backend/tests/conftest.py \
  backend/tests/test_seed_repeatability.py
git commit -m "feat: generate a real cash ledger from AR and AP payment history

One seeded bank account plus a cash_transactions row for every existing
customer payment (inflow) and every new vendor payment (outflow) -
cash position is always opening_balance + transactions to date, never
an independent input, so it can never drift from the payment history
that backs it."
```

---

### Task 8: Consistency check extension for AP and cash data

**Files:**
- Modify: `domains/finance/simulator/consistency_check.py`
- Create: `backend/tests/test_consistency_check_ap_cash.py`

**Interfaces:**
- Consumes: `VendorInvoiceModel`, `VendorPaymentModel`,
  `BankAccountModel`, `CashTransactionModel` (Tasks 1-2).
- Produces: `run_consistency_check` gains AP/cash violation checks,
  unchanged signature (`run_consistency_check(db: AsyncSession) ->
  list[str]`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_consistency_check_ap_cash.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel, CashTransactionModel, PaymentModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_payment_repository import VendorPaymentRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulator.consistency_check import run_consistency_check
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_freshly_seeded_data_has_zero_ap_cash_violations(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert violations == []


@pytest.mark.asyncio
async def test_detects_vendor_invoice_balance_mismatch(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_repo = VendorRepository(db_session)
    vendor = await vendor_repo.create(
        vendor_code="VEND-8001", company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    invoice_repo = VendorInvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        vendor_invoice_number="VINV-8001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    invoice.balance = Decimal("999999")
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("VINV-8001" in v and "balance" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_orphan_cash_transaction(clean_db: None, db_session: AsyncSession) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-8001", company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-8001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=date(2026, 1, 15),
        amount=Decimal("500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("1000"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()
    # Deliberately no cash_transactions row for this payment.
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("Payment" in v and "cash transaction" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_vendor_payment_repository_record_payment_paid_in_full(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_repo = VendorRepository(db_session)
    vendor = await vendor_repo.create(
        vendor_code="VEND-8101", company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    invoice_repo = VendorInvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        vendor_invoice_number="VINV-8101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    payment_repo = VendorPaymentRepository(db_session)
    await payment_repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 1, 20),
        amount=Decimal("750"), payment_method="bank_transfer", today=date(2026, 1, 20),
    )
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert violations == []
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_consistency_check_ap_cash.py -v`
Expected: FAIL — `test_freshly_seeded_data_has_zero_ap_cash_violations`
and the last test pass vacuously today (no AP/cash checks exist yet to
find the seeded data valid), but
`test_detects_vendor_invoice_balance_mismatch` and
`test_detects_orphan_cash_transaction` FAIL because
`run_consistency_check` doesn't check these yet (returns `[]`
unconditionally for these cases).

- [ ] **Step 3: Implement the AP/cash checks**

Modify `domains/finance/simulator/consistency_check.py` — extend the
model import:

```python
from domains.finance.models import (
    BankAccountModel,
    CashTransactionModel,
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
```

Add, inside `run_consistency_check` right before the final `return
violations` (after the existing invoice-balance/overdue loop):

```python
    all_vendor_invoices = (await db.execute(select(VendorInvoiceModel))).scalars().all()
    vendor_invoices_by_id = {vi.id: vi for vi in all_vendor_invoices}

    for vendor_invoice in all_vendor_invoices:
        if vendor_invoice.vendor_id not in vendor_ids:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} references missing "
                f"vendor {vendor_invoice.vendor_id}"
            )
        if (
            vendor_invoice.purchase_order_id is not None
            and vendor_invoice.purchase_order_id not in purchase_orders
        ):
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} references missing "
                f"purchase order {vendor_invoice.purchase_order_id}"
            )

    vendor_payments = (await db.execute(select(VendorPaymentModel))).scalars().all()
    vendor_payments_by_invoice: dict[uuid.UUID, Decimal] = {}
    for vendor_payment in vendor_payments:
        if vendor_payment.vendor_invoice_id not in vendor_invoices_by_id:
            violations.append(
                f"Vendor payment {vendor_payment.id} references missing vendor invoice "
                f"{vendor_payment.vendor_invoice_id}"
            )
            continue
        vendor_payments_by_invoice[vendor_payment.vendor_invoice_id] = (
            vendor_payments_by_invoice.get(vendor_payment.vendor_invoice_id, Decimal("0"))
            + vendor_payment.amount
        )

    for vendor_invoice in all_vendor_invoices:
        paid_total = vendor_payments_by_invoice.get(vendor_invoice.id, Decimal("0"))
        expected_balance = vendor_invoice.total - paid_total
        if vendor_invoice.balance != expected_balance:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} balance "
                f"{vendor_invoice.balance} != total {vendor_invoice.total} - payments "
                f"{paid_total} = {expected_balance}"
            )

        if vendor_invoice.status == "cancelled":
            continue
        is_past_due_unpaid = (
            vendor_invoice.due_date < SIMULATION_TODAY and vendor_invoice.balance > 0
        )
        if (
            vendor_invoice.status != "draft"
            and is_past_due_unpaid
            and vendor_invoice.status != "overdue"
        ):
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} is past due with "
                f"balance {vendor_invoice.balance} but status is "
                f"{vendor_invoice.status!r}, expected 'overdue'"
            )
        if vendor_invoice.status == "overdue" and not is_past_due_unpaid:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} has status 'overdue' "
                "but its due date/balance don't justify it"
            )

    bank_account_ids = set(
        (await db.execute(select(BankAccountModel.id))).scalars().all()
    )
    payment_ids = {payment.id for payment in payments}
    vendor_payment_ids = {vp.id for vp in vendor_payments}
    cash_transactions = (await db.execute(select(CashTransactionModel))).scalars().all()
    transactions_by_payment_id = {
        ct.payment_id for ct in cash_transactions if ct.payment_id is not None
    }
    transactions_by_vendor_payment_id = {
        ct.vendor_payment_id for ct in cash_transactions if ct.vendor_payment_id is not None
    }

    for transaction in cash_transactions:
        if transaction.bank_account_id not in bank_account_ids:
            violations.append(
                f"Cash transaction {transaction.id} references missing bank account "
                f"{transaction.bank_account_id}"
            )
        if transaction.payment_id is not None and transaction.payment_id not in payment_ids:
            violations.append(
                f"Cash transaction {transaction.id} references missing payment "
                f"{transaction.payment_id}"
            )
        if (
            transaction.vendor_payment_id is not None
            and transaction.vendor_payment_id not in vendor_payment_ids
        ):
            violations.append(
                f"Cash transaction {transaction.id} references missing vendor payment "
                f"{transaction.vendor_payment_id}"
            )

    for payment in payments:
        if payment.id not in transactions_by_payment_id:
            violations.append(f"Payment {payment.id} has no corresponding cash transaction")

    for vendor_payment in vendor_payments:
        if vendor_payment.id not in transactions_by_vendor_payment_id:
            violations.append(
                f"Vendor payment {vendor_payment.id} has no corresponding cash transaction"
            )

    return violations
```

This block replaces the function's existing `return violations` line
(which itself now sits at the end of this new block) — `vendor_ids` is
already computed earlier in the function alongside `customer_ids`, so
this block reuses it directly rather than recomputing it.

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_consistency_check_ap_cash.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 5: Re-run the existing consistency check test file too**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_consistency_check.py -v`
Expected: PASS — confirms the AR checks are untouched by this change.

- [ ] **Step 6: Manually re-verify the CLI acceptance criterion**

Run: `cd backend && .venv/Scripts/python -m domains.finance.simulator.seed --reset`
Run: `cd backend && .venv/Scripts/python -m domains.finance.simulator.consistency_check`
Expected: `Consistency check passed: 0 violations.`

- [ ] **Step 7: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 8: Commit**

```bash
git add domains/finance/simulator/consistency_check.py backend/tests/test_consistency_check_ap_cash.py
git commit -m "feat: extend consistency_check.py for AP and cash data

Same rule shapes as the AR side: no orphan FKs, vendor_invoice.balance
== total - payments, overdue status matches due_date/balance, and every
payment/vendor_payment has exactly one corresponding cash_transaction
in both directions."
```

---

### Task 9: `VendorService.get_vendor_balance` — upgrade to the real ledger

**Files:**
- Modify: `domains/finance/services/vendor_service.py`
- Modify: `backend/tests/test_vendor_service.py`
- Modify: `domains/finance/tools/get_vendor_balance.py`
- Modify: `backend/tests/test_get_vendor_balance_tool.py`
- Modify: `backend/tests/test_get_vendor_balance_integration.py`

**Interfaces:**
- Consumes: `VendorInvoiceRepository.list_by_statuses` (Task 3).
- Produces: `VendorBalance` (renamed fields:
  `open_invoice_count`, `oldest_due_date` replacing
  `open_purchase_order_count`, `oldest_order_date`),
  `VendorService.get_vendor_balance(*, vendor_name: str) -> VendorBalance`
  now sums outstanding `vendor_invoices.balance` instead of
  `purchase_orders.total_amount`. `GetVendorBalanceResult`'s fields are
  renamed to match. `VendorService.__init__`'s first constructor argument
  changes from `purchase_order_repository: PurchaseOrderRepository` to
  `vendor_invoice_repository: VendorInvoiceRepository` (its second
  argument, `vendor_repository: VendorRepository`, is unchanged) — this
  is a deliberate, one-time breaking change to an internal constructor,
  confined to this task; the tool's public contract
  (`GetVendorBalanceParams`/the LLM-facing description) keeps its
  `vendor_name` parameter unchanged, only the *result* field names change.

- [ ] **Step 1: Write the failing service tests**

Replace the entire contents of `backend/tests/test_vendor_service.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorBalance, VendorService


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


def _service(db_session: AsyncSession) -> VendorService:
    return VendorService(VendorInvoiceRepository(db_session), VendorRepository(db_session))


@pytest.mark.asyncio
async def test_get_vendor_balance_sums_outstanding_vendor_invoices(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-2001", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-3001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("1000.00"), tax=Decimal("0"), total=Decimal("1000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3002", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("2000.00"), tax=Decimal("0"), total=Decimal("2000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3003", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="paid",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")

    assert isinstance(balance, VendorBalance)
    assert balance.vendor_code == "VEND-2001"
    assert balance.total_outstanding == Decimal("3000.00")
    assert balance.open_invoice_count == 2
    assert balance.oldest_due_date == date(2026, 2, 1)


@pytest.mark.asyncio
async def test_get_vendor_balance_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2101", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="summit traders")
    assert balance.vendor_code == "VEND-2101"


@pytest.mark.asyncio
async def test_get_vendor_balance_with_no_outstanding_invoices_returns_zero(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2201", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")
    assert balance.total_outstanding == Decimal("0")
    assert balance.open_invoice_count == 0
    assert balance.oldest_due_date is None


@pytest.mark.asyncio
async def test_get_vendor_balance_unknown_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).get_vendor_balance(vendor_name="Does Not Exist Traders")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: FAIL — `VendorService.__init__` still takes
`PurchaseOrderRepository`, and `VendorBalance` doesn't have
`open_invoice_count`/`oldest_due_date` yet.

- [ ] **Step 3: Implement**

Replace the entire contents of `domains/finance/services/vendor_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository

OUTSTANDING_VENDOR_INVOICE_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class VendorBalance:
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_invoice_count: int
    oldest_due_date: date | None


class VendorService:
    """Business logic for accounts-payable vendor obligations.

    get_vendor_balance sums a vendor's outstanding vendor_invoices.balance
    (status sent/partially_paid/overdue - the AP mirror of AR's
    UNPAID_STATUSES). Milestone 6 originally approximated this from
    purchase_orders.total_amount, before real vendor invoices existed;
    Milestone 7 replaced that approximation with the real ledger.
    """

    def __init__(
        self,
        vendor_invoice_repository: VendorInvoiceRepository,
        vendor_repository: VendorRepository,
    ) -> None:
        self._vendor_invoice_repository = vendor_invoice_repository
        self._vendor_repository = vendor_repository

    async def get_vendor_balance(self, *, vendor_name: str) -> VendorBalance:
        vendor = await self._vendor_repository.get_by_name(vendor_name)
        if vendor is None:
            raise ValueError(f"Vendor not found: {vendor_name}")

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES, vendor_id=vendor.id
        )
        total_outstanding = sum((invoice.balance for invoice in invoices), Decimal("0"))
        oldest_due_date = min((invoice.due_date for invoice in invoices), default=None)

        return VendorBalance(
            vendor_code=vendor.vendor_code,
            vendor_name=vendor.company_name,
            total_outstanding=total_outstanding,
            open_invoice_count=len(invoices),
            oldest_due_date=oldest_due_date,
        )
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 5: Update the tool to match the new field names**

Replace the entire contents of `domains/finance/tools/get_vendor_balance.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetVendorBalanceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str


class GetVendorBalanceResult(BaseModel):
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_invoice_count: int
    oldest_due_date: date | None


async def get_vendor_balance_handler(
    params: GetVendorBalanceParams, context: ToolContext
) -> GetVendorBalanceResult:
    service = VendorService(VendorInvoiceRepository(context.db), VendorRepository(context.db))
    balance = await service.get_vendor_balance(vendor_name=params.vendor_name)
    return GetVendorBalanceResult(
        vendor_code=balance.vendor_code,
        vendor_name=balance.vendor_name,
        total_outstanding=balance.total_outstanding,
        open_invoice_count=balance.open_invoice_count,
        oldest_due_date=balance.oldest_due_date,
    )


GET_VENDOR_BALANCE_TOOL = ToolSpec(
    name="get_vendor_balance",
    description=(
        "Returns how much the company currently owes a single vendor: the "
        "total outstanding balance across that vendor's unpaid vendor "
        "invoices (status 'sent', 'partially_paid', or 'overdue'), how "
        "many such invoices exist, and the due date of the oldest one. "
        "Requires vendor_name (the vendor's company name as the user says "
        "it, e.g. 'Summit Traders' - not a business code). Use this "
        "whenever the user asks how much is owed to a specific vendor, "
        "however phrased - e.g. 'What do we owe Summit Traders?' or "
        "\"What's our balance with Cascade Logistics?\""
    ),
    parameters_model=GetVendorBalanceParams,
    result_model=GetVendorBalanceResult,
    handler=get_vendor_balance_handler,
)
```

- [ ] **Step 6: Update the tool's unit and integration tests**

Modify `backend/tests/test_get_vendor_balance_tool.py` — update any
reference to `open_purchase_order_count`/`oldest_order_date` to
`open_invoice_count`/`oldest_due_date` (the test file's structure —
params-model validation, `ToolSpec` wiring assertions — is otherwise
unchanged; read the existing file first and rename only the field
references, since its exact current content wasn't reproduced here to
avoid duplicating what Milestone 6 already wrote correctly).

Modify `backend/tests/test_get_vendor_balance_integration.py` similarly:
replace any `PurchaseOrderRepository`-based fixture setup with
`VendorInvoiceRepository`-based setup (creating vendor invoices with
`sent`/`overdue`/`paid` statuses instead of purchase orders with
`approved`/`received`/`draft` statuses), and rename result-field
assertions the same way.

- [ ] **Step 7: Run the tool tests to confirm they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_vendor_balance_tool.py tests/test_get_vendor_balance_integration.py -v`
Expected: PASS.

- [ ] **Step 8: Update the services README**

Modify `domains/finance/services/README.md`, replacing the last
paragraph:

```markdown
`InvoiceService` (Milestone 5, extended in Milestone 6) covers Accounts
Receivable: unpaid/overdue/search invoice queries and per-customer
balances. `VendorService` (Milestone 6, upgraded in Milestone 7) is the
Accounts Payable service: `get_vendor_balance` sums a vendor's
outstanding vendor invoices (`OUTSTANDING_VENDOR_INVOICE_STATUSES`),
`get_cash_position` reports the company's cash ledger balance, and
`list_outstanding_vendor_invoices` backs the `get_vendor_invoices` tool.
Milestone 6 originally approximated vendor balance from purchase orders,
before real vendor invoices/payments existed; that approximation is
gone now that the real ledger does. Both services call repositories
directly - neither executes SQL itself.
```

- [ ] **Step 9: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 10: Commit**

```bash
git add domains/finance/services/vendor_service.py domains/finance/tools/get_vendor_balance.py \
  domains/finance/services/README.md backend/tests/test_vendor_service.py \
  backend/tests/test_get_vendor_balance_tool.py backend/tests/test_get_vendor_balance_integration.py
git commit -m "feat: upgrade VendorService.get_vendor_balance to the real AP ledger

Replaces Milestone 6's purchase-order approximation now that real
vendor invoices/payments exist. VendorBalance's fields are renamed
(open_invoice_count/oldest_due_date) since it now counts invoices, not
purchase orders - a one-time breaking change to this dataclass and the
tool's result model, confined to this task."
```

---

### Task 10: `VendorService.get_cash_position`

**Files:**
- Modify: `domains/finance/services/vendor_service.py`
- Modify: `backend/tests/test_vendor_service.py`
- Modify: `domains/finance/tools/get_vendor_balance.py`
- Modify: `backend/tests/test_get_vendor_balance_tool.py`
- Modify: `backend/tests/test_get_vendor_balance_integration.py`

**Interfaces:**
- Consumes: `CashRepository.get_balance_as_of` (Task 5).
- Produces: `CashPosition` frozen dataclass (`balance: Decimal,
  as_of_date: date`), `VendorService.get_cash_position(as_of: date | None
  = None) -> CashPosition`. `VendorService.__init__` gains a third
  constructor argument, `cash_repository: CashRepository` (after
  `vendor_repository`) — every existing call site (the
  `get_vendor_balance` tool and its tests, from Task 9) must be updated
  to pass it.

- [ ] **Step 1: Write the failing service tests**

Add to `backend/tests/test_vendor_service.py`:

```python
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.services.vendor_service import CashPosition
```

(add these two import lines to the top of the file, alongside the
existing imports)

Update the `_service` helper to pass the new third argument:

```python
def _service(db_session: AsyncSession) -> VendorService:
    return VendorService(
        VendorInvoiceRepository(db_session),
        VendorRepository(db_session),
        CashRepository(db_session),
    )
```

(only the `CashRepository(db_session)` argument is new)

Add at the end of the file:

```python
async def _make_bank_account(db_session: AsyncSession, opening_balance: Decimal) -> None:
    from domains.finance.models import BankAccountModel

    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()


@pytest.mark.asyncio
async def test_get_cash_position_defaults_as_of_to_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("25000.00"))
    await db_session.commit()

    position = await _service(db_session).get_cash_position()

    assert isinstance(position, CashPosition)
    assert position.balance == Decimal("25000.00")
    assert position.as_of_date == date.today()


@pytest.mark.asyncio
async def test_get_cash_position_accepts_an_explicit_as_of(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("10000.00"))
    await db_session.commit()

    position = await _service(db_session).get_cash_position(as_of=date(2026, 3, 1))

    assert position.balance == Decimal("10000.00")
    assert position.as_of_date == date(2026, 3, 1)
```

Add `import uuid` to the top of the file (needed by `_make_bank_account`).

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: FAIL — `TypeError: VendorService.__init__() takes 3 positional
arguments but 4 were given` (the `_service` helper update runs ahead of
the constructor change), and `ImportError` for `CashPosition`.

- [ ] **Step 3: Implement**

Modify `domains/finance/services/vendor_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository

OUTSTANDING_VENDOR_INVOICE_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class VendorBalance:
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_invoice_count: int
    oldest_due_date: date | None


@dataclass(frozen=True)
class CashPosition:
    balance: Decimal
    as_of_date: date


class VendorService:
    """Business logic for accounts-payable vendor obligations and the
    company's cash position.

    get_vendor_balance sums a vendor's outstanding vendor_invoices.balance
    (status sent/partially_paid/overdue - the AP mirror of AR's
    UNPAID_STATUSES). get_cash_position reports the company's real cash
    ledger balance as of a date (defaults to today - a live, ongoing
    figure, same reasoning as InvoiceService.get_unpaid_invoices's as_of
    default).
    """

    def __init__(
        self,
        vendor_invoice_repository: VendorInvoiceRepository,
        vendor_repository: VendorRepository,
        cash_repository: CashRepository,
    ) -> None:
        self._vendor_invoice_repository = vendor_invoice_repository
        self._vendor_repository = vendor_repository
        self._cash_repository = cash_repository

    async def get_vendor_balance(self, *, vendor_name: str) -> VendorBalance:
        vendor = await self._vendor_repository.get_by_name(vendor_name)
        if vendor is None:
            raise ValueError(f"Vendor not found: {vendor_name}")

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES, vendor_id=vendor.id
        )
        total_outstanding = sum((invoice.balance for invoice in invoices), Decimal("0"))
        oldest_due_date = min((invoice.due_date for invoice in invoices), default=None)

        return VendorBalance(
            vendor_code=vendor.vendor_code,
            vendor_name=vendor.company_name,
            total_outstanding=total_outstanding,
            open_invoice_count=len(invoices),
            oldest_due_date=oldest_due_date,
        )

    async def get_cash_position(self, as_of: date | None = None) -> CashPosition:
        effective_as_of = as_of if as_of is not None else date.today()
        balance = await self._cash_repository.get_balance_as_of(effective_as_of)
        return CashPosition(balance=balance, as_of_date=effective_as_of)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: PASS, all 6 tests.

- [ ] **Step 5: Update the `get_vendor_balance` tool's handler to pass the new argument**

Modify `domains/finance/tools/get_vendor_balance.py` — the handler
constructs `VendorService` with one more argument:

```python
from domains.finance.repositories.cash_repository import CashRepository
```

(add this import line, alongside the existing repository imports)

```python
async def get_vendor_balance_handler(
    params: GetVendorBalanceParams, context: ToolContext
) -> GetVendorBalanceResult:
    service = VendorService(
        VendorInvoiceRepository(context.db),
        VendorRepository(context.db),
        CashRepository(context.db),
    )
    balance = await service.get_vendor_balance(vendor_name=params.vendor_name)
    return GetVendorBalanceResult(
        vendor_code=balance.vendor_code,
        vendor_name=balance.vendor_name,
        total_outstanding=balance.total_outstanding,
        open_invoice_count=balance.open_invoice_count,
        oldest_due_date=balance.oldest_due_date,
    )
```

(only the `VendorService(...)` construction call changes, from two
arguments to three; everything else in the file — params/result models,
`GET_VENDOR_BALANCE_TOOL` — is unchanged from Task 9)

- [ ] **Step 6: Update the tool's own tests for the new constructor arity**

Modify `backend/tests/test_get_vendor_balance_integration.py` — any
direct `VendorService(...)` construction in the test file (if present)
gains the third `CashRepository(db_session)` argument, matching Step 3's
change. If the integration test only calls the handler (not the service
directly), no change is needed there since the handler already
constructs its own dependencies internally.

- [ ] **Step 7: Run the tool tests to confirm they still pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_vendor_balance_tool.py tests/test_get_vendor_balance_integration.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add domains/finance/services/vendor_service.py domains/finance/tools/get_vendor_balance.py \
  backend/tests/test_vendor_service.py backend/tests/test_get_vendor_balance_tool.py \
  backend/tests/test_get_vendor_balance_integration.py
git commit -m "feat: add VendorService.get_cash_position

Reports the company's real cash-ledger balance as of a date (defaults
to today). VendorService.__init__ gains a third constructor argument
(CashRepository) - the get_vendor_balance tool's handler updated to
match; its own params/result contract is unchanged."
```

---

### Task 11: `VendorService.list_outstanding_vendor_invoices`

**Files:**
- Modify: `domains/finance/services/vendor_service.py`
- Modify: `backend/tests/test_vendor_service.py`

**Interfaces:**
- Produces: `VendorInvoiceRecord` frozen dataclass
  (`vendor_invoice_number, vendor_name, issue_date, due_date, total,
  balance, days_until_due, status`),
  `VendorService.list_outstanding_vendor_invoices(as_of: date | None =
  None) -> list[VendorInvoiceRecord]`, sorted by `due_date` ascending
  (soonest-due first).

- [ ] **Step 1: Write the failing service tests**

Add to `backend/tests/test_vendor_service.py`:

```python
from domains.finance.services.vendor_service import VendorInvoiceRecord
```

(add to the existing import line from `domains.finance.services.
vendor_service`)

Add at the end of the file:

```python
@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_excludes_paid_draft_cancelled(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-4001", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    for number, status in [
        ("VINV-5002", "paid"), ("VINV-5003", "draft"), ("VINV-5004", "cancelled"),
    ]:
        await invoice_repo.create(
            vendor_invoice_number=number, vendor_id=vendor.id, purchase_order_id=None,
            issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status=status,
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        as_of=date(2026, 7, 8)
    )

    assert [r.vendor_invoice_number for r in records] == ["VINV-5001"]
    assert records[0].vendor_name == "Summit Traders"
    assert records[0].days_until_due == (date(2026, 7, 1) - date(2026, 7, 8)).days == -7


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_sorts_by_due_date_ascending(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-4101", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-5102", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 6, 15), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        as_of=date(2026, 7, 8)
    )

    assert [r.vendor_invoice_number for r in records] == ["VINV-5102", "VINV-5101"]


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_defaults_as_of_to_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    records = await _service(db_session).list_outstanding_vendor_invoices()
    assert records == []
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: FAIL — `AttributeError: 'VendorService' object has no attribute
'list_outstanding_vendor_invoices'`.

- [ ] **Step 3: Implement**

Modify `domains/finance/services/vendor_service.py` — add the new
dataclass after `CashPosition`:

```python
@dataclass(frozen=True)
class VendorInvoiceRecord:
    vendor_invoice_number: str
    vendor_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_until_due: int
    status: str
```

Add the method to `VendorService`, after `get_cash_position`:

```python
    async def list_outstanding_vendor_invoices(
        self, as_of: date | None = None
    ) -> list[VendorInvoiceRecord]:
        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES
        )
        vendors = await self._vendor_repository.list_all()
        vendor_names = {vendor.id: vendor.company_name for vendor in vendors}

        records = [
            VendorInvoiceRecord(
                vendor_invoice_number=invoice.vendor_invoice_number,
                vendor_name=vendor_names.get(invoice.vendor_id, "Unknown vendor"),
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                total=invoice.total,
                balance=invoice.balance,
                days_until_due=(invoice.due_date - effective_as_of).days,
                status=invoice.status,
            )
            for invoice in invoices
        ]
        records.sort(key=lambda record: record.due_date)
        return records
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: PASS, all 9 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/services/vendor_service.py backend/tests/test_vendor_service.py
git commit -m "feat: add VendorService.list_outstanding_vendor_invoices

Sorted by due_date ascending (soonest-due first) - the natural
prioritization ordering, mirroring get_overdue_invoices's deliberate
urgency sort rather than search_invoices's incidental one.
days_until_due is signed (negative for already-overdue invoices),
giving Phase 2 a real urgency figure to reason over."
```

---

### Task 12: `get_cash_position` tool + registration

**Files:**
- Create: `domains/finance/tools/get_cash_position.py`
- Create: `backend/tests/test_get_cash_position_tool.py`
- Modify: `backend/app/core/tool_registry.py`
- Modify: `backend/tests/test_app_tool_registry.py`
- Modify: `domains/finance/tools/README.md`

**Interfaces:**
- Consumes: `VendorService.get_cash_position` (Task 10).
- Produces: `GetCashPositionParams` (no fields, `extra="forbid"`),
  `GetCashPositionResult(balance: Decimal, as_of_date: date)`,
  `get_cash_position_handler(params, context) -> GetCashPositionResult`,
  module-level `GET_CASH_POSITION_TOOL: ToolSpec`.

- [ ] **Step 1: Write the failing tool unit tests**

Create `backend/tests/test_get_cash_position_tool.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_cash_position import (
    GET_CASH_POSITION_TOOL,
    GetCashPositionParams,
    get_cash_position_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCashPositionParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_takes_no_fields() -> None:
    params = GetCashPositionParams()
    assert params.model_dump() == {}


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_CASH_POSITION_TOOL.name == "get_cash_position"
    assert "cash" in GET_CASH_POSITION_TOOL.description.lower()
    assert GET_CASH_POSITION_TOOL.handler is get_cash_position_handler
    assert GET_CASH_POSITION_TOOL.parameters_model is GetCashPositionParams
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_cash_position_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.tools.get_cash_position'`.

- [ ] **Step 3: Implement the tool**

Create `domains/finance/tools/get_cash_position.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetCashPositionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCashPositionResult(BaseModel):
    balance: Decimal
    as_of_date: date


async def get_cash_position_handler(
    params: GetCashPositionParams, context: ToolContext
) -> GetCashPositionResult:
    service = VendorService(
        VendorInvoiceRepository(context.db),
        VendorRepository(context.db),
        CashRepository(context.db),
    )
    position = await service.get_cash_position()
    return GetCashPositionResult(balance=position.balance, as_of_date=position.as_of_date)


GET_CASH_POSITION_TOOL = ToolSpec(
    name="get_cash_position",
    description=(
        "Returns the company's current cash balance (as of today) from "
        "its bank account ledger. Takes no parameters. Use this whenever "
        "the user asks about cash on hand, available cash, or how much "
        "money the company has, however phrased - e.g. 'What's our cash "
        "position?', 'How much cash do we have?', or as one of several "
        "tools when reasoning about which bills to pay first (combine "
        "with get_vendor_invoices for that)."
    ),
    parameters_model=GetCashPositionParams,
    result_model=GetCashPositionResult,
    handler=get_cash_position_handler,
)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_cash_position_tool.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Register the tool**

Modify `backend/app/core/tool_registry.py`:

```python
from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_cash_position import GET_CASH_POSITION_TOOL
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.get_vendor_balance import GET_VENDOR_BALANCE_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    registry.register(GET_VENDOR_BALANCE_TOOL)
    registry.register(GET_CASH_POSITION_TOOL)
    return registry
```

(the critical, easy-to-miss detail from Milestone 6 Task 4's fix round:
`from __future__ import annotations` MUST stay as the file's first line
— double-check it after editing)

Modify `backend/tests/test_app_tool_registry.py` — the test asserting the
full tool-name set gains `"get_cash_position"` (read the existing test
first and add the one new name to whatever set/list comparison it uses).

- [ ] **Step 6: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_app_tool_registry.py -v`
Expected: PASS.

- [ ] **Step 7: Update the tools README**

Modify `domains/finance/tools/README.md`, adding a new paragraph at the
end:

```markdown
`get_cash_position` (Milestone 7) returns the company's current cash
balance from the real bank-account ledger (`CashRepository`). Takes no
parameters. Used alongside `get_vendor_invoices` when the user asks a
reasoning question with no single-tool answer (e.g. "which invoices
should I pay first?") - Phase 2 reasons over both results together.
```

- [ ] **Step 8: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add domains/finance/tools/get_cash_position.py backend/tests/test_get_cash_position_tool.py \
  backend/app/core/tool_registry.py backend/tests/test_app_tool_registry.py \
  domains/finance/tools/README.md
git commit -m "feat: add get_cash_position tool"
```

---

### Task 13: Seeded-DB integration test for `get_cash_position`

**Files:**
- Create: `backend/tests/test_get_cash_position_integration.py`

**Interfaces:**
- Consumes: `get_cash_position_handler`, `GetCashPositionParams` (Task 12).

- [ ] **Step 1: Write the integration tests**

Create `backend/tests/test_get_cash_position_integration.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import BankAccountModel, CashTransactionModel, PaymentModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_cash_position import GetCashPositionParams, get_cash_position_handler


@pytest.mark.asyncio
async def test_seeded_db_returns_opening_balance_when_no_transactions(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("42000.00"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_cash_position_handler(GetCashPositionParams(), context)

    assert result.balance == Decimal("42000.00")
    assert result.as_of_date == date.today()


@pytest.mark.asyncio
async def test_seeded_db_reflects_a_customer_payment_transaction(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=Decimal("10000.00"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()

    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9801", company_name="Acme Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-9801", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("2500"), tax=Decimal("0"), total=Decimal("2500"),
    )
    payment = PaymentModel(
        id=uuid.uuid4(), invoice_id=invoice.id, payment_date=date.today(),
        amount=Decimal("2500"), payment_method="bank_transfer",
    )
    db_session.add(payment)
    db_session.add(
        CashTransactionModel(
            id=uuid.uuid4(), bank_account_id=account.id, transaction_date=date.today(),
            amount=Decimal("2500"), transaction_type="customer_payment", payment_id=payment.id,
        )
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_cash_position_handler(GetCashPositionParams(), context)

    assert result.balance == Decimal("12500.00")
```

- [ ] **Step 2: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_cash_position_integration.py -v`
Expected: PASS immediately (Tasks 5/10/12 already implement everything
this test exercises). If it fails, that indicates a real bug in existing
Task 5/10/12 code — investigate rather than guessing a fix here.

- [ ] **Step 3: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_get_cash_position_integration.py
git commit -m "test: add seeded-DB integration coverage for get_cash_position"
```

---

### Task 14: `get_vendor_invoices` tool + registration

**Files:**
- Create: `domains/finance/tools/get_vendor_invoices.py`
- Create: `backend/tests/test_get_vendor_invoices_tool.py`
- Modify: `backend/app/core/tool_registry.py`
- Modify: `backend/tests/test_app_tool_registry.py`
- Modify: `domains/finance/tools/README.md`

**Interfaces:**
- Consumes: `VendorService.list_outstanding_vendor_invoices` (Task 11).
- Produces: `GetVendorInvoicesParams(vendor_id: str | None = None)`
  (business code, optional — consistent with the AR list tools'
  convention, deliberately *not* `vendor_name` since this tool's job is
  bulk retrieval across vendors, not single-entity resolution),
  `VendorInvoiceOut`, `VendorInvoicesSummary(count, total_outstanding)`,
  `GetVendorInvoicesResult(invoices, summary)`,
  `get_vendor_invoices_handler(params, context) ->
  GetVendorInvoicesResult`, module-level `GET_VENDOR_INVOICES_TOOL:
  ToolSpec`.

Note: `VendorService.list_outstanding_vendor_invoices` (Task 11) doesn't
take a `vendor_id` filter yet — this task extends it to accept one,
mirroring `InvoiceService.get_overdue_invoices`'s `customer_id`
parameter shape exactly.

- [ ] **Step 1: Write the failing tool unit tests**

Create `backend/tests/test_get_vendor_invoices_tool.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_vendor_invoices import (
    GET_VENDOR_INVOICES_TOOL,
    GetVendorInvoicesParams,
    get_vendor_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetVendorInvoicesParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_defaults_are_none() -> None:
    params = GetVendorInvoicesParams()
    assert params.vendor_id is None


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_VENDOR_INVOICES_TOOL.name == "get_vendor_invoices"
    assert "vendor" in GET_VENDOR_INVOICES_TOOL.description.lower()
    assert GET_VENDOR_INVOICES_TOOL.handler is get_vendor_invoices_handler
    assert GET_VENDOR_INVOICES_TOOL.parameters_model is GetVendorInvoicesParams
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_vendor_invoices_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.tools.get_vendor_invoices'`.

- [ ] **Step 3: Extend `VendorService.list_outstanding_vendor_invoices` with an optional `vendor_id` filter**

Modify `domains/finance/services/vendor_service.py`:

```python
    async def list_outstanding_vendor_invoices(
        self, *, vendor_id: str | None = None, as_of: date | None = None
    ) -> list[VendorInvoiceRecord]:
        resolved_vendor_id: uuid.UUID | None = None
        if vendor_id is not None:
            vendor = await self._vendor_repository.get_by_code(vendor_id)
            if vendor is None:
                raise ValueError(f"Vendor not found: {vendor_id}")
            resolved_vendor_id = vendor.id

        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES, vendor_id=resolved_vendor_id
        )
        vendors = await self._vendor_repository.list_all()
        vendor_names = {vendor.id: vendor.company_name for vendor in vendors}

        records = [
            VendorInvoiceRecord(
                vendor_invoice_number=invoice.vendor_invoice_number,
                vendor_name=vendor_names.get(invoice.vendor_id, "Unknown vendor"),
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                total=invoice.total,
                balance=invoice.balance,
                days_until_due=(invoice.due_date - effective_as_of).days,
                status=invoice.status,
            )
            for invoice in invoices
        ]
        records.sort(key=lambda record: record.due_date)
        return records
```

(replaces Task 11's version of this method — the signature gains a
keyword-only `vendor_id: str | None = None` parameter and the
name-resolution block from `get_vendor_balance`, everything else
unchanged; add `import uuid` to the top of `vendor_service.py` if not
already present, needed for `uuid.UUID` in the new local variable's type
annotation)

- [ ] **Step 4: Add a test for the new filter and re-run the service test file**

Add to `backend/tests/test_vendor_service.py`:

```python
@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_filters_by_vendor_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-4201", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-4202", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-5201", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-5202", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    records = await _service(db_session).list_outstanding_vendor_invoices(
        vendor_id="VEND-4201", as_of=date(2026, 7, 8)
    )
    assert [r.vendor_invoice_number for r in records] == ["VINV-5201"]


@pytest.mark.asyncio
async def test_list_outstanding_vendor_invoices_unknown_vendor_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).list_outstanding_vendor_invoices(vendor_id="VEND-DOES-NOT-EXIST")
```

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_vendor_service.py -v`
Expected: PASS, all 11 tests.

- [ ] **Step 5: Implement the tool**

Create `domains/finance/tools/get_vendor_invoices.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetVendorInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: str | None = None


class VendorInvoiceOut(BaseModel):
    vendor_invoice_number: str
    vendor_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_until_due: int
    status: str


class VendorInvoicesSummary(BaseModel):
    count: int
    total_outstanding: Decimal


class GetVendorInvoicesResult(BaseModel):
    invoices: list[VendorInvoiceOut]
    summary: VendorInvoicesSummary


async def get_vendor_invoices_handler(
    params: GetVendorInvoicesParams, context: ToolContext
) -> GetVendorInvoicesResult:
    service = VendorService(
        VendorInvoiceRepository(context.db),
        VendorRepository(context.db),
        CashRepository(context.db),
    )
    records = await service.list_outstanding_vendor_invoices(vendor_id=params.vendor_id)
    invoices_out = [
        VendorInvoiceOut(
            vendor_invoice_number=record.vendor_invoice_number,
            vendor_name=record.vendor_name,
            issue_date=record.issue_date,
            due_date=record.due_date,
            total=record.total,
            balance=record.balance,
            days_until_due=record.days_until_due,
            status=record.status,
        )
        for record in records
    ]
    total_outstanding = sum((invoice.balance for invoice in invoices_out), Decimal("0"))
    return GetVendorInvoicesResult(
        invoices=invoices_out,
        summary=VendorInvoicesSummary(
            count=len(invoices_out), total_outstanding=total_outstanding
        ),
    )


GET_VENDOR_INVOICES_TOOL = ToolSpec(
    name="get_vendor_invoices",
    description=(
        "Returns the company's outstanding vendor invoices (status "
        "'sent', 'partially_paid', or 'overdue' - bills not yet fully "
        "paid), sorted by due date, soonest first. Optionally filter to "
        "one vendor via vendor_id (business code, e.g. 'VEND-0007'). Use "
        "this for 'what vendor invoices are outstanding' style questions, "
        "and as one of several tools when reasoning about which bills to "
        "pay first (combine with get_cash_position for that) - e.g. "
        "'Which invoices should I pay first?' or 'What vendor bills are "
        "outstanding?'"
    ),
    parameters_model=GetVendorInvoicesParams,
    result_model=GetVendorInvoicesResult,
    handler=get_vendor_invoices_handler,
)
```

- [ ] **Step 6: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_vendor_invoices_tool.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 7: Register the tool**

Modify `backend/app/core/tool_registry.py`:

```python
from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_cash_position import GET_CASH_POSITION_TOOL
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.get_vendor_balance import GET_VENDOR_BALANCE_TOOL
from domains.finance.tools.get_vendor_invoices import GET_VENDOR_INVOICES_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    registry.register(GET_VENDOR_BALANCE_TOOL)
    registry.register(GET_CASH_POSITION_TOOL)
    registry.register(GET_VENDOR_INVOICES_TOOL)
    return registry
```

(double-check `from __future__ import annotations` survives as line 1)

Modify `backend/tests/test_app_tool_registry.py` — add
`"get_vendor_invoices"` to the expected tool-name set.

- [ ] **Step 8: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_app_tool_registry.py -v`
Expected: PASS.

- [ ] **Step 9: Update the tools README**

Modify `domains/finance/tools/README.md`, adding a new paragraph:

```markdown
`get_vendor_invoices` (Milestone 7) returns the company's outstanding
vendor invoices (status sent/partially_paid/overdue), sorted by due
date soonest-first, optionally filtered to one vendor by `vendor_id`
(business code). Used alongside `get_cash_position` for
payment-prioritization reasoning questions.
```

- [ ] **Step 10: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 11: Commit**

```bash
git add domains/finance/services/vendor_service.py backend/tests/test_vendor_service.py \
  domains/finance/tools/get_vendor_invoices.py backend/tests/test_get_vendor_invoices_tool.py \
  backend/app/core/tool_registry.py backend/tests/test_app_tool_registry.py \
  domains/finance/tools/README.md
git commit -m "feat: add get_vendor_invoices tool

VendorService.list_outstanding_vendor_invoices gains an optional
vendor_id business-code filter (mirroring get_overdue_invoices's
customer_id shape), consumed by the new tool."
```

---

### Task 15: Seeded-DB integration test for `get_vendor_invoices`

**Files:**
- Create: `backend/tests/test_get_vendor_invoices_integration.py`

**Interfaces:**
- Consumes: `get_vendor_invoices_handler`, `GetVendorInvoicesParams`
  (Task 14).

- [ ] **Step 1: Write the integration tests**

Create `backend/tests/test_get_vendor_invoices_integration.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.tools.get_vendor_invoices import (
    GetVendorInvoicesParams,
    get_vendor_invoices_handler,
)


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


@pytest.mark.asyncio
async def test_seeded_db_lists_outstanding_invoices_sorted_by_due_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-9301", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-9302", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-9301", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("1000.00"), tax=Decimal("0"), total=Decimal("1000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9302", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 6, 1), status="overdue",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9303", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 6, 1), status="paid",
        subtotal=Decimal("999.00"), tax=Decimal("0"), total=Decimal("999.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_invoices_handler(GetVendorInvoicesParams(), context)

    assert [i.vendor_invoice_number for i in result.invoices] == ["VINV-9302", "VINV-9301"]
    assert result.summary.count == 2
    assert result.summary.total_outstanding == Decimal("1500.00")


@pytest.mark.asyncio
async def test_seeded_db_filters_by_vendor_id(clean_db: None, db_session: AsyncSession) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-9401", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-9402", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-9401", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9402", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_invoices_handler(
        GetVendorInvoicesParams(vendor_id="VEND-9401"), context
    )
    assert [i.vendor_invoice_number for i in result.invoices] == ["VINV-9401"]


@pytest.mark.asyncio
async def test_seeded_db_unknown_vendor_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Vendor not found"):
        await get_vendor_invoices_handler(
            GetVendorInvoicesParams(vendor_id="VEND-DOES-NOT-EXIST"), context
        )
```

- [ ] **Step 2: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_vendor_invoices_integration.py -v`
Expected: PASS immediately (Tasks 11/14 already implement everything
this test exercises). If it fails, investigate the real bug in that
existing code rather than adjusting this test.

- [ ] **Step 3: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_get_vendor_invoices_integration.py
git commit -m "test: add seeded-DB integration coverage for get_vendor_invoices"
```

---

### Task 16: `get_customer` tool + registration

**Files:**
- Create: `domains/finance/tools/get_customer.py`
- Create: `backend/tests/test_get_customer_tool.py`
- Modify: `backend/app/core/tool_registry.py`
- Modify: `backend/tests/test_app_tool_registry.py`
- Modify: `domains/finance/tools/README.md`

**Interfaces:**
- Consumes: `CustomerRepository.get_by_name` (already exists, Milestone
  6).
- Produces: `GetCustomerParams(customer_name: str)` (required),
  `GetCustomerResult(customer_code: str, customer_name: str)`,
  `get_customer_handler(params, context) -> GetCustomerResult`,
  module-level `GET_CUSTOMER_TOOL: ToolSpec`. Deliberately *not* a
  superset of `get_customer_balance`'s result (no balance field) — this
  is a pure identity lookup, so the planner never has a reason to call
  the more expensive/business-meaningful tool just to extract a code for
  piping into another tool's `customer_id` parameter (Task 19).

- [ ] **Step 1: Write the failing tool unit tests**

Create `backend/tests/test_get_customer_tool.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL, GetCustomerParams


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCustomerParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_requires_customer_name() -> None:
    with pytest.raises(ValidationError):
        GetCustomerParams()  # type: ignore[call-arg]


def test_tool_spec_wires_up_the_handler() -> None:
    from domains.finance.tools.get_customer import get_customer_handler

    assert GET_CUSTOMER_TOOL.name == "get_customer"
    assert "not a business code" in GET_CUSTOMER_TOOL.description.lower()
    assert GET_CUSTOMER_TOOL.handler is get_customer_handler
    assert GET_CUSTOMER_TOOL.parameters_model is GetCustomerParams
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_customer_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'domains.finance.tools.get_customer'`.

- [ ] **Step 3: Implement the tool**

Create `domains/finance/tools/get_customer.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository


class GetCustomerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str


class GetCustomerResult(BaseModel):
    customer_code: str
    customer_name: str


async def get_customer_handler(params: GetCustomerParams, context: ToolContext) -> GetCustomerResult:
    repository = CustomerRepository(context.db)
    customer = await repository.get_by_name(params.customer_name)
    if customer is None:
        raise ValueError(f"Customer not found: {params.customer_name}")
    return GetCustomerResult(customer_code=customer.customer_code, customer_name=customer.company_name)


GET_CUSTOMER_TOOL = ToolSpec(
    name="get_customer",
    description=(
        "Resolves a customer's company name to their business code and "
        "confirmed name - a pure identity lookup with no balance or "
        "invoice data. Requires customer_name (the company name as the "
        "user says it, e.g. 'ABC Industries' - not a business code). Use "
        "this as the first step of a multi-step plan when a later tool "
        "call needs a customer_id (business code) but the user only gave "
        "a company name - e.g. 'Which of those belong to ABC Industries?' "
        "resolves ABC Industries to its code first, then filters the "
        "invoice tool by that code. Don't use this when the question is "
        "just about one customer's balance (use get_customer_balance "
        "directly instead)."
    ),
    parameters_model=GetCustomerParams,
    result_model=GetCustomerResult,
    handler=get_customer_handler,
)
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_customer_tool.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 5: Register the tool**

Modify `backend/app/core/tool_registry.py`:

```python
from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_cash_position import GET_CASH_POSITION_TOOL
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.get_vendor_balance import GET_VENDOR_BALANCE_TOOL
from domains.finance.tools.get_vendor_invoices import GET_VENDOR_INVOICES_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    registry.register(GET_VENDOR_BALANCE_TOOL)
    registry.register(GET_CASH_POSITION_TOOL)
    registry.register(GET_VENDOR_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_TOOL)
    return registry
```

(double-check `from __future__ import annotations` survives as line 1 —
this file has now been edited five times across Milestones 6-7; treat
this check as mandatory every time)

Modify `backend/tests/test_app_tool_registry.py` — add `"get_customer"`
to the expected tool-name set.

- [ ] **Step 6: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_app_tool_registry.py -v`
Expected: PASS.

- [ ] **Step 7: Update the tools README**

Modify `domains/finance/tools/README.md`, adding a final paragraph:

```markdown
`get_customer` (Milestone 7) is a pure name-to-code identity lookup - no
balance, no invoices. It exists specifically so the planner can chain
it into a later tool call that needs a `customer_id` business code but
the user only gave a company name (see `ExecutionPlanner`'s parameter
piping) - e.g. resolving "ABC Industries" before filtering
`get_overdue_invoices(customer_id=...)` by it.
```

- [ ] **Step 8: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add domains/finance/tools/get_customer.py backend/tests/test_get_customer_tool.py \
  backend/app/core/tool_registry.py backend/tests/test_app_tool_registry.py \
  domains/finance/tools/README.md
git commit -m "feat: add get_customer name-to-code lookup tool

Deliberately a flat, balance-free result distinct from
get_customer_balance - this tool exists specifically to be piped into a
later tool call's customer_id parameter (Task 19), not to answer a
balance question on its own."
```

---

### Task 17: Seeded-DB integration test for `get_customer`

**Files:**
- Create: `backend/tests/test_get_customer_integration.py`

**Interfaces:**
- Consumes: `get_customer_handler`, `GetCustomerParams` (Task 16).

- [ ] **Step 1: Write the integration tests**

Create `backend/tests/test_get_customer_integration.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.tools.get_customer import GetCustomerParams, get_customer_handler


@pytest.mark.asyncio
async def test_seeded_db_resolves_customer_by_name(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9501", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_customer_handler(GetCustomerParams(customer_name="ABC Industries"), context)

    assert result.customer_code == "CUST-9501"
    assert result.customer_name == "ABC Industries"


@pytest.mark.asyncio
async def test_seeded_db_resolution_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-9502", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_customer_handler(GetCustomerParams(customer_name="abc industries"), context)
    assert result.customer_code == "CUST-9502"


@pytest.mark.asyncio
async def test_seeded_db_unknown_customer_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_customer_handler(GetCustomerParams(customer_name="Nonexistent Corp"), context)
```

- [ ] **Step 2: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_get_customer_integration.py -v`
Expected: PASS immediately (Task 16 already implements everything this
test exercises; `CustomerRepository.get_by_name` is unchanged from
Milestone 6).

- [ ] **Step 3: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_get_customer_integration.py
git commit -m "test: add seeded-DB integration coverage for get_customer"
```

---

## Phase A complete: 17 tasks (schema, simulator, repositories, services,
three new tools: `get_cash_position`, `get_vendor_invoices`,
`get_customer`, plus the `get_vendor_balance` upgrade to the real
ledger). Phase B builds the multi-tool orchestration engine on top.

---

## Phase B — Multi-Tool Orchestration

### Task 18: Cap plans at 5 tool calls, fail gracefully into a clarifying question

**Files:**
- Modify: `ai_platform/orchestration/planner.py`
- Modify: `backend/tests/test_planner.py`

**Interfaces:**
- Produces: `MAX_TOOL_CALLS_PER_PLAN: Final[int] = 5` (module constant),
  `Planner.create_plan` returns `Plan(clarification_needed=...)` directly
  (never raises) when the raw plan's `tool_calls` list exceeds the cap —
  every other malformed-plan case keeps today's existing `AIError`
  behavior unchanged.

- [ ] **Step 1: Write the failing tests**

Read `backend/tests/test_planner.py` first to see the existing test
file's fixtures (a `FakeLLMService`-backed `Planner` construction
helper) and match its style. Add:

```python
@pytest.mark.asyncio
async def test_create_plan_returns_clarification_when_tool_calls_exceed_the_cap() -> None:
    tool_calls_json = ", ".join(
        f'{{"tool": "get_current_date", "parameters": {{}}}}' for _ in range(6)
    )
    llm_service = FakeLLMService(
        tokens=["unused"], plan_response=f'{{"tool_calls": [{tool_calls_json}]}}'
    )
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    plan = await planner.create_plan([], "do six things")

    assert plan.clarification_needed is not None
    assert plan.tool_calls is None
    assert "narrow" in plan.clarification_needed.lower()


@pytest.mark.asyncio
async def test_create_plan_accepts_exactly_five_tool_calls() -> None:
    tool_calls_json = ", ".join(
        f'{{"tool": "get_current_date", "parameters": {{}}}}' for _ in range(5)
    )
    llm_service = FakeLLMService(
        tokens=["unused"], plan_response=f'{{"tool_calls": [{tool_calls_json}]}}'
    )
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    plan = await planner.create_plan([], "do five things")

    assert plan.tool_calls is not None
    assert len(plan.tool_calls) == 5
```

(add these to whatever imports the existing file already has — it should
already import `FakeLLMService`, `Planner`, `PromptBuilder`,
`ToolRegistry`, `GET_CURRENT_DATE_TOOL`, and `pytest`, given it already
tests `create_plan`'s other branches; add any of these that are missing)

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planner.py -v`
Expected: FAIL — six tool calls currently either get accepted (no cap
exists yet) or raise `AIError` from a generic `ValidationError`, not
`plan.clarification_needed` being set.

- [ ] **Step 3: Implement the cap**

Modify `ai_platform/orchestration/planner.py`:

```python
from __future__ import annotations

import json
from typing import Any, Final

from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import HistoryMessage
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.planning_prompt import build_planning_prompt
from ai_platform.tool_registry.registry import ToolRegistry
from app.core.errors import AIError

MAX_TOOL_CALLS_PER_PLAN: Final[int] = 5
TOO_MANY_TOOL_CALLS_MESSAGE: Final[str] = (
    "That's a lot to look up at once - could you narrow your question down a bit?"
)


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
        except json.JSONDecodeError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc

        raw_tool_calls = data.get("tool_calls") if isinstance(data, dict) else None
        if isinstance(raw_tool_calls, list) and len(raw_tool_calls) > MAX_TOOL_CALLS_PER_PLAN:
            return Plan(clarification_needed=TOO_MANY_TOOL_CALLS_MESSAGE)

        try:
            return Plan.model_validate(data)
        except PydanticValidationError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc
```

(the `json.loads` call is split out of the original single `try` block
so the tool-call-count check can run between parsing and validation;
every other line — including the `AIError` messages themselves — is
unchanged from before this task)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planner.py -v`
Expected: PASS, including every pre-existing test in the file (confirm
the full file, not just the two new tests, since `create_plan`'s control
flow changed).

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/orchestration/planner.py backend/tests/test_planner.py
git commit -m "feat: cap plans at 5 tool calls, fail gracefully into a clarifying question

An oversized plan now returns Plan(clarification_needed=...) directly
instead of raising a generic AIError - reuses the plan's existing
three-branch contract rather than a new failure path. Every other
malformed-plan case (bad JSON, wrong shape) is unchanged."
```

---

### Task 19: `ExecutionPlanner` — parameter-piping resolution

**Files:**
- Create: `ai_platform/orchestration/execution_planner.py`
- Create: `backend/tests/test_execution_planner.py`

**Interfaces:**
- Consumes: `ToolExecutionOutcome` (`ai_platform.tool_registry.executor`,
  unchanged).
- Produces: `ExecutionPlanner().resolve_parameters(parameters:
  dict[str, Any], prior_outcomes: list[ToolExecutionOutcome]) ->
  tuple[dict[str, Any] | None, str | None]` — returns `(resolved, None)`
  on success, `(None, error_message)` if any `$stepN.field` reference in
  `parameters` can't be resolved.

Design refinement from the spec: `ExecutionPlanner` is a **pure**
resolver with no `run()` method and no dependency on `ToolExecutor` —
`ChatWorkflow` (Task 20) keeps its own per-step loop and still emits a
`tool_call` event before each execution, exactly as it does today. A
`run()` method that internally looped and executed every step would
lose that per-step streaming (all `tool_call` events would only appear
after every step in the plan had already finished), regressing a real
behavior Milestone 3 established. Keeping `ExecutionPlanner` a pure,
synchronous function needing no database or `ToolExecutor` also makes
this task's own tests simpler — no `clean_db`/`db_session` fixtures
needed at all.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_execution_planner.py`:

```python
from __future__ import annotations

from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.tool_registry.executor import ToolExecutionOutcome


def _success_outcome(tool: str, result: dict[str, object]) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        tool=tool, parameters={}, result=result, status="success",
        error_message=None, duration_ms=1,
    )


def _error_outcome(tool: str) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        tool=tool, parameters={}, result=None, status="error",
        error_message="boom", duration_ms=1,
    )


def test_resolve_parameters_passes_through_literal_values_unchanged() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"minimum_days": 30, "status": "overdue"}, [])
    assert error is None
    assert resolved == {"minimum_days": 30, "status": "overdue"}


def test_resolve_parameters_substitutes_a_step_reference() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_code": "CUST-0042"})]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert error is None
    assert resolved == {"customer_id": "CUST-0042"}


def test_resolve_parameters_mixes_literal_and_referenced_values() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_code": "CUST-0042"})]

    resolved, error = planner.resolve_parameters(
        {"customer_id": "$step0.customer_code", "minimum_days": 30}, prior
    )

    assert error is None
    assert resolved == {"customer_id": "CUST-0042", "minimum_days": 30}


def test_resolve_parameters_fails_when_step_index_does_not_exist() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, [])
    assert resolved is None
    assert error is not None
    assert "step 0" in error


def test_resolve_parameters_fails_when_referenced_step_did_not_succeed() -> None:
    planner = ExecutionPlanner()
    prior = [_error_outcome("get_customer")]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert resolved is None
    assert error is not None
    assert "did not succeed" in error


def test_resolve_parameters_fails_when_field_is_missing_from_the_result() -> None:
    planner = ExecutionPlanner()
    prior = [_success_outcome("get_customer", {"customer_name": "ABC Industries"})]

    resolved, error = planner.resolve_parameters({"customer_id": "$step0.customer_code"}, prior)

    assert resolved is None
    assert error is not None
    assert "customer_code" in error


def test_resolve_parameters_ignores_strings_that_are_not_step_references() -> None:
    planner = ExecutionPlanner()
    resolved, error = planner.resolve_parameters({"vendor_name": "$100 Traders"}, [])
    assert error is None
    assert resolved == {"vendor_name": "$100 Traders"}
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_execution_planner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.orchestration.execution_planner'`.

- [ ] **Step 3: Implement**

Create `ai_platform/orchestration/execution_planner.py`:

```python
from __future__ import annotations

import re
from typing import Any

from ai_platform.tool_registry.executor import ToolExecutionOutcome

_STEP_REFERENCE = re.compile(r"^\$step(\d+)\.(\w+)$")


class ExecutionPlanner:
    """Resolves `$stepN.field` parameter references against prior tool
    outcomes in the same plan - the deterministic "how" behind the
    LLM's declarative "what" (CLAUDE.md: FastAPI decides how it happens).
    Pure and synchronous: it never calls a tool itself, so the caller
    (ChatWorkflow) keeps full control of per-step event streaming.
    """

    def resolve_parameters(
        self, parameters: dict[str, Any], prior_outcomes: list[ToolExecutionOutcome]
    ) -> tuple[dict[str, Any] | None, str | None]:
        resolved: dict[str, Any] = {}
        for key, value in parameters.items():
            if not isinstance(value, str):
                resolved[key] = value
                continue
            match = _STEP_REFERENCE.match(value)
            if match is None:
                resolved[key] = value
                continue

            step_index = int(match.group(1))
            field = match.group(2)

            if step_index >= len(prior_outcomes):
                return None, f"Could not resolve {value}: step {step_index} does not exist"

            step_outcome = prior_outcomes[step_index]
            if step_outcome.status != "success" or step_outcome.result is None:
                return None, f"Could not resolve {value}: step {step_index} did not succeed"

            if field not in step_outcome.result:
                return (
                    None,
                    f"Could not resolve {value}: field '{field}' not found in step "
                    f"{step_index}'s result",
                )

            resolved[key] = step_outcome.result[field]

        return resolved, None
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_execution_planner.py -v`
Expected: PASS, all 7 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/orchestration/execution_planner.py backend/tests/test_execution_planner.py
git commit -m "feat: add ExecutionPlanner for \$stepN.field parameter piping

Pure, synchronous resolver - never calls a tool itself, so ChatWorkflow
keeps full control of per-step tool_call event streaming (Task 20).
A missing step, a failed step, or a missing field all produce a clear
error message rather than a silent None or a crash."
```

---

### Task 20: Wire `ExecutionPlanner` into `ChatWorkflow`

**Files:**
- Modify: `ai_platform/orchestration/chat_workflow.py`
- Modify: `backend/tests/test_chat_workflow.py`
- Modify: `backend/app/api/chat.py`
- Create: `backend/tests/test_execution_planner_integration.py`

**Interfaces:**
- Consumes: `ExecutionPlanner.resolve_parameters` (Task 19).
- Produces: `ChatWorkflow.__init__` gains a new required constructor
  argument, `execution_planner: ExecutionPlanner` (in addition to the
  existing `tool_executor: ToolExecutor` — both are needed, since
  `ExecutionPlanner` only resolves parameters and `ToolExecutor` still
  executes). Every existing `ChatWorkflow(...)` call site (production
  and tests) must pass it.

- [ ] **Step 1: Wire it into the workflow's execute loop**

Modify `ai_platform/orchestration/chat_workflow.py`:

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
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.orchestration.result_shaping import cap_result_for_prompt
from ai_platform.prompts.system_prompt import SYSTEM_PROMPT
from ai_platform.tool_registry.executor import ToolExecutionOutcome, ToolExecutor
from ai_platform.workflow.base import Workflow, WorkflowContext
from app.core.errors import ValidationError
from app.core.logging import conversation_id_ctx_var, workflow_ctx_var

logger = logging.getLogger("ai_platform.chat")
```

(only the `from ai_platform.orchestration.execution_planner import
ExecutionPlanner` line is new, added alphabetically before
`ai_platform.orchestration.planner`)

Modify the constructor:

```python
class ChatWorkflow(Workflow[ChatRequest, ChatEvent]):
    name = "chat"

    def __init__(
        self,
        repository: ConversationRepository,
        memory: ConversationMemory,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        planner: Planner,
        execution_planner: ExecutionPlanner,
        tool_executor: ToolExecutor,
        request_id: str | None,
    ) -> None:
        self._repository = repository
        self._memory = memory
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service
        self._planner = planner
        self._execution_planner = execution_planner
        self._tool_executor = tool_executor
        self._request_id = request_id
```

(only `execution_planner: ExecutionPlanner` and its assignment are new,
inserted between `planner` and `tool_executor`)

Modify the tool-call loop inside `execute`:

```python
            outcomes: list[ToolExecutionOutcome] = []
            for tool_call in plan.tool_calls or []:
                yield ChatEvent(type="tool_call", tool=tool_call.tool)
                resolved_parameters, resolution_error = (
                    self._execution_planner.resolve_parameters(tool_call.parameters, outcomes)
                )
                if resolution_error is not None:
                    outcomes.append(
                        ToolExecutionOutcome(
                            tool=tool_call.tool,
                            parameters=tool_call.parameters,
                            result=None,
                            status="error",
                            error_message=resolution_error,
                            duration_ms=0,
                        )
                    )
                    continue
                outcome = await self._tool_executor.execute(
                    request_id=self._request_id,
                    conversation_id=conversation_id,
                    tool=tool_call.tool,
                    parameters=resolved_parameters,
                )
                outcomes.append(outcome)
```

(replaces the previous loop body: the `yield ChatEvent(...)` line and the
final `outcomes.append(outcome)` are unchanged; everything about
resolving parameters and handling a resolution failure is new)

Everything else in `chat_workflow.py` — `_build_response_message`, the
rest of `execute`, `initialize`/`validate`/`log` — is unchanged.

- [ ] **Step 2: Update `test_chat_workflow.py`'s `_make_workflow` helper**

Modify `backend/tests/test_chat_workflow.py`:

```python
from ai_platform.orchestration.execution_planner import ExecutionPlanner
```

(add this import line, alongside the existing orchestration imports)

```python
def _make_workflow(
    db_session: AsyncSession,
    llm_service: FakeLLMService,
    extra_tools: list[ToolSpec] | None = None,
) -> tuple[ChatWorkflow, ConversationRepository, ToolExecutionRepository]:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    for tool in extra_tools or []:
        registry.register(tool)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    planner = Planner(llm_service, registry, prompt_builder)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id="req-test",
    )
    return workflow, repository, execution_repository
```

(only the import and the `execution_planner=ExecutionPlanner(),` line
are new; the rest of this helper is unchanged from Milestone 6)

- [ ] **Step 3: Update `chat.py`'s production wiring**

Modify `backend/app/api/chat.py`:

```python
from ai_platform.orchestration.execution_planner import ExecutionPlanner
```

(add this import line, alongside the existing orchestration imports)

```python
    repository = ConversationRepository(db)
    memory = ConversationMemory(repository)
    prompt_builder = PromptBuilder()
    execution_repository = ToolExecutionRepository(db)
    tool_executor = ToolExecutor(tool_registry, execution_repository, db)
    planner = Planner(llm_service, tool_registry, prompt_builder)
    workflow = ChatWorkflow(
        repository=repository,
        memory=memory,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=planner,
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id=request_id_ctx_var.get(),
    )
```

(only the `execution_planner=ExecutionPlanner(),` line is new)

- [ ] **Step 4: Run the existing chat workflow/eval/api test files to confirm nothing broke**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_workflow.py tests/test_chat_eval.py tests/test_chat_api.py -v`
Expected: FAIL at first — every other `_make_workflow`-style helper in
`test_chat_eval.py` and any direct `ChatWorkflow(...)` construction in
`test_chat_api.py` also needs the new `execution_planner=
ExecutionPlanner()` argument. Update `test_chat_eval.py`'s
`_make_workflow` the same way as Step 2 above (add the import, add
`execution_planner=ExecutionPlanner(),` to the `ChatWorkflow(...)` call).
Search `test_chat_api.py` for any `ChatWorkflow(` construction and apply
the same fix if found (it may only exercise the app's real `/api/chat`
route via HTTP, in which case Step 3's fix already covers it and no
change is needed here — check before editing).

- [ ] **Step 5: Re-run to confirm they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_workflow.py tests/test_chat_eval.py tests/test_chat_api.py -v`
Expected: PASS.

- [ ] **Step 6: Write the failing integration test for a dependent two-step plan**

Create `backend/tests/test_execution_planner_integration.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CUSTOMER_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id="piping-test-req",
    )


@pytest.mark.asyncio
async def test_dependent_two_step_plan_pipes_the_resolved_customer_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-7701", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7701", customer_id=customer.id, purchase_order_id=None,
        issue_date=None or __import__("datetime").date(2026, 1, 1),
        due_date=__import__("datetime").date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    llm_service = FakeLLMService(
        tokens=["Here you go."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "ABC Industries"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events: list[ChatEvent] = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="piping-session", message="ABC Industries' overdue invoices")
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer", "get_overdue_invoices"]

    assert llm_service.last_message is not None
    payload_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[1]
    import json as json_module

    payload = json_module.loads(payload_json)
    assert payload[0]["status"] == "success"
    assert payload[1]["status"] == "success"
    assert payload[1]["result"]["invoices"][0]["invoice_number"] == "INV-7701"


@pytest.mark.asyncio
async def test_unresolvable_reference_degrades_gracefully_without_aborting_the_plan(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["Here you go."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "Nonexistent Corp"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events: list[ChatEvent] = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="piping-session-2", message="Nonexistent Corp's overdue invoices")
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer", "get_overdue_invoices"]

    assert llm_service.last_message is not None
    payload_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[1]
    import json as json_module

    payload = json_module.loads(payload_json)
    assert payload[0]["status"] == "error"
    assert payload[1]["status"] == "error"
    assert "did not succeed" in payload[1]["error"]
```

(the `__import__("datetime")` calls in the first test are a deliberately
compact inline import to avoid a top-level `from datetime import date`
just for one field — if this reads awkwardly during implementation,
adding a normal `from datetime import date` import at the top of the
file and using `date(2026, 1, 1)`/`date(2026, 2, 1)` directly is
equally correct and preferred; both are shown here only because the
exact import style doesn't affect what's being tested)

- [ ] **Step 7: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_execution_planner_integration.py -v`
Expected: PASS, both tests — this is the milestone's own named
acceptance test ("Integration (mocked LLM): dependent two-step plan
executes correctly with parameter piping").

- [ ] **Step 8: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add ai_platform/orchestration/chat_workflow.py backend/tests/test_chat_workflow.py \
  backend/tests/test_chat_eval.py backend/app/api/chat.py \
  backend/tests/test_execution_planner_integration.py
git commit -m "feat: wire ExecutionPlanner's parameter piping into ChatWorkflow

ChatWorkflow's per-tool-call loop now resolves \$stepN.field references
before each execution, still emitting one tool_call event per step
(unchanged streaming behavior). An unresolvable reference produces a
categorized error outcome for that one step and the loop continues -
independent later steps still run, matching the project's existing
per-tool graceful-degradation philosophy."
```

---

### Task 21: `entity_extraction.py`

**Files:**
- Create: `ai_platform/memory/entity_extraction.py`
- Create: `backend/tests/test_entity_extraction.py`

**Interfaces:**
- Consumes: `MAX_LIST_ITEMS_IN_PROMPT` (`ai_platform.orchestration.
  result_shaping`, already exists, `Final[int] = 10`).
- Produces: `extract_entities(tool: str, result: dict[str, Any]) ->
  dict[str, list[str]]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_entity_extraction.py`:

```python
from __future__ import annotations

from ai_platform.memory.entity_extraction import extract_entities


def test_extract_entities_returns_empty_dict_for_an_unregistered_tool() -> None:
    assert extract_entities("get_current_date", {"date": "2026-07-08"}) == {}


def test_extract_entities_pulls_customer_names_and_invoice_numbers_from_a_list_tool() -> None:
    result = {
        "invoices": [
            {"invoice_number": "INV-7002", "customer_name": "Crestline Holdings"},
            {"invoice_number": "INV-7015", "customer_name": "Summit Components"},
        ],
        "summary": {"count": 2, "total_outstanding": "1000.00"},
    }

    entities = extract_entities("get_overdue_invoices", result)

    assert entities["customer_name"] == ["Crestline Holdings", "Summit Components"]
    assert entities["invoice_number"] == ["INV-7002", "INV-7015"]
    assert "summary" not in entities


def test_extract_entities_dedupes_repeated_customer_names() -> None:
    result = {
        "invoices": [
            {"invoice_number": "INV-1", "customer_name": "Acme Corp"},
            {"invoice_number": "INV-2", "customer_name": "Acme Corp"},
        ],
    }

    entities = extract_entities("get_unpaid_invoices", result)

    assert entities["customer_name"] == ["Acme Corp"]
    assert entities["invoice_number"] == ["INV-1", "INV-2"]


def test_extract_entities_caps_at_max_list_items_in_prompt() -> None:
    result = {"invoices": [{"invoice_number": f"INV-{i}", "customer_name": f"Customer {i}"}
                           for i in range(25)]}

    entities = extract_entities("search_invoices", result)

    assert len(entities["invoice_number"]) == 10
    assert len(entities["customer_name"]) == 10


def test_extract_entities_pulls_vendor_fields_from_get_vendor_invoices() -> None:
    result = {
        "invoices": [
            {"vendor_invoice_number": "VINV-4001", "vendor_name": "Beacon Logistics"},
        ],
    }

    entities = extract_entities("get_vendor_invoices", result)

    assert entities["vendor_name"] == ["Beacon Logistics"]
    assert entities["vendor_invoice_number"] == ["VINV-4001"]


def test_extract_entities_pulls_a_single_name_from_a_flat_balance_tool() -> None:
    result = {
        "customer_code": "CUST-0042", "customer_name": "ABC Industries",
        "total_outstanding": "1200.00", "unpaid_invoice_count": 3, "oldest_due_date": "2026-06-01",
    }

    entities = extract_entities("get_customer_balance", result)

    assert entities == {"customer_name": ["ABC Industries"]}


def test_extract_entities_returns_empty_dict_for_a_list_tool_with_no_rows() -> None:
    assert extract_entities("get_overdue_invoices", {"invoices": [], "summary": {"count": 0}}) == {}
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_entity_extraction.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'ai_platform.memory.entity_extraction'`.

- [ ] **Step 3: Implement**

Create `ai_platform/memory/entity_extraction.py`:

```python
from __future__ import annotations

from typing import Any

from ai_platform.orchestration.result_shaping import MAX_LIST_ITEMS_IN_PROMPT

# tool name -> (list field, name field, code field). Explicit and small on
# purpose: adding a new list-shaped tool means adding one entry here, never
# a generic "walk every string field" heuristic that would pull in noise
# (statuses, dates) as if they were entities.
_LIST_TOOL_ENTITY_FIELDS: dict[str, tuple[str, str, str]] = {
    "get_unpaid_invoices": ("invoices", "customer_name", "invoice_number"),
    "search_invoices": ("invoices", "customer_name", "invoice_number"),
    "get_overdue_invoices": ("invoices", "customer_name", "invoice_number"),
    "get_vendor_invoices": ("invoices", "vendor_name", "vendor_invoice_number"),
}

# tool name -> the one identifying name field on its flat result.
_FLAT_TOOL_ENTITY_FIELDS: dict[str, str] = {
    "get_customer_balance": "customer_name",
    "get_vendor_balance": "vendor_name",
    "get_customer": "customer_name",
}


def extract_entities(tool: str, result: dict[str, Any]) -> dict[str, list[str]]:
    """Pulls a small, explicit set of identifying business fields out of a
    tool's own result shape, for the next turn's compact memory summary.
    Never NLP, never keyword matching on the user's message - purely a
    lookup against each tool's already-known result shape.
    """
    if tool in _LIST_TOOL_ENTITY_FIELDS:
        list_field, name_field, code_field = _LIST_TOOL_ENTITY_FIELDS[tool]
        items = result.get(list_field) or []
        names = _dedupe_capped(item.get(name_field) for item in items)
        codes = _dedupe_capped(item.get(code_field) for item in items)
        entities: dict[str, list[str]] = {}
        if names:
            entities[name_field] = names
        if codes:
            entities[code_field] = codes
        return entities

    if tool in _FLAT_TOOL_ENTITY_FIELDS:
        field = _FLAT_TOOL_ENTITY_FIELDS[tool]
        value = result.get(field)
        return {field: [value]} if value else {}

    return {}


def _dedupe_capped(values: Any) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.append(value)
        if len(seen) >= MAX_LIST_ITEMS_IN_PROMPT:
            break
    return seen
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_entity_extraction.py -v`
Expected: PASS, all 7 tests.

- [ ] **Step 5: Run lint/type checks**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/memory/entity_extraction.py backend/tests/test_entity_extraction.py
git commit -m "feat: add extract_entities for compact per-turn memory summaries

Explicit per-tool-shape mapping - a new list/flat tool needs one new
entry here, never a generic heuristic. Capped at MAX_LIST_ITEMS_IN_PROMPT
(same constant Milestone 6's payload cap uses) so a large result can't
blow up the next turn's planning prompt either."
```

---

### Task 22: `turn_summaries` table + `ConversationRepository` methods

**Files:**
- Create: `backend/alembic/versions/<REV3>_create_turn_summaries_table.py`
- Modify: `ai_platform/memory/models.py`
- Modify: `ai_platform/memory/repository.py`
- Create: `backend/tests/test_turn_summary_repository.py`

**Interfaces:**
- Produces: `TurnSummaryModel` (`__tablename__ = "turn_summaries"`,
  schema `application`), `ConversationRepository.record_turn_summary(
  conversation_id: uuid.UUID, *, tool_calls: list[dict[str, Any]],
  entities: dict[str, list[str]]) -> TurnSummaryModel`,
  `ConversationRepository.list_recent_turn_summaries(conversation_id:
  uuid.UUID, limit: int = 2) -> list[TurnSummaryModel]` (most recent
  first).

- [ ] **Step 1: Write the migration**

Run `cd backend && .venv/Scripts/python -m alembic revision -m "create turn_summaries table"`
(call the printed id `<REV3>` — its `down_revision` must be `<REV2>` from
Task 2). Replace the generated file's body with:

```python
"""create turn_summaries table

Revision ID: <REV3>
Revises: <REV2>
Create Date: <alembic's own timestamp>

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '<REV3>'
down_revision: str | Sequence[str] | None = '<REV2>'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "turn_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"), nullable=False,
        ),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False),
        sa.Column("entities", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_turn_summaries_conversation_id", "conversation_id"),
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("turn_summaries", schema="application")
```

- [ ] **Step 2: Write the ORM model**

Modify `ai_platform/memory/models.py` — add the import and the new model
class:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "application"
```

(only `from typing import Any` and `JSONB` in the `sqlalchemy.dialects.
postgresql` import are new)

Add at the end of the file, after `MessageModel`:

```python
class TurnSummaryModel(Base):
    __tablename__ = "turn_summaries"
    __table_args__ = (
        Index("ix_turn_summaries_conversation_id", "conversation_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    entities: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: Apply the migration**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: no errors; `alembic current` shows `<REV3> (head)`.

Round-trip check: `.venv/Scripts/python -m alembic downgrade -1` then
`.venv/Scripts/python -m alembic upgrade head` — both succeed.

- [ ] **Step 4: Write the failing repository tests**

Create `backend/tests/test_turn_summary_repository.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_record_turn_summary_and_list_recent(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-1")
    conversation = await repo.create_conversation("session-turn-1")

    await repo.record_turn_summary(
        conversation.id,
        tool_calls=[{"tool": "get_overdue_invoices", "parameters": {}}],
        entities={"customer_name": ["Crestline Holdings"], "invoice_number": ["INV-7002"]},
    )
    await db_session.commit()

    summaries = await repo.list_recent_turn_summaries(conversation.id)
    assert len(summaries) == 1
    assert summaries[0].tool_calls == [{"tool": "get_overdue_invoices", "parameters": {}}]
    assert summaries[0].entities["customer_name"] == ["Crestline Holdings"]


@pytest.mark.asyncio
async def test_list_recent_turn_summaries_returns_most_recent_first_and_respects_limit(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-2")
    conversation = await repo.create_conversation("session-turn-2")

    for i in range(4):
        await repo.record_turn_summary(
            conversation.id,
            tool_calls=[{"tool": f"tool_{i}", "parameters": {}}],
            entities={},
        )
    await db_session.commit()

    summaries = await repo.list_recent_turn_summaries(conversation.id, limit=2)
    assert [s.tool_calls[0]["tool"] for s in summaries] == ["tool_3", "tool_2"]


@pytest.mark.asyncio
async def test_list_recent_turn_summaries_returns_empty_for_a_fresh_conversation(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-3")
    conversation = await repo.create_conversation("session-turn-3")
    await db_session.commit()

    assert await repo.list_recent_turn_summaries(conversation.id) == []
```

- [ ] **Step 5: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_turn_summary_repository.py -v`
Expected: FAIL — `AttributeError: 'ConversationRepository' object has no
attribute 'record_turn_summary'`.

- [ ] **Step 6: Implement the repository methods**

Modify `ai_platform/memory/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.models import ConversationModel, MessageModel, SessionModel, TurnSummaryModel

TITLE_MAX_LENGTH = 50
```

(only `from typing import Any` and `TurnSummaryModel` in the models
import are new)

Add at the end of `ConversationRepository`, after `get_messages`:

```python
    async def record_turn_summary(
        self,
        conversation_id: uuid.UUID,
        *,
        tool_calls: list[dict[str, Any]],
        entities: dict[str, list[str]],
    ) -> TurnSummaryModel:
        summary = TurnSummaryModel(
            id=uuid.uuid4(), conversation_id=conversation_id,
            tool_calls=tool_calls, entities=entities,
        )
        self._db.add(summary)
        await self._db.flush()
        return summary

    async def list_recent_turn_summaries(
        self, conversation_id: uuid.UUID, limit: int = 2
    ) -> list[TurnSummaryModel]:
        stmt = (
            select(TurnSummaryModel)
            .where(TurnSummaryModel.conversation_id == conversation_id)
            .order_by(TurnSummaryModel.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 7: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_turn_summary_repository.py -v`
Expected: PASS, all 3 tests.

- [ ] **Step 8: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/ ai_platform/memory/models.py ai_platform/memory/repository.py \
  backend/tests/test_turn_summary_repository.py
git commit -m "feat: add turn_summaries table and ConversationRepository methods

One row per assistant turn that called tools: the tool+parameters
actually used (post-piping) plus a small entities dict from
extract_entities. Pure data access - no business meaning, no LLM call."
```

---

### Task 23: `ConversationMemory.get_recent_turn_summaries`

**Files:**
- Modify: `ai_platform/memory/conversation_memory.py`
- Modify: `backend/tests/test_conversation_memory.py`

**Interfaces:**
- Consumes: `ConversationRepository.list_recent_turn_summaries` (Task 22).
- Produces: `TurnSummary` frozen dataclass (`tool_calls:
  list[dict[str, Any]], entities: dict[str, list[str]]`),
  `ConversationMemory.get_recent_turn_summaries(conversation_id:
  uuid.UUID, limit: int = 2) -> list[TurnSummary]` (most recent first,
  same order as the repository).

- [ ] **Step 1: Write the failing tests**

Read `backend/tests/test_conversation_memory.py` first to match its
existing fixture style (it already tests `get_context_window` against a
real `ConversationRepository`/`db_session`). Add:

```python
@pytest.mark.asyncio
async def test_get_recent_turn_summaries_returns_most_recent_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    await repository.get_or_create_session("session-memory-turns")
    conversation = await repository.create_conversation("session-memory-turns")
    await repository.record_turn_summary(
        conversation.id, tool_calls=[{"tool": "get_unpaid_invoices", "parameters": {}}],
        entities={},
    )
    await repository.record_turn_summary(
        conversation.id,
        tool_calls=[{"tool": "get_overdue_invoices", "parameters": {"minimum_days": 30}}],
        entities={"customer_name": ["Crestline Holdings"]},
    )
    await db_session.commit()

    summaries = await memory.get_recent_turn_summaries(conversation.id)

    assert len(summaries) == 2
    assert isinstance(summaries[0], TurnSummary)
    assert summaries[0].tool_calls[0]["tool"] == "get_overdue_invoices"
    assert summaries[0].entities["customer_name"] == ["Crestline Holdings"]
    assert summaries[1].tool_calls[0]["tool"] == "get_unpaid_invoices"


@pytest.mark.asyncio
async def test_get_recent_turn_summaries_empty_for_a_fresh_conversation(
    clean_db: None, db_session: AsyncSession
) -> None:
    repository = ConversationRepository(db_session)
    memory = ConversationMemory(repository)
    await repository.get_or_create_session("session-memory-turns-2")
    conversation = await repository.create_conversation("session-memory-turns-2")
    await db_session.commit()

    assert await memory.get_recent_turn_summaries(conversation.id) == []
```

(add `TurnSummary` to whatever import line already pulls
`ConversationMemory`/`HistoryMessage` from
`ai_platform.memory.conversation_memory`)

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_conversation_memory.py -v`
Expected: FAIL — `ImportError: cannot import name 'TurnSummary'`.

- [ ] **Step 3: Implement**

Modify `ai_platform/memory/conversation_memory.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ai_platform.memory.repository import ConversationRepository

MAX_HISTORY_MESSAGES = 10
DEFAULT_TURN_SUMMARY_LIMIT = 2


@dataclass(frozen=True)
class HistoryMessage:
    """A (role, content) pair ready to hand to an LLM prompt.

    This is the seam a future milestone can use to swap recency-based
    retrieval for something smarter (embeddings, relevance ranking)
    without changing `PromptBuilder` or `ChatWorkflow`.
    """

    role: str
    content: str


@dataclass(frozen=True)
class TurnSummary:
    """A compact, mechanically-derived record of one prior turn's tool
    activity - what tool(s) ran, with what parameters, and which business
    entities (customer/vendor names and codes, invoice numbers) appeared
    in their results. Lets the planner resolve a follow-up like "which of
    those belong to ABC Industries?" without re-sending the full,
    potentially large, prior tool result.
    """

    tool_calls: list[dict[str, Any]]
    entities: dict[str, list[str]]


class ConversationMemory:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def get_context_window(self, conversation_id: uuid.UUID) -> list[HistoryMessage]:
        messages = await self._repository.get_messages(conversation_id)
        recent = messages[-MAX_HISTORY_MESSAGES:]
        return [HistoryMessage(role=m.role, content=m.content) for m in recent]

    async def get_recent_turn_summaries(
        self, conversation_id: uuid.UUID, limit: int = DEFAULT_TURN_SUMMARY_LIMIT
    ) -> list[TurnSummary]:
        summaries = await self._repository.list_recent_turn_summaries(conversation_id, limit)
        return [TurnSummary(tool_calls=s.tool_calls, entities=s.entities) for s in summaries]
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_conversation_memory.py -v`
Expected: PASS, including every pre-existing test in the file.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/memory/conversation_memory.py backend/tests/test_conversation_memory.py
git commit -m "feat: add ConversationMemory.get_recent_turn_summaries

TurnSummary mirrors HistoryMessage's decoupling pattern - a plain
dataclass distinct from the ORM model, giving PromptBuilder/Planner a
stable shape independent of how turn summaries are stored."
```

---

### Task 24: Wire turn-summary retrieval and population end-to-end

**Files:**
- Modify: `ai_platform/orchestration/planner.py`
- Modify: `ai_platform/prompts/planning_prompt.py`
- Modify: `ai_platform/orchestration/chat_workflow.py`
- Modify: `backend/tests/test_planner.py`
- Modify: `backend/tests/test_planning_prompt.py`
- Create: `backend/tests/test_turn_summary_memory_integration.py`

**Interfaces:**
- Consumes: `ConversationMemory.get_recent_turn_summaries` (Task 23),
  `extract_entities` (Task 21), `ConversationRepository.
  record_turn_summary` (Task 22).
- Produces: `build_planning_prompt(tools_json: str, recent_activity: str
  = "") -> str` (new optional second parameter, backward compatible —
  every existing single-argument call site is unaffected),
  `Planner.create_plan(history, message, recent_turn_summaries:
  list[TurnSummary] | None = None) -> Plan` (new optional third
  parameter). `ChatWorkflow.execute` fetches recent turn summaries before
  planning and records a new one after tool execution (only when at
  least one tool call succeeded).

This task wires the *mechanism* only — it doesn't yet teach the planning
prompt how to use the rendered activity block in its Rules section
(that's Task 25's version-bump content change). A prompt with an empty
Rules-section reference to "recent tool activity" but a populated data
block is intentionally fine for this task's own tests (which assert the
block's *presence*, not that a real LLM acts on it yet).

- [ ] **Step 1: Write the failing prompt-rendering test**

Read `backend/tests/test_planning_prompt.py` first. Add:

```python
def test_build_planning_prompt_with_no_recent_activity_is_unchanged() -> None:
    with_default = build_planning_prompt('[{"name": "get_current_date"}]')
    with_explicit_empty = build_planning_prompt('[{"name": "get_current_date"}]', "")
    assert with_default == with_explicit_empty


def test_build_planning_prompt_includes_recent_activity_when_provided() -> None:
    prompt = build_planning_prompt(
        '[{"name": "get_current_date"}]',
        "Recent tool activity:\n- get_overdue_invoices(minimum_days=30) -> "
        "customer_name: ['Crestline Holdings']",
    )
    assert "Recent tool activity:" in prompt
    assert "Crestline Holdings" in prompt
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: FAIL — `TypeError: build_planning_prompt() takes 1 positional
argument but 2 were given`.

- [ ] **Step 3: Add the optional parameter to `build_planning_prompt`**

Modify `ai_platform/prompts/planning_prompt.py` — only the function at
the bottom of the file changes:

```python
def build_planning_prompt(tools_json: str, recent_activity: str = "") -> str:
    prompt = PLANNING_SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
    if recent_activity:
        prompt = f"{prompt}\n{recent_activity}\n"
    return prompt
```

(everything above this function — `VERSION`, `CHANGELOG`,
`PLANNING_SYSTEM_PROMPT_TEMPLATE` itself — is unchanged this task; Task
25 bumps those)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: PASS, including every pre-existing test in the file.

- [ ] **Step 5: Write the failing `Planner.create_plan` test**

Read `backend/tests/test_planner.py`'s existing fixtures again. Add:

```python
@pytest.mark.asyncio
async def test_create_plan_renders_recent_turn_summaries_into_the_prompt() -> None:
    llm_service = FakeLLMService(tokens=["unused"], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())
    summaries = [
        TurnSummary(
            tool_calls=[{"tool": "get_overdue_invoices", "parameters": {"minimum_days": 30}}],
            entities={"customer_name": ["Crestline Holdings"]},
        )
    ]

    await planner.create_plan([], "anything", summaries)

    assert llm_service.last_complete_system is not None
    assert "get_overdue_invoices" in llm_service.last_complete_system
    assert "Crestline Holdings" in llm_service.last_complete_system


@pytest.mark.asyncio
async def test_create_plan_with_no_recent_turn_summaries_omits_the_activity_block() -> None:
    llm_service = FakeLLMService(tokens=["unused"], plan_response='{"direct_answer": true}')
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    planner = Planner(llm_service, registry, PromptBuilder())

    await planner.create_plan([], "anything")

    assert llm_service.last_complete_system is not None
    assert "Recent tool activity" not in llm_service.last_complete_system
```

(add `TurnSummary` to the import line pulling from
`ai_platform.memory.conversation_memory`, alongside whatever's already
imported there)

- [ ] **Step 6: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planner.py -v`
Expected: FAIL — `TypeError: Planner.create_plan() takes 3 positional
arguments but 4 were given`.

- [ ] **Step 7: Implement `create_plan`'s new parameter and rendering**

Modify `ai_platform/orchestration/planner.py`:

```python
from __future__ import annotations

import json
from typing import Any, Final

from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from ai_platform.llm.service import LLMService
from ai_platform.memory.conversation_memory import HistoryMessage, TurnSummary
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.prompts.planning_prompt import build_planning_prompt
from ai_platform.tool_registry.registry import ToolRegistry
from app.core.errors import AIError
```

(only `TurnSummary` in the `ai_platform.memory.conversation_memory`
import is new)

Add a rendering helper right after `_strip_code_fences`:

```python
def _render_recent_activity(summaries: list[TurnSummary]) -> str:
    if not summaries:
        return ""
    lines = ["Recent tool activity:"]
    for summary in reversed(summaries):
        calls = ", ".join(
            f"{call['tool']}({', '.join(f'{k}={v!r}' for k, v in call['parameters'].items())})"
            for call in summary.tool_calls
        )
        if summary.entities:
            entity_parts = [f"{key}: {values}" for key, values in summary.entities.items()]
            entities_text = "; ".join(entity_parts)
        else:
            entities_text = "no entities"
        lines.append(f"- {calls} -> {entities_text}")
    return "\n".join(lines)
```

Modify `create_plan`:

```python
    async def create_plan(
        self,
        history: list[HistoryMessage],
        message: str,
        recent_turn_summaries: list[TurnSummary] | None = None,
    ) -> Plan:
        tools_json = json.dumps(self._registry.to_planner_json(), indent=2)
        recent_activity = _render_recent_activity(recent_turn_summaries or [])
        system = build_planning_prompt(tools_json, recent_activity)
        prompt = self._prompt_builder.build(system, history)
        raw = await self._llm_service.complete(prompt.system, prompt.messages, message)
        cleaned = _strip_code_fences(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc

        raw_tool_calls = data.get("tool_calls") if isinstance(data, dict) else None
        if isinstance(raw_tool_calls, list) and len(raw_tool_calls) > MAX_TOOL_CALLS_PER_PLAN:
            return Plan(clarification_needed=TOO_MANY_TOOL_CALLS_MESSAGE)

        try:
            return Plan.model_validate(data)
        except PydanticValidationError as exc:
            raise AIError(
                "I had trouble figuring out how to answer that. Please try rephrasing."
            ) from exc
```

(only the new `recent_turn_summaries` parameter and the
`recent_activity = _render_recent_activity(...)`/`build_planning_prompt(
tools_json, recent_activity)` lines change; the rest of the method body
is identical to Task 18's version)

- [ ] **Step 8: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planner.py -v`
Expected: PASS, including every pre-existing test.

- [ ] **Step 9: Wire retrieval and population into `ChatWorkflow`**

Modify `ai_platform/orchestration/chat_workflow.py`:

```python
from ai_platform.memory.entity_extraction import extract_entities
```

(add this import line, alongside the existing `ai_platform.memory.*`
imports, alphabetically before `ai_platform.memory.repository`)

Modify `execute`'s body — the history/memory retrieval block:

```python
            history = await self._memory.get_context_window(conversation_id)
            recent_turn_summaries = await self._memory.get_recent_turn_summaries(conversation_id)
            await self._repository.add_message(conversation_id, "user", input_data.message)

            plan = await self._planner.create_plan(history, input_data.message, recent_turn_summaries)
```

(only the `recent_turn_summaries = ...` line and passing it as
`create_plan`'s third argument are new)

Add the population step right after the tool-call loop, before building
the Phase-2 message:

```python
            successful_tool_calls = [
                {"tool": outcome.tool, "parameters": outcome.parameters}
                for outcome in outcomes
                if outcome.status == "success"
            ]
            if successful_tool_calls:
                merged_entities: dict[str, list[str]] = {}
                for outcome in outcomes:
                    if outcome.status != "success" or outcome.result is None:
                        continue
                    for key, values in extract_entities(outcome.tool, outcome.result).items():
                        bucket = merged_entities.setdefault(key, [])
                        for value in values:
                            if value not in bucket:
                                bucket.append(value)
                await self._repository.record_turn_summary(
                    conversation_id, tool_calls=successful_tool_calls, entities=merged_entities
                )

            prompt = self._prompt_builder.build(SYSTEM_PROMPT, history)
```

(everything from `successful_tool_calls = [...]` through the
`record_turn_summary` call is new, inserted between the existing
tool-call loop and the existing `prompt = self._prompt_builder.build(...)`
line — that line itself, and everything after it, is unchanged)

- [ ] **Step 10: Write the failing end-to-end integration test**

Create `backend/tests/test_turn_summary_memory_integration.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id="turn-summary-test-req",
    )


@pytest.mark.asyncio
async def test_second_turns_planning_prompt_sees_the_first_turns_tool_activity(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-7801", company_name="Crestline Holdings", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7801", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    llm_service = FakeLLMService(
        tokens=["Here are the overdue invoices."],
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    conversation_id: str | None = None
    async for event in workflow.run(
        ChatRequest(session_id="turn-summary-session", message="Show overdue invoices")
    ):
        if event.type == "done":
            conversation_id = event.conversation_id
    await db_session.commit()
    assert conversation_id is not None

    llm_service_2 = FakeLLMService(
        tokens=["Just that one."],
        plan_response='{"direct_answer": true}',
    )
    workflow_2 = _make_workflow(db_session, llm_service_2)
    async for _ in workflow_2.run(
        ChatRequest(
            session_id="turn-summary-session",
            message="Which of those belong to Crestline Holdings?",
            conversation_id=conversation_id,
        )
    ):
        pass
    await db_session.commit()

    assert llm_service_2.last_complete_system is not None
    assert "get_overdue_invoices" in llm_service_2.last_complete_system
    assert "Crestline Holdings" in llm_service_2.last_complete_system
    assert "INV-7801" in llm_service_2.last_complete_system
```

- [ ] **Step 11: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_turn_summary_memory_integration.py -v`
Expected: PASS — proves the full retrieval-render-populate loop end to
end against real Postgres.

- [ ] **Step 12: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 13: Commit**

```bash
git add ai_platform/orchestration/planner.py ai_platform/prompts/planning_prompt.py \
  ai_platform/orchestration/chat_workflow.py backend/tests/test_planner.py \
  backend/tests/test_planning_prompt.py backend/tests/test_turn_summary_memory_integration.py
git commit -m "feat: wire turn-summary retrieval and population end-to-end

ChatWorkflow fetches the last 2 turn summaries before planning and
passes them to Planner.create_plan, which renders them into a compact
'Recent tool activity' block in the planning prompt. After tool
execution, a new turn summary is recorded (successful calls only, plus
deduplicated entities from extract_entities) - only when at least one
tool call succeeded. This is the mechanism only; Task 25 teaches the
prompt's Rules section how to use it for follow-up resolution."
```

---

### Task 25: Bump the planning prompt to 1.3.0

**Files:**
- Modify: `ai_platform/prompts/planning_prompt.py`
- Modify: `backend/tests/test_planning_prompt.py`

**Interfaces:**
- Consumes: nothing new — this task teaches the LLM to use mechanisms
  Tasks 18-24 already built (piping syntax, the 5-call cap, the
  reasoning-query pattern, `get_customer`).
- Produces: `planning_prompt.VERSION == "1.3.0"`, extended
  `PLANNING_SYSTEM_PROMPT_TEMPLATE` Rules section.

- [ ] **Step 1: Write the failing prompt tests**

Modify `backend/tests/test_planning_prompt.py`:

```python
def test_planning_prompt_is_versioned() -> None:
    assert VERSION == "1.3.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 4
```

(update the existing `test_planning_prompt_is_versioned` test's expected
version and changelog length — everything else in the file from Task 24
is unchanged)

Add at the end of the file:

```python
def test_build_planning_prompt_teaches_parameter_piping_syntax() -> None:
    prompt = build_planning_prompt("[]")
    assert "$step0.customer_code" in prompt
    assert "get_customer" in prompt


def test_build_planning_prompt_states_the_five_tool_call_cap() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "5 tool calls" in prompt


def test_build_planning_prompt_teaches_the_reasoning_query_pattern() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "get_vendor_invoices" in prompt
    assert "get_cash_position" in prompt
    assert "which invoices should i pay first" in prompt


def test_build_planning_prompt_disambiguates_get_customer_from_get_customer_balance() -> None:
    prompt = build_planning_prompt("[]").lower()
    assert "get_customer" in prompt
    assert "get_customer_balance" in prompt
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: FAIL — `VERSION == "1.3.0"` fails (still `"1.2.0"`), and the
four new phrase-presence tests fail.

- [ ] **Step 3: Bump the planning prompt**

Modify `ai_platform/prompts/planning_prompt.py`:

```python
"""Versioned system prompt for the Phase 1 planner.

Version: 1.3.0
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
  - 1.2.0 (2026-07-11): Milestone 6 adds four tools (search_invoices,
    get_overdue_invoices, get_customer_balance, get_vendor_balance).
    Teaches paraphrase invariance for each, and adds an explicit
    disambiguation rule between get_unpaid_invoices and
    get_overdue_invoices, since both can plausibly describe "who owes
    money" style requests.
  - 1.3.0 (2026-07-12): Milestone 7 teaches multi-step plans: the
    "$stepN.field" parameter-piping syntax (with a worked
    get_customer -> get_overdue_invoices example resolving a company
    name to a business code before scoping a follow-up), the 5-tool-call
    cap, the reasoning-query pattern (plan get_vendor_invoices and
    get_cash_position together, no piping, for "which invoices should I
    pay first?" style questions), and a disambiguation rule between the
    new get_customer (pure code lookup) and get_customer_balance
    (computes a balance).
"""

from __future__ import annotations

VERSION = "1.3.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-07): Initial version - three-branch planning contract "
    "(clarification_needed / tool_calls / direct_answer).",
    "1.1.0 (2026-07-10): Add a paraphrase-invariance rule with a worked "
    "accounts-receivable example (get_unpaid_invoices).",
    "1.2.0 (2026-07-11): Add search_invoices/get_overdue_invoices/"
    "get_customer_balance/get_vendor_balance paraphrase examples and an "
    "unpaid-vs-overdue disambiguation rule.",
    "1.3.0 (2026-07-12): Teach multi-step plans - $stepN.field parameter "
    "piping (worked get_customer -> get_overdue_invoices example), the "
    "5-tool-call cap, the get_vendor_invoices + get_cash_position "
    "reasoning-query pattern, and a get_customer-vs-get_customer_balance "
    "disambiguation rule.",
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
    "retrieval capability (get_unpaid_invoices), even though none of the "
    "words match each other.\n"
    "- 'Who owes us money', 'unpaid invoices', or 'outstanding invoices' "
    "(no specific day threshold) means get_unpaid_invoices - it covers "
    "every unpaid status (sent, partially_paid, overdue). Only use "
    "get_overdue_invoices when the request is specifically about invoices "
    "past their due date, especially when the user gives a day threshold "
    "(e.g. 'overdue by more than 30 days') or explicitly says "
    "'overdue'/'past due' rather than just 'unpaid'/'outstanding'.\n"
    "- All of 'Find invoice INV-1045' and 'Show invoice INV-1045' select "
    "search_invoices with invoice_number set - search_invoices is also "
    "the right choice for any filtered invoice lookup by status, amount "
    "range, or due-date range that isn't specifically 'unpaid' or "
    "'overdue'.\n"
    "- All of 'How much does ABC Industries owe us?' and \"What's ABC "
    "Industries' balance?\" select get_customer_balance with "
    "customer_name='ABC Industries' - use the company name exactly as the "
    "user said it, not a business code.\n"
    "- All of 'What do we owe Summit Traders?' and \"What's our balance "
    "with Summit Traders?\" select get_vendor_balance with "
    "vendor_name='Summit Traders' - same naming rule as "
    "get_customer_balance.\n"
    "- A plan may include more than one tool call, in order, and a later "
    "call's parameter value may reference an earlier call's result with "
    "the exact string \"$stepN.field\" (N is the 0-based index into this "
    "same tool_calls list, field is a field name from that step's result). "
    "Use this whenever a later tool needs a business code (e.g. "
    "customer_id) but the user only gave a plain-English name, and no "
    "other tool call already produced that code this turn. Worked "
    "example - 'Which of those belong to ABC Industries?' after a prior "
    "invoices list, where ABC Industries hasn't been resolved to a code "
    "yet: "
    '{{"tool_calls": [{{"tool": "get_customer", "parameters": '
    '{{"customer_name": "ABC Industries"}}}}, {{"tool": '
    '"get_overdue_invoices", "parameters": {{"customer_id": '
    '"$step0.customer_code"}}}}]}}. '
    "Carry forward any filter the user already applied in a prior turn "
    "(e.g. a day threshold) alongside the new scope, using the recent "
    "tool activity shown above the tool list, when present.\n"
    "- Plan at most 5 tool calls in one tool_calls list. If a request "
    "would genuinely need more than 5, ask a clarifying question instead "
    "of planning a longer list.\n"
    "- 'Which invoices should I pay first?', 'What should we pay now?', "
    "or any question weighing what to pay against available money has no "
    "single tool that answers it - plan get_vendor_invoices and "
    "get_cash_position together (they don't depend on each other, so no "
    "$stepN.field piping is needed) so the response stage can reason over "
    "both together.\n"
    "- When a later step only needs a customer's business code (not their "
    "balance), select get_customer - not get_customer_balance, which "
    "computes an unpaid-invoice balance nobody asked for in that step.\n"
    "- Output ONLY the JSON object. No explanation, no markdown fences, "
    "no extra text.\n"
)


def build_planning_prompt(tools_json: str, recent_activity: str = "") -> str:
    prompt = PLANNING_SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
    if recent_activity:
        prompt = f"{prompt}\n{recent_activity}\n"
    return prompt
```

(only the Rules section gains the four new bullet points above the
existing "Output ONLY the JSON object" line; `build_planning_prompt`
itself is unchanged from Task 24)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_planning_prompt.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/prompts/planning_prompt.py backend/tests/test_planning_prompt.py
git commit -m "feat: bump planning prompt to 1.3.0 for multi-tool reasoning

Teaches \$stepN.field parameter piping with a worked get_customer ->
get_overdue_invoices example, the 5-tool-call cap, the
get_vendor_invoices + get_cash_position reasoning-query pattern, and a
get_customer-vs-get_customer_balance disambiguation rule - keeping all
intent routing in the prompt/LLM layer per CLAUDE.md."
```

---

### Task 26: Bump the system (Phase 2) prompt to 1.4.0

**Files:**
- Modify: `ai_platform/prompts/system_prompt.py`
- Modify: `backend/tests/test_system_prompt.py`

**Interfaces:**
- Produces: `system_prompt.VERSION == "1.4.0"`, extended
  `SYSTEM_PROMPT` with a reasoning-grounding instruction for turns where
  multiple tool results are present together.

- [ ] **Step 1: Write the failing prompt tests**

Read `backend/tests/test_system_prompt.py` first (it already tests
`VERSION`, `AUTHOR`, `CHANGELOG` length, and several substring
assertions on `SYSTEM_PROMPT` from Milestones 5-6). Update the version
test:

```python
def test_system_prompt_is_versioned() -> None:
    assert VERSION == "1.4.0"
    assert AUTHOR
    assert len(CHANGELOG) >= 5
```

Add at the end of the file:

```python
def test_system_prompt_instructs_grounding_when_reasoning_over_combined_results() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "more than one tool result" in lowered or "multiple tool results" in lowered
    assert "recommend" in lowered or "priorit" in lowered
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_system_prompt.py -v`
Expected: FAIL — `VERSION == "1.4.0"` fails (still `"1.3.0"`), and the
new instruction-presence test fails.

- [ ] **Step 3: Bump the system prompt**

Modify `ai_platform/prompts/system_prompt.py`:

```python
"""Versioned system prompt for the general chat assistant.

Version: 1.4.0
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
  - 1.3.0 (2026-07-11): Milestone 6 caps large list-shaped tool results
    before they reach this prompt (top 10 by materiality/urgency, see
    result_shaping.py). Instructs the model to say so and quote the
    result's summary block for true totals whenever a result is marked
    truncated, rather than only summing the rows shown.
  - 1.4.0 (2026-07-12): Milestone 7 adds multi-tool reasoning questions
    (e.g. "which invoices should I pay first?") where more than one tool
    result is provided together with no single answer already computed.
    Instructs the model to ground every ranking/recommendation strictly
    in the provided figures and never state or compute a number absent
    from them, reinforcing the existing hallucination-prevention rule
    for this specific, higher-stakes case.
"""

from __future__ import annotations

VERSION = "1.4.0"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-05): Initial version - general chat persona, no tools.",
    "1.1.0 (2026-07-07): Add tool-result grounding instruction now that "
    "get_current_date() can supply real tool output.",
    "1.2.0 (2026-07-10): Instruct the model to render list-shaped tool "
    "results (e.g. unpaid invoices) as markdown tables now that "
    "get_unpaid_invoices exists and the frontend can render them.",
    "1.3.0 (2026-07-11): Instruct the model to acknowledge truncated tool "
    "results and quote the summary block's true totals, now that large "
    "result sets are capped before reaching this prompt.",
    "1.4.0 (2026-07-12): Instruct the model to ground reasoning/"
    "recommendation answers (e.g. payment prioritization) strictly in the "
    "figures present across all provided tool results, never inventing or "
    "computing a number that isn't already there, now that a turn can "
    "carry more than one tool result with no single tool answering the "
    "question.",
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
    "list as prose. "
    "If a tool result includes \"_truncated\": true, tell the user you're "
    "showing only the top records (by materiality or urgency) out of the "
    "total count, and give the true overall totals from the result's "
    "summary block rather than only summing the rows shown. "
    "When more than one tool result is provided together for a question "
    "with no single tool answer (e.g. ranking or recommending which "
    "invoices to pay first), reason across all of them but ground every "
    "comparison, ranking, or recommendation strictly in the figures "
    "actually present - due dates, amounts, balances, cash figures - and "
    "explain the reasoning using those figures; never state or compute a "
    "number that isn't already present in the provided results."
)
```

(only the version/changelog header and the final new sentence of
`SYSTEM_PROMPT` are new; every line before it is unchanged from
Milestone 6)

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_system_prompt.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add ai_platform/prompts/system_prompt.py backend/tests/test_system_prompt.py
git commit -m "feat: bump system prompt to 1.4.0 for multi-tool reasoning grounding

Instructs Phase 2 to ground every ranking/recommendation strictly in
the figures present across all provided tool results when a turn
carries more than one, and never invent or compute a number that isn't
already there - the concrete hallucination-prevention requirement for
'which invoices should I pay first?' style questions."
```

---

### Task 27: AI eval test — the "those" follow-up scenario

**Files:**
- Modify: `backend/tests/test_chat_eval.py`

**Interfaces:**
- Consumes: `GET_CASH_POSITION_TOOL`, `GET_VENDOR_INVOICES_TOOL`,
  `GET_CUSTOMER_TOOL` (Tasks 12/14/16), `ExecutionPlanner` (Task 19).

- [ ] **Step 1: Register the three new Phase A tools in `_make_workflow`**

Modify `backend/tests/test_chat_eval.py`:

```python
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_cash_position import GET_CASH_POSITION_TOOL
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.get_vendor_balance import GET_VENDOR_BALANCE_TOOL
from domains.finance.tools.get_vendor_invoices import GET_VENDOR_INVOICES_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    registry.register(GET_VENDOR_BALANCE_TOOL)
    registry.register(GET_CASH_POSITION_TOOL)
    registry.register(GET_VENDOR_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id="eval-req",
    )
```

(only the `ExecutionPlanner` import, the three new tool imports
`GET_CASH_POSITION_TOOL`/`GET_CUSTOMER_TOOL`/`GET_VENDOR_INVOICES_TOOL`,
their three `registry.register(...)` calls, and the
`execution_planner=ExecutionPlanner(),` line are new — every other
pre-existing test in this file that calls `_make_workflow` is otherwise
unaffected, since it's the same helper with a wider tool set)

- [ ] **Step 2: Run the full file to confirm every pre-existing test still passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_eval.py -v`
Expected: PASS, every test from Milestones 3/5/6 unchanged.

- [ ] **Step 3: Write the failing "those" follow-up eval test**

Add at the end of the file:

```python
@pytest.mark.asyncio
async def test_eval_those_follow_up_resolves_customer_name_via_piping(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Milestone 7 acceptance: 'Show overdue invoices' followed by 'Which
    of those belong to ABC Industries?' must plan a two-step
    get_customer -> get_overdue_invoices chain for the follow-up, proving
    the planner can combine memory (recognizing 'those' refers to the
    prior overdue-invoices turn) with parameter piping (resolving the
    company name to a business code) in one plan."""
    llm_service_1 = FakeLLMService(
        tokens=["Here are the overdue invoices."],
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
    )
    workflow_1 = _make_workflow(db_session, llm_service_1)

    conversation_id: str | None = None
    async for event in workflow_1.run(
        ChatRequest(session_id="eval-those-session", message="Show overdue invoices")
    ):
        if event.type == "done":
            conversation_id = event.conversation_id
    await db_session.commit()
    assert conversation_id is not None

    llm_service_2 = FakeLLMService(
        tokens=["Just that one."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "ABC Industries"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
    )
    workflow_2 = _make_workflow(db_session, llm_service_2)

    events = [
        e
        async for e in workflow_2.run(
            ChatRequest(
                session_id="eval-those-session",
                message="Which of those belong to ABC Industries?",
                conversation_id=conversation_id,
            )
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer", "get_overdue_invoices"]
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_eval.py -v`
Expected: PASS, including the new test (it uses a hardcoded
`plan_response` per Milestone 5/6's established scope boundary — proves
the system correctly executes whatever the planner decided, not real
NLU accuracy for this exact phrasing).

- [ ] **Step 5: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_chat_eval.py
git commit -m "test: add AI eval case for the 'those' follow-up scenario

Two-turn scripted conversation (FakeLLMService, hardcoded plan_response
per turn) proving the workflow correctly executes a get_customer ->
get_overdue_invoices piped plan for a follow-up referencing a prior
turn's result set - Milestone 7's first named acceptance scenario."
```

---

### Task 28: AI eval test — the payment-prioritization scenario

**Files:**
- Modify: `backend/tests/test_chat_eval.py`

**Interfaces:**
- Consumes: `_make_workflow` (Task 27, already registers
  `GET_VENDOR_INVOICES_TOOL`/`GET_CASH_POSITION_TOOL`).

- [ ] **Step 1: Write the failing eval test**

Add at the end of `backend/tests/test_chat_eval.py`:

```python
@pytest.mark.asyncio
async def test_eval_payment_prioritization_plans_vendor_invoices_and_cash_position(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Milestone 7 acceptance: 'Which invoices should I pay first?' has no
    single tool - the planner must retrieve both get_vendor_invoices and
    get_cash_position (independent, no piping needed) so Phase 2 can
    reason over the combined data."""
    llm_service = FakeLLMService(
        tokens=["Based on due dates and cash on hand, pay X first."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_vendor_invoices", "parameters": {}}, '
            '{"tool": "get_cash_position", "parameters": {}}'
            ']}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events = [
        e
        async for e in workflow.run(
            ChatRequest(
                session_id="eval-payment-priority-session",
                message="Which invoices should I pay first?",
            )
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_vendor_invoices", "get_cash_position"]

    assert llm_service.last_message is not None
    payload_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[1]
    import json as json_module

    payload = json_module.loads(payload_json)
    assert {result["tool"] for result in payload} == {"get_vendor_invoices", "get_cash_position"}
```

- [ ] **Step 2: Run it to confirm it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_chat_eval.py -v`
Expected: PASS — both tools' results reach the Phase-2 prompt together.

- [ ] **Step 3: Run the full backend suite and lint/type checks**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_chat_eval.py
git commit -m "test: add AI eval case for the payment-prioritization scenario

Proves get_vendor_invoices and get_cash_position both execute and both
reach the Phase-2 prompt together for a reasoning question with no
single-tool answer - Milestone 7's second named acceptance scenario."
```

---

### Task 29: Full verification re-run and HANDOFF.md rewrite

**Files:**
- Modify: `HANDOFF.md`

**Interfaces:** None — this is a verification and documentation task, no
code changes.

- [ ] **Step 1: Re-seed the simulator from a clean slate**

Run, from `backend/`:
```bash
.venv/Scripts/python -m domains.finance.simulator.seed --reset
```
Expected: `Seeded Northwind Manufacturing Ltd. (seed=42).`

```bash
.venv/Scripts/python -m domains.finance.simulator.consistency_check
```
Expected: `Consistency check passed: 0 violations.`

Note the real seeded data this session will use for the live check in
Step 5 — direct SQL spot-checks: a real customer name with overdue
invoices (e.g. via `SELECT company_name FROM finance.customers c JOIN
finance.invoices i ON i.customer_id = c.id WHERE i.status = 'overdue'
LIMIT 5`), and confirm `finance.vendor_invoices`/
`finance.cash_transactions` are populated (`SELECT COUNT(*) FROM
finance.vendor_invoices`, `SELECT COUNT(*) FROM
finance.cash_transactions`).

- [ ] **Step 2: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: PASS, every test from Milestones 1-6 plus every new test in
this plan. Reseed afterward (per Milestone 6 HANDOFF's own documented
procedural finding: `clean_db` truncates the same dev database the seed
script populates) before Step 5's live check.

- [ ] **Step 3: Run lint and strict type checks over the full project scope**

Run: `cd backend && .venv/Scripts/python -m ruff check . ../ai_platform ../domains`
Run: `cd backend && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: `All checks passed!` and `Success: no issues found in N source
files`.

- [ ] **Step 4: Run frontend checks (no code changed, confirm no regression)**

Run: `cd frontend && npm run lint`
Run: `cd frontend && npm run typecheck`
Run: `cd frontend && npm run build`
Expected: all clean, matching Milestone 6's baseline (this milestone
made no frontend changes — every new tool's result is either
`{invoices, summary}`-shaped or a flat record, both already handled
generically by the existing renderer — this step exists to confirm that
claim, not to fix anything).

- [ ] **Step 5: Manual chat smoke test against the real running app**

Reseed first (`.venv/Scripts/python -m domains.finance.simulator.seed
--reset`, per Step 2's note). Start the backend
(`uvicorn app.main:app --reload` from `backend/`) and frontend (`npm run
dev` from `frontend/`) and, in the browser, exercise the two PRD
scripted conversations end to end. Substitute real seeded entity names
where the brief's own literal examples ("ABC Industries") don't exist in
this seed (per Milestone 6 HANDOFF's precedent — substitute
transparently and record both the substitution and the literal phrasing
tested):

1. **Turn 1**: "Show overdue invoices" (or "Which invoices are overdue?")
   → a table of overdue invoices.
2. **Turn 2, same conversation**: "Which of those belong to
   `<a real seeded customer name from Step 1's overdue results>`?" → a
   table scoped to just that customer's overdue invoices (or a correct
   "none of those" answer if that customer happens to have no overdue
   invoices — either is a valid, correct answer; verify against direct
   SQL either way). Confirm via `application.tool_executions` that turn
   2 actually called `get_customer` then `get_overdue_invoices` with the
   resolved `customer_id`, not a re-listing of turn 1's raw results.
3. **New conversation, "Which invoices should I pay first?"** → a
   prioritized recommendation naming specific vendor invoices, due
   dates, and the current cash position, with reasoning grounded in
   those figures (not a table — this is a reasoning answer). Confirm via
   `tool_executions` that both `get_vendor_invoices` and
   `get_cash_position` were called for this turn.

Record the actual observed results (pass/fail per turn, the exact
LLM/data used, and anything that didn't go as expected) in HANDOFF.md —
do not claim success without having run this.

- [ ] **Step 6: Rewrite `HANDOFF.md`**

Update `HANDOFF.md` following the same structure as Milestone 6's
version: current milestone/status header, §1 verified current state
(commands + output), §2 work completed this session, §3 in-progress work
(should be "nothing" if all tasks are done), §4 decisions made (mirror
this plan's two-phase design and the load-bearing decisions: the
`VendorBalance` field rename, the `ExecutionPlanner` being a pure
resolver rather than a `run()`-style executor to preserve per-step
`tool_call` streaming, the `$stepN.field` piping syntax, the 5-call cap
firing a clarifying question rather than an error), §5 known issues
(carry forward anything still open — `PaymentRepository.record_payment`'s
validation gap remains untouched and still relevant; note whether the
live check's two scripted conversations both worked, or surfaced new
findings the way Milestone 6's own closing task did), §6 do-NOT-do list,
§7 next steps (Domain Adapters, per Milestone 6 HANDOFF §7 item 1, are
now overdue given 8 real tools exist after this milestone; parallel
tool execution for independent steps, per Milestone 5 HANDOFF's
long-deferred item 7, is now concrete since multi-step plans exist to
parallelize; the still-open `PaymentRepository`/customer_id-vs-name
harmonization items from Milestone 6 HANDOFF remain queued).

- [ ] **Step 7: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 7 (Multi-Tool Reasoning) completion"
```

---

## Acceptance Criteria (from the milestone brief)

- Integration test (mocked LLM, real Postgres): a dependent two-step plan
  executes correctly with parameter piping (Task 20).
- AI eval tests: the "those" follow-up scenario and the
  payment-prioritization scenario each produce the correct tool sequence
  (Tasks 27-28).
- Both PRD scripted conversations ("Show overdue invoices" → "Which of
  those belong to ABC Industries?", and "Which invoices should I pay
  first?") work end-to-end in the UI with visible, correct answers,
  verified live with a real LLM (Task 29).

