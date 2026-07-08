# Milestone 4 — Finance Simulation Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Finance Simulation Environment: 11 `finance`-schema
tables (+ an empty `evaluation` schema) via Alembic, a deterministic seed
generator for "Northwind Manufacturing Ltd.", five repositories, and a
consistency-check script — so `python -m domains.finance.simulator.seed
--reset` produces a believable company and `python -m
domains.finance.simulator.consistency_check` reports zero violations.

**Architecture:** `domains/finance/models/` (SQLAlchemy ORM, one file per
aggregate) → `domains/finance/repositories/` (thin async data access, no
business rules, mirroring `ai_platform/memory/repository.py`) →
`domains/finance/simulator/` (a `SimulatorSeeder` driven by one seeded
`random.Random` instance, calling the repositories for every write so the
seeder and any future runtime tool share identical balance-update logic).

**Tech Stack:** SQLAlchemy 2.0 async ORM, Alembic, asyncpg, pytest +
pytest-asyncio, Python 3.12 stdlib `random`/`decimal`/`datetime` only (no
Faker).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-08-milestone-4-finance-simulator-design.md` — every task below implements a section of it; consult it for the "why" behind any decision that looks arbitrary.
- Python 3.12, mypy strict mode (`disallow_untyped_defs`, `warn_return_any`, no implicit optional) — every new function needs full type annotations.
- `from __future__ import annotations` at the top of every new `.py` file, matching the existing codebase.
- All money columns/values are `Decimal` via SQLAlchemy `Numeric` — never `float`.
- `SIMULATION_TODAY = date(2026, 7, 8)` is the **only** source of "today" inside the simulator — never `datetime.now()`/`date.today()` in `domains/finance/simulator/`. Repositories stay domain-agnostic: they accept an optional `today: date | None` parameter that defaults to real `date.today()`, and only the simulator ever passes `SIMULATION_TODAY` explicitly.
- No new dependencies (no Faker) — realistic data comes from hand-written word lists in `domains/finance/simulator/data.py`.
- `ruff check . ../ai_platform` and `mypy app alembic ../ai_platform` (run from `backend/`) must stay clean after every task — the codebase's existing bar, not a new one.
- Tests use the existing `clean_db`/`db_session` fixtures from `backend/tests/conftest.py` — do not invent a new DB-fixture pattern.
- Every migration, model, and repository follows the exact style already established in `ai_platform/memory/models.py`, `ai_platform/memory/repository.py`, and `backend/alembic/versions/daf36d10940a_create_application_schema.py` — read those before writing new ones if a step's code looks unfamiliar.

---

## Task 1: `Customer`, `Vendor`, `Product` ORM models

**Files:**
- Create: `domains/__init__.py` (empty)
- Create: `domains/finance/__init__.py` (empty)
- Create: `domains/finance/models/__init__.py`
- Create: `domains/finance/models/organizations.py`
- Create: `domains/finance/models/catalog.py`
- Test: `backend/tests/test_finance_models.py`

**Interfaces:**
- Produces: `CustomerModel`, `VendorModel` (both `SCHEMA = "finance"`, in `domains/finance/models/organizations.py`), `ProductModel` (`domains/finance/models/catalog.py`). Re-exported from `domains.finance.models`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_finance_models.py`:

```python
from __future__ import annotations

from domains.finance.models import CustomerModel, ProductModel, VendorModel


def test_customer_model_uses_finance_schema() -> None:
    assert CustomerModel.__table__.schema == "finance"


def test_customer_model_has_expected_columns() -> None:
    columns = {c.name for c in CustomerModel.__table__.columns}
    assert {
        "id", "customer_code", "company_name", "industry", "contact_name",
        "contact_email", "payment_terms", "credit_limit", "status",
        "created_at", "updated_at",
    } <= columns
    assert "balance" not in columns


def test_vendor_model_has_expected_columns() -> None:
    columns = {c.name for c in VendorModel.__table__.columns}
    assert {
        "id", "vendor_code", "company_name", "category", "contact_name",
        "contact_email", "payment_terms", "preferred", "status",
        "created_at", "updated_at",
    } <= columns


def test_product_model_has_expected_columns() -> None:
    columns = {c.name for c in ProductModel.__table__.columns}
    assert {"id", "sku", "name", "category", "unit_price", "is_active", "created_at"} <= columns
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.models'`

- [ ] **Step 3: Create the package skeleton**

Create `domains/__init__.py` (empty file).
Create `domains/finance/__init__.py` (empty file).

- [ ] **Step 4: Write `domains/finance/models/organizations.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class CustomerModel(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_customers_payment_terms",
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(20), nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VendorModel(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_vendors_payment_terms",
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_vendors_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(20), nullable=False)
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Write `domains/finance/models/catalog.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 6: Write `domains/finance/models/__init__.py`**

```python
from __future__ import annotations

from domains.finance.models.catalog import ProductModel
from domains.finance.models.organizations import CustomerModel, VendorModel

__all__ = [
    "CustomerModel",
    "VendorModel",
    "ProductModel",
]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add domains/__init__.py domains/finance/__init__.py domains/finance/models/ backend/tests/test_finance_models.py
git commit -m "feat: add Customer, Vendor, Product finance ORM models"
```

---

## Task 2: `Department`, `Employee`, `PurchaseOrder`, `PurchaseOrderItem` ORM models

**Files:**
- Create: `domains/finance/models/workforce.py`
- Create: `domains/finance/models/purchasing.py`
- Modify: `domains/finance/models/__init__.py`
- Modify: `backend/tests/test_finance_models.py`

**Interfaces:**
- Consumes: `Base` from `app.db.base` (Task 1 pattern).
- Produces: `DepartmentModel`, `EmployeeModel`, `PurchaseOrderModel`, `PurchaseOrderItemModel`, all re-exported from `domains.finance.models`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_finance_models.py` (add to the existing import line and add new functions):

```python
from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorModel,
)


def test_department_model_has_expected_columns() -> None:
    columns = {c.name for c in DepartmentModel.__table__.columns}
    assert {"id", "name", "created_at"} <= columns


def test_employee_model_references_department() -> None:
    fk_targets = {fk.target_fullname for fk in EmployeeModel.__table__.foreign_keys}
    assert "finance.departments.id" in fk_targets


def test_purchase_order_model_references_vendor_and_employee() -> None:
    fk_targets = {fk.target_fullname for fk in PurchaseOrderModel.__table__.foreign_keys}
    assert "finance.vendors.id" in fk_targets
    assert "finance.employees.id" in fk_targets


def test_purchase_order_item_model_references_po_and_product() -> None:
    fk_targets = {fk.target_fullname for fk in PurchaseOrderItemModel.__table__.foreign_keys}
    assert "finance.purchase_orders.id" in fk_targets
    assert "finance.products.id" in fk_targets
```

(Replace the old single-line import of `CustomerModel, ProductModel, VendorModel` with the combined import block above.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'DepartmentModel'`

- [ ] **Step 3: Write `domains/finance/models/workforce.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class DepartmentModel(Base):
    __tablename__ = "departments"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmployeeModel(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="ck_employees_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Write `domains/finance/models/purchasing.py`**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class PurchaseOrderModel(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
        Index("ix_purchase_orders_vendor_id", "vendor_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PurchaseOrderItemModel(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
```

- [ ] **Step 5: Update `domains/finance/models/__init__.py`**

```python
from __future__ import annotations

from domains.finance.models.catalog import ProductModel
from domains.finance.models.organizations import CustomerModel, VendorModel
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
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Commit**

```bash
git add domains/finance/models/ backend/tests/test_finance_models.py
git commit -m "feat: add Department, Employee, PurchaseOrder finance ORM models"
```

---

## Task 3: `Invoice`, `InvoiceItem`, `Payment`, `ExpenseClaim` ORM models

**Files:**
- Create: `domains/finance/models/billing.py`
- Create: `domains/finance/models/expenses.py`
- Modify: `domains/finance/models/__init__.py`
- Modify: `backend/tests/test_finance_models.py`

**Interfaces:**
- Produces: `InvoiceModel`, `InvoiceItemModel`, `PaymentModel`, `ExpenseClaimModel`, all re-exported from `domains.finance.models`. This completes the model package — every later task imports models only from `domains.finance.models`, never from the individual aggregate files.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_finance_models.py`. Replace the import block with the full set:

```python
from domains.finance.models import (
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
    VendorModel,
)


def test_invoice_model_has_expected_columns() -> None:
    columns = {c.name for c in InvoiceModel.__table__.columns}
    assert {
        "id", "invoice_number", "customer_id", "purchase_order_id", "issue_date",
        "due_date", "status", "currency", "subtotal", "tax", "total",
        "amount_paid", "balance", "created_at", "updated_at",
    } <= columns


def test_invoice_model_purchase_order_is_nullable() -> None:
    column = InvoiceModel.__table__.columns["purchase_order_id"]
    assert column.nullable is True


def test_payment_model_references_invoice() -> None:
    fk_targets = {fk.target_fullname for fk in PaymentModel.__table__.foreign_keys}
    assert "finance.invoices.id" in fk_targets


def test_expense_claim_model_references_employee() -> None:
    fk_targets = {fk.target_fullname for fk in ExpenseClaimModel.__table__.foreign_keys}
    assert "finance.employees.id" in fk_targets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'InvoiceModel'`

- [ ] **Step 3: Write `domains/finance/models/billing.py`**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class InvoiceModel(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled')",
            name="ck_invoices_status",
        ),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_due_date", "due_date"),
        Index("ix_invoices_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.customers.id"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.purchase_orders.id"), nullable=True
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
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


class InvoiceItemModel(Base):
    __tablename__ = "invoice_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.invoices.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class PaymentModel(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('bank_transfer', 'check', 'credit_card', 'cash')",
            name="ck_payments_payment_method",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.invoices.id"), nullable=False, index=True
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Write `domains/finance/models/expenses.py`**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class ExpenseClaimModel(Base):
    __tablename__ = "expense_claims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'reimbursed')",
            name="ck_expense_claims_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Finalize `domains/finance/models/__init__.py`**

```python
from __future__ import annotations

from domains.finance.models.billing import InvoiceItemModel, InvoiceModel, PaymentModel
from domains.finance.models.catalog import ProductModel
from domains.finance.models.expenses import ExpenseClaimModel
from domains.finance.models.organizations import CustomerModel, VendorModel
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
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_finance_models.py -v`
Expected: PASS (12 tests)

- [ ] **Step 7: Run ruff and mypy**

Run (from `backend/`): `.venv/Scripts/python -m ruff check . ../ai_platform ../domains && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: both clean. Fix any reported issues before continuing (common one: unused imports if a column type import isn't actually used in a file).

- [ ] **Step 8: Commit**

```bash
git add domains/finance/models/ backend/tests/test_finance_models.py
git commit -m "feat: add Invoice, Payment, ExpenseClaim finance ORM models"
```

---

## Task 4: Alembic migration for the `finance` and `evaluation` schemas

**Files:**
- Create: `backend/alembic/versions/<generated>_create_finance_schema.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: all 11 model classes from Task 1-3 (column names/types/constraints must match exactly — this migration is hand-written, not autogenerated, so any drift is a real bug the ORM-model tests won't catch).
- Produces: `finance.*` tables and an empty `evaluation` schema in the real Postgres database. Every later task that touches the DB (repositories, generator, consistency check) depends on this migration having been applied.

- [ ] **Step 1: Make sure Postgres is running**

Run: `docker compose up -d` (repo root)
Expected: `postgres` container healthy (`docker compose ps` shows `healthy`).

- [ ] **Step 2: Generate a new empty migration**

Run (from `backend/`): `.venv/Scripts/python -m alembic revision -m "create finance and evaluation schemas"`
Expected: a new file appears under `backend/alembic/versions/`, e.g. `backend/alembic/versions/a1b2c3d4e5f6_create_finance_and_evaluation_schemas.py`, with `down_revision = "3ab683f3086d"` already filled in (the current head).

- [ ] **Step 3: Fill in `upgrade()`/`downgrade()`**

Open the generated file and replace the `upgrade`/`downgrade` bodies (keep the auto-generated `revision`/`down_revision` header as-is):

```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS finance")
    op.execute("CREATE SCHEMA IF NOT EXISTS evaluation")

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("contact_email", sa.String(length=200), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_customers_payment_terms",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        schema="finance",
    )

    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("contact_email", sa.String(length=200), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_vendors_payment_terms",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_vendors_status"),
        schema="finance",
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(length=30), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_employees_status"),
        schema="finance",
    )

    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("po_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.vendors.id"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column(
            "approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.employees.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
        sa.Index("ix_purchase_orders_vendor_id", "vendor_id"),
        schema="finance",
    )

    op.create_table(
        "purchase_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Index("ix_purchase_order_items_purchase_order_id", "purchase_order_id"),
        schema="finance",
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.customers.id"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
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
            name="ck_invoices_status",
        ),
        sa.Index("ix_invoices_customer_id", "customer_id"),
        sa.Index("ix_invoices_due_date", "due_date"),
        sa.Index("ix_invoices_status", "status"),
        schema="finance",
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.invoices.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Index("ix_invoice_items_invoice_id", "invoice_id"),
        schema="finance",
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.invoices.id"),
            nullable=False,
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
            name="ck_payments_payment_method",
        ),
        sa.Index("ix_payments_invoice_id", "invoice_id"),
        schema="finance",
    )

    op.create_table(
        "expense_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.employees.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("submitted_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'reimbursed')",
            name="ck_expense_claims_status",
        ),
        sa.Index("ix_expense_claims_employee_id", "employee_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("expense_claims", schema="finance")
    op.drop_table("payments", schema="finance")
    op.drop_table("invoice_items", schema="finance")
    op.drop_table("invoices", schema="finance")
    op.drop_table("purchase_order_items", schema="finance")
    op.drop_table("purchase_orders", schema="finance")
    op.drop_table("employees", schema="finance")
    op.drop_table("products", schema="finance")
    op.drop_table("vendors", schema="finance")
    op.drop_table("customers", schema="finance")
    op.drop_table("departments", schema="finance")
    op.execute("DROP SCHEMA IF EXISTS evaluation CASCADE")
    op.execute("DROP SCHEMA IF EXISTS finance CASCADE")
```

- [ ] **Step 4: Wire the models into `backend/alembic/env.py`**

In `backend/alembic/env.py`, add one import line after the existing model imports (around line 24):

```python
from ai_platform.memory import models as _memory_models  # noqa: E402,F401
from ai_platform.tool_registry import models as _tool_registry_models  # noqa: E402,F401
from domains.finance import models as _finance_models  # noqa: E402,F401
```

- [ ] **Step 5: Apply the migration**

Run (from `backend/`): `.venv/Scripts/python -m alembic upgrade head`
Expected: no errors; last line mentions the new revision ID.

- [ ] **Step 6: Verify against the live database**

Run (from `backend/`):
```bash
.venv/Scripts/python -c "
import asyncio
from sqlalchemy import text
from app.db.session import get_engine

async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(
            \"SELECT table_name FROM information_schema.tables WHERE table_schema = 'finance' ORDER BY table_name\"
        ))
        print(sorted(row[0] for row in result))
        result = await conn.execute(text(
            \"SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'evaluation'\"
        ))
        print(list(result))
    await engine.dispose()

asyncio.run(main())
"
```
Expected: prints all 11 table names and one `evaluation` schema row.

- [ ] **Step 7: Verify downgrade/upgrade round-trip**

Run (from `backend/`):
```bash
.venv/Scripts/python -m alembic downgrade -1
.venv/Scripts/python -m alembic upgrade head
```
Expected: both succeed with no errors — proves `downgrade()` is not just decorative.

- [ ] **Step 8: Extend `clean_db`'s TRUNCATE list in `backend/tests/conftest.py`**

Modify the `clean_db` fixture's `TRUNCATE` statement (around line 62-66):

```python
        await conn.execute(
            text(
                "TRUNCATE TABLE application.tool_executions, application.messages, "
                "application.conversations, application.sessions, "
                "finance.payments, finance.invoice_items, finance.invoices, "
                "finance.purchase_order_items, finance.purchase_orders, "
                "finance.expense_claims, finance.employees, finance.departments, "
                "finance.products, finance.customers, finance.vendors CASCADE"
            )
        )
```

- [ ] **Step 9: Run the full existing test suite to confirm nothing broke**

Run (from `backend/`): `.venv/Scripts/python -m pytest -v`
Expected: all pre-existing tests still PASS (the `clean_db` fixture change must not break Milestone 1-3 tests).

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/ backend/tests/conftest.py
git commit -m "feat: add finance and evaluation schema migration"
```

---

## Task 5: `CustomerRepository` and `VendorRepository`

**Files:**
- Create: `domains/finance/repositories/__init__.py`
- Create: `domains/finance/repositories/customer_repository.py`
- Create: `domains/finance/repositories/vendor_repository.py`
- Test: `backend/tests/test_customer_repository.py`
- Test: `backend/tests/test_vendor_repository.py`

**Interfaces:**
- Consumes: `CustomerModel`, `VendorModel` from `domains.finance.models` (Task 1).
- Produces: `CustomerRepository(db: AsyncSession)` with `create(...) -> CustomerModel`, `get_by_id(customer_id: uuid.UUID) -> CustomerModel | None`, `get_by_code(customer_code: str) -> CustomerModel | None`, `list_all() -> list[CustomerModel]`. `VendorRepository` mirrors the same four methods for `VendorModel`. Task 9 (seed generator) calls these directly.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_customer_repository.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository


@pytest.mark.asyncio
async def test_create_and_get_by_id(clean_db: None, db_session: AsyncSession) -> None:
    repo = CustomerRepository(db_session)
    customer = await repo.create(
        customer_code="CUST-0001",
        company_name="Northwind Manufacturing Ltd.",
        industry="Automotive",
        contact_name="Jane Doe",
        contact_email="jane.doe@example.com",
        payment_terms="net_30",
        credit_limit=Decimal("100000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_id(customer.id)
    assert fetched is not None
    assert fetched.customer_code == "CUST-0001"
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_get_by_code_returns_none_when_missing(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-0002",
        company_name="Atlas Industries",
        industry="Electronics",
        contact_name="John Smith",
        contact_email="john.smith@example.com",
        payment_terms="net_45",
        credit_limit=Decimal("50000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_code("CUST-0002")
    assert fetched is not None
    assert fetched.company_name == "Atlas Industries"
    assert await repo.get_by_code("CUST-9999") is None


@pytest.mark.asyncio
async def test_list_all_orders_by_customer_code(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = CustomerRepository(db_session)
    await repo.create(
        customer_code="CUST-0002", company_name="B Corp", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("1000.00"),
    )
    await repo.create(
        customer_code="CUST-0001", company_name="A Corp", industry="Retail",
        contact_name="B", contact_email="b@example.com", payment_terms="net_30",
        credit_limit=Decimal("1000.00"),
    )
    await db_session.commit()

    customers = await repo.list_all()
    assert [c.customer_code for c in customers] == ["CUST-0001", "CUST-0002"]
```

Create `backend/tests/test_vendor_repository.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_repository import VendorRepository


@pytest.mark.asyncio
async def test_create_and_get_by_id(clean_db: None, db_session: AsyncSession) -> None:
    repo = VendorRepository(db_session)
    vendor = await repo.create(
        vendor_code="VEND-0001",
        company_name="Summit Traders",
        category="raw_materials",
        contact_name="Amy Chen",
        contact_email="amy.chen@example.com",
        payment_terms="net_30",
    )
    await db_session.commit()

    fetched = await repo.get_by_id(vendor.id)
    assert fetched is not None
    assert fetched.vendor_code == "VEND-0001"
    assert fetched.preferred is False
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_get_by_code_returns_none_when_missing(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = VendorRepository(db_session)
    await repo.create(
        vendor_code="VEND-0002",
        company_name="Cascade Logistics",
        category="logistics",
        contact_name="Bo Kim",
        contact_email="bo.kim@example.com",
        payment_terms="net_15",
        preferred=True,
    )
    await db_session.commit()

    fetched = await repo.get_by_code("VEND-0002")
    assert fetched is not None
    assert fetched.preferred is True
    assert await repo.get_by_code("VEND-9999") is None


@pytest.mark.asyncio
async def test_list_all_orders_by_vendor_code(clean_db: None, db_session: AsyncSession) -> None:
    repo = VendorRepository(db_session)
    await repo.create(
        vendor_code="VEND-0002", company_name="B Vendor", category="software",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    await repo.create(
        vendor_code="VEND-0001", company_name="A Vendor", category="software",
        contact_name="B", contact_email="b@example.com", payment_terms="net_30",
    )
    await db_session.commit()

    vendors = await repo.list_all()
    assert [v.vendor_code for v in vendors] == ["VEND-0001", "VEND-0002"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_customer_repository.py tests/test_vendor_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.repositories'`

- [ ] **Step 3: Write `domains/finance/repositories/__init__.py`**

```python
from __future__ import annotations
```

- [ ] **Step 4: Write `domains/finance/repositories/customer_repository.py`**

```python
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import CustomerModel


class CustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        customer_code: str,
        company_name: str,
        industry: str,
        contact_name: str,
        contact_email: str,
        payment_terms: str,
        credit_limit: Decimal,
        status: str = "active",
    ) -> CustomerModel:
        customer = CustomerModel(
            id=uuid.uuid4(),
            customer_code=customer_code,
            company_name=company_name,
            industry=industry,
            contact_name=contact_name,
            contact_email=contact_email,
            payment_terms=payment_terms,
            credit_limit=credit_limit,
            status=status,
        )
        self._db.add(customer)
        await self._db.flush()
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> CustomerModel | None:
        return await self._db.get(CustomerModel, customer_id)

    async def get_by_code(self, customer_code: str) -> CustomerModel | None:
        stmt = select(CustomerModel).where(CustomerModel.customer_code == customer_code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[CustomerModel]:
        stmt = select(CustomerModel).order_by(CustomerModel.customer_code)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 5: Write `domains/finance/repositories/vendor_repository.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import VendorModel


class VendorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        vendor_code: str,
        company_name: str,
        category: str,
        contact_name: str,
        contact_email: str,
        payment_terms: str,
        preferred: bool = False,
        status: str = "active",
    ) -> VendorModel:
        vendor = VendorModel(
            id=uuid.uuid4(),
            vendor_code=vendor_code,
            company_name=company_name,
            category=category,
            contact_name=contact_name,
            contact_email=contact_email,
            payment_terms=payment_terms,
            preferred=preferred,
            status=status,
        )
        self._db.add(vendor)
        await self._db.flush()
        return vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> VendorModel | None:
        return await self._db.get(VendorModel, vendor_id)

    async def get_by_code(self, vendor_code: str) -> VendorModel | None:
        stmt = select(VendorModel).where(VendorModel.vendor_code == vendor_code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[VendorModel]:
        stmt = select(VendorModel).order_by(VendorModel.vendor_code)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_customer_repository.py tests/test_vendor_repository.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add domains/finance/repositories/ backend/tests/test_customer_repository.py backend/tests/test_vendor_repository.py
git commit -m "feat: add CustomerRepository and VendorRepository"
```

---

## Task 6: `PurchaseOrderRepository`

**Files:**
- Create: `domains/finance/repositories/purchase_order_repository.py`
- Test: `backend/tests/test_purchase_order_repository.py`

**Interfaces:**
- Consumes: `PurchaseOrderModel` from `domains.finance.models`; `VendorRepository` from Task 5 (test setup only).
- Produces: `PurchaseOrderRepository(db)` with `create(...) -> PurchaseOrderModel`, `get_by_id`, `get_by_number`, `list_by_vendor(vendor_id) -> list[PurchaseOrderModel]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_purchase_order_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    vendor_repo = VendorRepository(db_session)
    return await vendor_repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


@pytest.mark.asyncio
async def test_create_and_get_by_number(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    repo = PurchaseOrderRepository(db_session)
    po = await repo.create(
        po_number="PO-1001",
        vendor_id=vendor.id,
        order_date=date(2026, 1, 15),
        status="approved",
        total_amount=Decimal("5000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_number("PO-1001")
    assert fetched is not None
    assert fetched.id == po.id
    assert fetched.approved_by is None


@pytest.mark.asyncio
async def test_list_by_vendor_orders_by_order_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session)
    repo = PurchaseOrderRepository(db_session)
    await repo.create(
        po_number="PO-1002", vendor_id=vendor.id, order_date=date(2026, 2, 1),
        status="received", total_amount=Decimal("1000.00"),
    )
    await repo.create(
        po_number="PO-1001", vendor_id=vendor.id, order_date=date(2026, 1, 1),
        status="received", total_amount=Decimal("2000.00"),
    )
    await db_session.commit()

    purchase_orders = await repo.list_by_vendor(vendor.id)
    assert [po.po_number for po in purchase_orders] == ["PO-1001", "PO-1002"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_purchase_order_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.repositories.purchase_order_repository'`

- [ ] **Step 3: Write `domains/finance/repositories/purchase_order_repository.py`**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import PurchaseOrderModel


class PurchaseOrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        po_number: str,
        vendor_id: uuid.UUID,
        order_date: date,
        status: str,
        total_amount: Decimal,
        approved_by: uuid.UUID | None = None,
        approved_at: datetime | None = None,
    ) -> PurchaseOrderModel:
        purchase_order = PurchaseOrderModel(
            id=uuid.uuid4(),
            po_number=po_number,
            vendor_id=vendor_id,
            order_date=order_date,
            status=status,
            approved_by=approved_by,
            approved_at=approved_at,
            total_amount=total_amount,
        )
        self._db.add(purchase_order)
        await self._db.flush()
        return purchase_order

    async def get_by_id(self, purchase_order_id: uuid.UUID) -> PurchaseOrderModel | None:
        return await self._db.get(PurchaseOrderModel, purchase_order_id)

    async def get_by_number(self, po_number: str) -> PurchaseOrderModel | None:
        stmt = select(PurchaseOrderModel).where(PurchaseOrderModel.po_number == po_number)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_id: uuid.UUID) -> list[PurchaseOrderModel]:
        stmt = (
            select(PurchaseOrderModel)
            .where(PurchaseOrderModel.vendor_id == vendor_id)
            .order_by(PurchaseOrderModel.order_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_purchase_order_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add domains/finance/repositories/purchase_order_repository.py backend/tests/test_purchase_order_repository.py
git commit -m "feat: add PurchaseOrderRepository"
```

---

## Task 7: `InvoiceRepository` and `compute_invoice_status`

**Files:**
- Create: `domains/finance/repositories/invoice_repository.py`
- Test: `backend/tests/test_invoice_repository.py`

**Interfaces:**
- Consumes: `InvoiceModel` from `domains.finance.models`; `CustomerRepository` from Task 5 (test setup only).
- Produces:
  - `compute_invoice_status(*, total: Decimal, amount_paid: Decimal, due_date: date, as_of: date, current_status: str) -> str` — the priority rule from the design spec (`cancelled`/`draft` preserved; else `paid` > `overdue` > `partially_paid` > `sent`). **Task 8 imports this function** — its name and signature must not change later.
  - `InvoiceRepository(db)` with `create(...) -> InvoiceModel` (always sets `amount_paid=0`, `balance=total`), `get_by_id`, `get_by_number`, `list_by_customer(customer_id) -> list[InvoiceModel]`, `list_overdue(as_of: date) -> list[InvoiceModel]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import (
    InvoiceRepository,
    compute_invoice_status,
)


async def _make_customer(db_session: AsyncSession, code: str = "CUST-0001") -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000.00"),
    )


@pytest.mark.asyncio
async def test_create_sets_balance_to_total(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    invoice = await repo.create(
        invoice_number="INV-7001",
        customer_id=customer.id,
        purchase_order_id=None,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        status="sent",
        subtotal=Decimal("900.00"),
        tax=Decimal("100.00"),
        total=Decimal("1000.00"),
    )
    await db_session.commit()

    assert invoice.amount_paid == Decimal("0")
    assert invoice.balance == Decimal("1000.00")
    assert invoice.currency == "USD"


@pytest.mark.asyncio
async def test_list_by_customer_orders_by_issue_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7002", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    invoices = await repo.list_by_customer(customer.id)
    assert [i.invoice_number for i in invoices] == ["INV-7001", "INV-7002"]


@pytest.mark.asyncio
async def test_list_overdue_filters_by_status_and_due_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7003", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2025, 12, 1), due_date=date(2026, 1, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7004", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    overdue = await repo.list_overdue(as_of=date(2026, 7, 8))
    assert [i.invoice_number for i in overdue] == ["INV-7003"]


def test_compute_invoice_status_priority_rule() -> None:
    common = {"total": Decimal("100"), "due_date": date(2026, 1, 1), "as_of": date(2026, 7, 8)}
    assert compute_invoice_status(amount_paid=Decimal("0"), current_status="cancelled", **common) == "cancelled"
    assert compute_invoice_status(amount_paid=Decimal("0"), current_status="draft", **common) == "draft"
    assert compute_invoice_status(amount_paid=Decimal("100"), current_status="sent", **common) == "paid"
    assert compute_invoice_status(amount_paid=Decimal("40"), current_status="sent", **common) == "overdue"
    not_yet_due = {"total": Decimal("100"), "due_date": date(2026, 12, 1), "as_of": date(2026, 7, 8)}
    assert compute_invoice_status(amount_paid=Decimal("40"), current_status="sent", **not_yet_due) == "partially_paid"
    assert compute_invoice_status(amount_paid=Decimal("0"), current_status="sent", **not_yet_due) == "sent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_invoice_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.repositories.invoice_repository'`

- [ ] **Step 3: Write `domains/finance/repositories/invoice_repository.py`**

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import InvoiceModel


def compute_invoice_status(
    *,
    total: Decimal,
    amount_paid: Decimal,
    due_date: date,
    as_of: date,
    current_status: str,
) -> str:
    """Derives an invoice's status from its balance and due date.

    `cancelled` and `draft` are manually-controlled states never overridden
    by balance/due-date math; every other status is derived, in priority
    order: paid > overdue > partially_paid > sent. A partially-paid invoice
    that is also past due is `overdue`, not `partially_paid` (see design
    spec's "Status determination rule").
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


class InvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        invoice_number: str,
        customer_id: uuid.UUID,
        purchase_order_id: uuid.UUID | None,
        issue_date: date,
        due_date: date,
        status: str,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
        currency: str = "USD",
    ) -> InvoiceModel:
        invoice = InvoiceModel(
            id=uuid.uuid4(),
            invoice_number=invoice_number,
            customer_id=customer_id,
            purchase_order_id=purchase_order_id,
            issue_date=issue_date,
            due_date=due_date,
            status=status,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            amount_paid=Decimal("0"),
            balance=total,
        )
        self._db.add(invoice)
        await self._db.flush()
        return invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> InvoiceModel | None:
        return await self._db.get(InvoiceModel, invoice_id)

    async def get_by_number(self, invoice_number: str) -> InvoiceModel | None:
        stmt = select(InvoiceModel).where(InvoiceModel.invoice_number == invoice_number)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: uuid.UUID) -> list[InvoiceModel]:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.customer_id == customer_id)
            .order_by(InvoiceModel.issue_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_overdue(self, as_of: date) -> list[InvoiceModel]:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.status == "overdue", InvoiceModel.due_date < as_of)
            .order_by(InvoiceModel.due_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_invoice_repository.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add domains/finance/repositories/invoice_repository.py backend/tests/test_invoice_repository.py
git commit -m "feat: add InvoiceRepository and compute_invoice_status"
```

---

## Task 8: `PaymentRepository`

**Files:**
- Create: `domains/finance/repositories/payment_repository.py`
- Test: `backend/tests/test_payment_repository.py`

**Interfaces:**
- Consumes: `PaymentModel`, `InvoiceModel` from `domains.finance.models`; `compute_invoice_status` from Task 7's `domains.finance.repositories.invoice_repository`; `CustomerRepository`, `InvoiceRepository` (test setup only).
- Produces: `PaymentRepository(db)` with `record_payment(*, invoice_id, payment_date, amount, payment_method, reference_number=None, today=None) -> PaymentModel` (mutates and flushes the parent invoice's `amount_paid`/`balance`/`status` in the same call) and `list_by_invoice(invoice_id) -> list[PaymentModel]`. **Task 9/10's `SimulatorSeeder` calls `record_payment` for every seeded payment** — this is the only place invoice balances are ever mutated.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_payment_repository.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository


async def _make_invoice(
    db_session: AsyncSession, *, due_date: date, total: Decimal = Decimal("1000.00")
) -> object:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-0001", company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    return await invoice_repo.create(
        invoice_number="INV-7001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=due_date, status="sent",
        subtotal=total, tax=Decimal("0"), total=total,
    )


@pytest.mark.asyncio
async def test_full_payment_marks_invoice_paid(clean_db: None, db_session: AsyncSession) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("1000.00"),
        payment_method="bank_transfer", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.amount_paid == Decimal("1000.00")
    assert invoice.balance == Decimal("0.00")
    assert invoice.status == "paid"


@pytest.mark.asyncio
async def test_partial_payment_before_due_date_is_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.balance == Decimal("600.00")
    assert invoice.status == "partially_paid"


@pytest.mark.asyncio
async def test_partial_payment_after_due_date_is_overdue_not_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 1, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.balance == Decimal("600.00")
    assert invoice.status == "overdue"


@pytest.mark.asyncio
async def test_list_by_invoice_returns_all_payments(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 15), amount=Decimal("600.00"),
        payment_method="bank_transfer", today=date(2026, 7, 8),
    )
    await db_session.commit()

    payments = await repo.list_by_invoice(invoice.id)
    assert len(payments) == 2
    assert invoice.status == "paid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_payment_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.repositories.payment_repository'`

- [ ] **Step 3: Write `domains/finance/repositories/payment_repository.py`**

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import InvoiceModel, PaymentModel
from domains.finance.repositories.invoice_repository import compute_invoice_status


class PaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_payment(
        self,
        *,
        invoice_id: uuid.UUID,
        payment_date: date,
        amount: Decimal,
        payment_method: str,
        reference_number: str | None = None,
        today: date | None = None,
    ) -> PaymentModel:
        invoice = await self._db.get(InvoiceModel, invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} does not exist")

        payment = PaymentModel(
            id=uuid.uuid4(),
            invoice_id=invoice_id,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
        )
        self._db.add(payment)

        as_of = today if today is not None else date.today()
        invoice.amount_paid = invoice.amount_paid + amount
        invoice.balance = invoice.total - invoice.amount_paid
        invoice.status = compute_invoice_status(
            total=invoice.total,
            amount_paid=invoice.amount_paid,
            due_date=invoice.due_date,
            as_of=as_of,
            current_status=invoice.status,
        )

        await self._db.flush()
        return payment

    async def list_by_invoice(self, invoice_id: uuid.UUID) -> list[PaymentModel]:
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.invoice_id == invoice_id)
            .order_by(PaymentModel.payment_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_payment_repository.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run ruff and mypy, then full suite**

Run (from `backend/`):
```bash
.venv/Scripts/python -m ruff check . ../ai_platform ../domains
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains
.venv/Scripts/python -m pytest -v
```
Expected: all clean/PASS.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/repositories/payment_repository.py backend/tests/test_payment_repository.py
git commit -m "feat: add PaymentRepository with balance/status bookkeeping"
```

---

## Task 9: Simulator constants, word lists, and master-data generation

**Files:**
- Create: `domains/finance/simulator/__init__.py`
- Create: `domains/finance/simulator/constants.py`
- Create: `domains/finance/simulator/data.py`
- Create: `domains/finance/simulator/generator.py`
- Test: `backend/tests/test_simulator_master_data.py`

**Interfaces:**
- Consumes: `CustomerRepository`, `VendorRepository` (Task 5).
- Produces: `SimulatorSeeder(db: AsyncSession, seed: int = DEFAULT_SEED)` with (for now) `_seed_departments()`, `_seed_employees(departments)`, `_seed_customers()`, `_seed_vendors()`, `_seed_products()` — private helpers Task 10 assembles into the public `seed()` method. `_seed_customers()` returns `tuple[list[CustomerModel], dict[uuid.UUID, str]]` (customers, and a behavior-weight lookup by customer id) — Task 10's payment generation consumes that dict.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_simulator_master_data.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.simulator.constants import BEHAVIOR_WEIGHTS, NUM_CUSTOMERS, NUM_VENDORS
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_master_data_generation_produces_expected_counts(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    departments = await seeder._seed_departments()
    employees = await seeder._seed_employees(departments)
    customers, behavior_by_customer = await seeder._seed_customers()
    vendors = await seeder._seed_vendors()
    products = await seeder._seed_products()
    await db_session.commit()

    assert len(departments) == 5
    assert len(employees) == 20
    assert len(customers) == NUM_CUSTOMERS
    assert len(vendors) == NUM_VENDORS
    assert len(products) > 0
    assert len({c.customer_code for c in customers}) == NUM_CUSTOMERS
    assert set(behavior_by_customer.values()) <= set(BEHAVIOR_WEIGHTS)
    assert len(behavior_by_customer) == NUM_CUSTOMERS


@pytest.mark.asyncio
async def test_master_data_generation_is_deterministic(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder_a = SimulatorSeeder(db_session, seed=42)
    customers_a, _ = await seeder_a._seed_customers()
    names_a = [c.company_name for c in customers_a]
    await db_session.commit()

    async with db_session.begin():
        await db_session.execute(text("TRUNCATE TABLE finance.customers CASCADE"))

    seeder_b = SimulatorSeeder(db_session, seed=42)
    customers_b, _ = await seeder_b._seed_customers()
    names_b = [c.company_name for c in customers_b]

    assert names_a == names_b
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_simulator_master_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.simulator.constants'`

- [ ] **Step 3: Write `domains/finance/simulator/__init__.py`**

```python
from __future__ import annotations
```

- [ ] **Step 4: Write `domains/finance/simulator/constants.py`**

```python
from __future__ import annotations

from datetime import date

# Fixed anchor -- never datetime.now()/date.today() anywhere in this package.
# See design spec S3: re-running the same seed must always produce the same
# data, including which invoices count as overdue, regardless of the real
# calendar date on the machine running it.
SIMULATION_TODAY: date = date(2026, 7, 8)
DEFAULT_SEED: int = 42

NUM_CUSTOMERS = 25
NUM_VENDORS = 15
NUM_PURCHASE_ORDERS = 40
NUM_INVOICES = 200
NUM_DUPLICATE_INVOICES = 5
NUM_EXPENSE_CLAIMS_PER_EMPLOYEE = 3
NUM_EMPLOYEES = 20

PAYMENT_COVERAGE = 0.70
INVOICE_WINDOW_MONTHS = 18

# Mirrors the CHECK constraints in domains/finance/models/ -- one place
# each is spelled out, per the design spec.
PAYMENT_TERMS = ("net_15", "net_30", "net_45", "net_60")
ORG_STATUSES = ("active", "inactive")
PO_STATUSES = ("draft", "approved", "received", "cancelled")
INVOICE_STATUSES = ("draft", "sent", "paid", "partially_paid", "overdue", "cancelled")
PAYMENT_METHODS = ("bank_transfer", "check", "credit_card", "cash")
EXPENSE_STATUSES = ("submitted", "approved", "rejected", "reimbursed")

PAYMENT_TERMS_DAYS = {"net_15": 15, "net_30": 30, "net_45": 45, "net_60": 60}

# Per-customer payment-behavior weight, drawn once at generation time to bias
# payment timing and coverage -- not a formal Persona class or scenario-pack
# system (explicitly out of scope, see design spec's Scope Boundary).
BEHAVIOR_WEIGHTS = ("reliable", "average", "slow", "risky")
BEHAVIOR_DAYS_OFFSET = {
    "reliable": (-5, 2),
    "average": (-2, 10),
    "slow": (5, 45),
    "risky": (20, 90),
}
```

- [ ] **Step 5: Write `domains/finance/simulator/data.py`**

```python
from __future__ import annotations

COMPANY_PREFIXES = [
    "Northwind", "Atlas", "Summit", "Cascade", "Vertex", "Harbor", "Granite",
    "Meridian", "Pioneer", "Union", "Beacon", "Cobalt", "Anchor", "Falcon",
    "Redwood", "Sterling", "Horizon", "Titan", "Delta", "Crestline",
]
COMPANY_SUFFIXES = [
    "Manufacturing", "Industries", "Traders", "Logistics", "Supply Co.",
    "Holdings", "Materials", "Components", "Systems", "Distribution",
]
INDUSTRIES = [
    "Automotive", "Aerospace", "Electronics", "Textiles", "Food Processing",
    "Construction", "Retail", "Chemicals", "Packaging", "Energy",
]
VENDOR_CATEGORIES = [
    "raw_materials", "logistics", "software", "equipment", "maintenance", "packaging",
]
FIRST_NAMES = [
    "James", "Maria", "Wei", "Fatima", "Carlos", "Aisha", "Liam", "Priya",
    "Noah", "Elena", "Kenji", "Grace", "Omar", "Sofia", "Ivan", "Chidi",
    "Anna", "Mateo", "Ling", "David",
]
LAST_NAMES = [
    "Anderson", "Garcia", "Chen", "Khan", "Rossi", "Silva", "Muller",
    "Kim", "Nguyen", "Patel", "Kowalski", "Dubois", "Ivanov", "Adeyemi",
    "Suzuki", "Brown", "Novak", "Torres", "Larsen", "Osei",
]
PRODUCT_CATALOG: dict[str, list[str]] = {
    "Industrial Equipment": ["Industrial Pump", "Hydraulic Press", "Conveyor Motor"],
    "Raw Materials": ["Steel Sheet", "Aluminum Rod", "Copper Wire Coil"],
    "Services": ["Maintenance Service", "Installation Service", "Consulting Retainer"],
    "Software": ["ERP License", "Analytics Suite License", "Support Subscription"],
    "Packaging": ["Corrugated Box Pallet", "Shrink Wrap Roll", "Pallet Wrap"],
}
DEPARTMENT_NAMES = ["Finance", "Procurement", "Operations", "Sales", "Engineering"]
EMPLOYEE_ROLES = ["Accountant", "Buyer", "Operations Manager", "Sales Rep", "Engineer"]
EXPENSE_CATEGORIES = ["travel", "meals", "supplies", "software", "training"]
```

- [ ] **Step 6: Write `domains/finance/simulator/generator.py`** (master-data methods only — Task 10 adds the rest)

```python
from __future__ import annotations

import random
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import CustomerModel, DepartmentModel, EmployeeModel, ProductModel, VendorModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulator.constants import (
    BEHAVIOR_WEIGHTS,
    DEFAULT_SEED,
    NUM_CUSTOMERS,
    NUM_EMPLOYEES,
    NUM_VENDORS,
    PAYMENT_TERMS,
)
from domains.finance.simulator.data import (
    COMPANY_PREFIXES,
    COMPANY_SUFFIXES,
    DEPARTMENT_NAMES,
    EMPLOYEE_ROLES,
    FIRST_NAMES,
    INDUSTRIES,
    LAST_NAMES,
    PRODUCT_CATALOG,
    VENDOR_CATEGORIES,
)


class SimulatorSeeder:
    """Generates a deterministic, internally consistent Northwind Manufacturing dataset."""

    def __init__(self, db: AsyncSession, seed: int = DEFAULT_SEED) -> None:
        self._db = db
        self._rng = random.Random(seed)
        self._customers = CustomerRepository(db)
        self._vendors = VendorRepository(db)

    async def _seed_departments(self) -> list[DepartmentModel]:
        departments = []
        for name in DEPARTMENT_NAMES:
            department = DepartmentModel(id=uuid.uuid4(), name=name)
            self._db.add(department)
            departments.append(department)
        await self._db.flush()
        return departments

    async def _seed_employees(self, departments: list[DepartmentModel]) -> list[EmployeeModel]:
        employees = []
        for i in range(1, NUM_EMPLOYEES + 1):
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            department = self._rng.choice(departments)
            employee = EmployeeModel(
                id=uuid.uuid4(),
                employee_code=f"EMP-{i:04d}",
                full_name=f"{first} {last}",
                department_id=department.id,
                role=self._rng.choice(EMPLOYEE_ROLES),
                email=f"{first.lower()}.{last.lower()}@northwindmfg.example",
                status="active",
            )
            self._db.add(employee)
            employees.append(employee)
        await self._db.flush()
        return employees

    async def _seed_customers(self) -> tuple[list[CustomerModel], dict[uuid.UUID, str]]:
        customers = []
        behavior_by_customer: dict[uuid.UUID, str] = {}
        for i in range(1, NUM_CUSTOMERS + 1):
            name = f"{self._rng.choice(COMPANY_PREFIXES)} {self._rng.choice(COMPANY_SUFFIXES)}"
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            customer = await self._customers.create(
                customer_code=f"CUST-{i:04d}",
                company_name=name,
                industry=self._rng.choice(INDUSTRIES),
                contact_name=f"{first} {last}",
                contact_email=f"{first.lower()}.{last.lower()}@example.com",
                payment_terms=self._rng.choice(PAYMENT_TERMS),
                credit_limit=Decimal(self._rng.randrange(20_000, 300_000, 5_000)),
                status="active",
            )
            behavior_by_customer[customer.id] = self._rng.choice(BEHAVIOR_WEIGHTS)
            customers.append(customer)
        return customers, behavior_by_customer

    async def _seed_vendors(self) -> list[VendorModel]:
        vendors = []
        for i in range(1, NUM_VENDORS + 1):
            name = f"{self._rng.choice(COMPANY_PREFIXES)} {self._rng.choice(COMPANY_SUFFIXES)}"
            first = self._rng.choice(FIRST_NAMES)
            last = self._rng.choice(LAST_NAMES)
            vendor = await self._vendors.create(
                vendor_code=f"VEND-{i:04d}",
                company_name=name,
                category=self._rng.choice(VENDOR_CATEGORIES),
                contact_name=f"{first} {last}",
                contact_email=f"{first.lower()}.{last.lower()}@example.com",
                payment_terms=self._rng.choice(PAYMENT_TERMS),
                preferred=self._rng.random() < 0.3,
                status="active",
            )
            vendors.append(vendor)
        return vendors

    async def _seed_products(self) -> list[ProductModel]:
        products = []
        sku_num = 1
        for category, names in PRODUCT_CATALOG.items():
            for name in names:
                unit_price = Decimal(self._rng.randrange(50, 5000, 25))
                product = ProductModel(
                    id=uuid.uuid4(),
                    sku=f"SKU-{sku_num:04d}",
                    name=name,
                    category=category,
                    unit_price=unit_price,
                    is_active=True,
                )
                self._db.add(product)
                products.append(product)
                sku_num += 1
        await self._db.flush()
        return products
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_simulator_master_data.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add domains/finance/simulator/ backend/tests/test_simulator_master_data.py
git commit -m "feat: add simulator master-data generation (departments, employees, customers, vendors, products)"
```

---

## Task 10: Transactional generation — purchase orders, invoices, duplicates, payments, expense claims

**Files:**
- Modify: `domains/finance/simulator/generator.py`
- Test: `backend/tests/test_simulator_transactions.py`

**Interfaces:**
- Consumes: `PurchaseOrderRepository` (Task 6), `InvoiceRepository` + `compute_invoice_status` (Task 7), `PaymentRepository` (Task 8), the master-data methods from Task 9.
- Produces: the completed public `SimulatorSeeder.seed() -> None` method — the one entry point Task 11's CLI calls.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_simulator_transactions.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    ExpenseClaimModel,
    InvoiceModel,
    PaymentModel,
    PurchaseOrderModel,
)
from domains.finance.simulator.constants import (
    NUM_DUPLICATE_INVOICES,
    NUM_INVOICES,
    NUM_PURCHASE_ORDERS,
    SIMULATION_TODAY,
)
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_seed_produces_expected_scale(clean_db: None, db_session: AsyncSession) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    po_count = (await db_session.execute(select(func.count()).select_from(PurchaseOrderModel))).scalar_one()
    invoice_count = (await db_session.execute(select(func.count()).select_from(InvoiceModel))).scalar_one()
    payment_count = (await db_session.execute(select(func.count()).select_from(PaymentModel))).scalar_one()
    expense_count = (await db_session.execute(select(func.count()).select_from(ExpenseClaimModel))).scalar_one()

    assert po_count == NUM_PURCHASE_ORDERS
    assert invoice_count == NUM_INVOICES + NUM_DUPLICATE_INVOICES
    assert payment_count > 0
    assert expense_count > 0


@pytest.mark.asyncio
async def test_seed_invoices_all_reference_real_customers(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    invoices = (await db_session.execute(select(InvoiceModel))).scalars().all()
    for invoice in invoices:
        assert invoice.total == invoice.subtotal + invoice.tax
        assert invoice.balance == invoice.total - invoice.amount_paid


@pytest.mark.asyncio
async def test_seed_creates_duplicate_invoices_sharing_customer_and_po(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    duplicates = (
        await db_session.execute(
            select(InvoiceModel).where(InvoiceModel.invoice_number.like("INV-9%"))
        )
    ).scalars().all()
    assert len(duplicates) == NUM_DUPLICATE_INVOICES
    for duplicate in duplicates:
        assert duplicate.purchase_order_id is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_simulator_transactions.py -v`
Expected: FAIL with `AttributeError: 'SimulatorSeeder' object has no attribute 'seed'`

- [ ] **Step 3: Extend `domains/finance/simulator/generator.py`**

Add these imports to the top of the file (merge with the existing import block from Task 9):

```python
from datetime import date, datetime, timedelta

from sqlalchemy import select

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
from domains.finance.repositories.invoice_repository import InvoiceRepository, compute_invoice_status
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.simulator.constants import (
    BEHAVIOR_DAYS_OFFSET,
    EXPENSE_STATUSES,
    INVOICE_WINDOW_MONTHS,
    NUM_DUPLICATE_INVOICES,
    NUM_EXPENSE_CLAIMS_PER_EMPLOYEE,
    NUM_INVOICES,
    NUM_PURCHASE_ORDERS,
    PAYMENT_COVERAGE,
    PAYMENT_METHODS,
    PAYMENT_TERMS_DAYS,
    SIMULATION_TODAY,
)
from domains.finance.simulator.data import EXPENSE_CATEGORIES
```

Add `self._purchase_orders = PurchaseOrderRepository(db)`, `self._invoices = InvoiceRepository(db)`, and `self._payments = PaymentRepository(db)` to `__init__` (alongside the existing `self._customers`/`self._vendors` lines).

Add the public entry point and remaining private methods to the `SimulatorSeeder` class:

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
        await self._seed_expense_claims(employees)
        await self._db.flush()

    async def _seed_purchase_orders(
        self,
        vendors: list[VendorModel],
        products: list[ProductModel],
        employees: list[EmployeeModel],
    ) -> list[PurchaseOrderModel]:
        purchase_orders = []
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        for i in range(1, NUM_PURCHASE_ORDERS + 1):
            vendor = self._rng.choice(vendors)
            order_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
            status = self._rng.choices(
                ["received", "approved", "draft", "cancelled"], weights=[60, 25, 10, 5], k=1
            )[0]
            approver = self._rng.choice(employees) if status in ("approved", "received") else None
            chosen_products = self._rng.sample(products, k=self._rng.randint(1, 4))
            item_specs = [(product, self._rng.randint(1, 50)) for product in chosen_products]
            total_amount = sum(
                (product.unit_price * quantity for product, quantity in item_specs),
                start=Decimal("0"),
            )
            po = await self._purchase_orders.create(
                po_number=f"PO-{1000 + i}",
                vendor_id=vendor.id,
                order_date=order_date,
                status=status,
                approved_by=approver.id if approver else None,
                approved_at=datetime.combine(order_date, datetime.min.time()) if approver else None,
                total_amount=total_amount,
            )
            for product, quantity in item_specs:
                self._db.add(
                    PurchaseOrderItemModel(
                        id=uuid.uuid4(),
                        purchase_order_id=po.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.unit_price,
                        subtotal=product.unit_price * quantity,
                    )
                )
            purchase_orders.append(po)
        await self._db.flush()
        return purchase_orders

    async def _seed_invoices(
        self,
        customers: list[CustomerModel],
        purchase_orders: list[PurchaseOrderModel],
        products: list[ProductModel],
    ) -> list[InvoiceModel]:
        invoices = []
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        po_linkable = [po for po in purchase_orders if po.status in ("approved", "received")]
        for i in range(1, NUM_INVOICES + 1):
            customer = self._rng.choice(customers)
            issue_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
            due_date = issue_date + timedelta(days=PAYMENT_TERMS_DAYS[customer.payment_terms])
            po = (
                self._rng.choice(po_linkable)
                if po_linkable and self._rng.random() < 0.4
                else None
            )
            chosen_products = self._rng.sample(products, k=self._rng.randint(1, 3))
            item_specs = [(product, self._rng.randint(1, 10)) for product in chosen_products]
            subtotal = sum((p.unit_price * q for p, q in item_specs), start=Decimal("0"))
            tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
            total = subtotal + tax
            is_draft = i > NUM_INVOICES - 3
            status = compute_invoice_status(
                total=total,
                amount_paid=Decimal("0"),
                due_date=due_date,
                as_of=SIMULATION_TODAY,
                current_status="draft" if is_draft else "sent",
            )
            invoice = await self._invoices.create(
                invoice_number=f"INV-{7000 + i}",
                customer_id=customer.id,
                purchase_order_id=po.id if po else None,
                issue_date=issue_date,
                due_date=due_date,
                status=status,
                subtotal=subtotal,
                tax=tax,
                total=total,
            )
            for product, quantity in item_specs:
                self._db.add(
                    InvoiceItemModel(
                        id=uuid.uuid4(),
                        invoice_id=invoice.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.unit_price,
                        tax=(product.unit_price * quantity * Decimal("0.08")).quantize(Decimal("0.01")),
                        discount=Decimal("0"),
                        subtotal=product.unit_price * quantity,
                    )
                )
            invoices.append(invoice)
        await self._db.flush()
        return invoices

    async def _seed_duplicate_invoices(self, invoices: list[InvoiceModel]) -> None:
        po_linked = [
            invoice
            for invoice in invoices
            if invoice.purchase_order_id is not None and invoice.status != "cancelled"
        ]
        sample_size = min(NUM_DUPLICATE_INVOICES, len(po_linked))
        duplicates_source = self._rng.sample(po_linked, k=sample_size)
        for i, original in enumerate(duplicates_source, start=1):
            dup_issue_date = original.issue_date + timedelta(days=self._rng.choice([0, 1]))
            status = compute_invoice_status(
                total=original.total,
                amount_paid=Decimal("0"),
                due_date=original.due_date,
                as_of=SIMULATION_TODAY,
                current_status="sent",
            )
            duplicate = await self._invoices.create(
                invoice_number=f"INV-9{i:03d}",
                customer_id=original.customer_id,
                purchase_order_id=original.purchase_order_id,
                issue_date=dup_issue_date,
                due_date=original.due_date,
                status=status,
                subtotal=original.subtotal,
                tax=original.tax,
                total=original.total,
            )
            original_items = (
                await self._db.execute(
                    select(InvoiceItemModel).where(InvoiceItemModel.invoice_id == original.id)
                )
            ).scalars().all()
            for item in original_items:
                self._db.add(
                    InvoiceItemModel(
                        id=uuid.uuid4(),
                        invoice_id=duplicate.id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        tax=item.tax,
                        discount=item.discount,
                        subtotal=item.subtotal,
                    )
                )
            invoices.append(duplicate)
        await self._db.flush()

    async def _seed_payments(
        self, invoices: list[InvoiceModel], behavior_by_customer: dict[uuid.UUID, str]
    ) -> None:
        payable = [invoice for invoice in invoices if invoice.status not in ("draft", "cancelled")]
        target_count = int(len(payable) * PAYMENT_COVERAGE)
        paid_candidates = self._rng.sample(payable, k=min(target_count, len(payable)))
        for invoice in paid_candidates:
            behavior = behavior_by_customer.get(invoice.customer_id, "average")
            low, high = BEHAVIOR_DAYS_OFFSET[behavior]
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
            await self._payments.record_payment(
                invoice_id=invoice.id,
                payment_date=payment_date,
                amount=amount,
                payment_method=self._rng.choice(PAYMENT_METHODS),
                reference_number=f"PMT-{uuid.uuid4().hex[:10].upper()}",
                today=SIMULATION_TODAY,
            )

    async def _seed_expense_claims(self, employees: list[EmployeeModel]) -> None:
        window_start = SIMULATION_TODAY - timedelta(days=INVOICE_WINDOW_MONTHS * 30)
        window_days = (SIMULATION_TODAY - window_start).days
        claim_num = 1
        for employee in employees:
            for _ in range(NUM_EXPENSE_CLAIMS_PER_EMPLOYEE):
                submitted_date = window_start + timedelta(days=self._rng.randrange(0, window_days))
                status = self._rng.choices(list(EXPENSE_STATUSES), weights=[10, 30, 10, 50], k=1)[0]
                category = self._rng.choice(EXPENSE_CATEGORIES)
                self._db.add(
                    ExpenseClaimModel(
                        id=uuid.uuid4(),
                        claim_number=f"EXP-{claim_num:05d}",
                        employee_id=employee.id,
                        category=category,
                        amount=Decimal(self._rng.randrange(20, 2000, 10)),
                        description=f"{category.title()} expense",
                        submitted_date=submitted_date,
                        status=status,
                    )
                )
                claim_num += 1
        await self._db.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_simulator_transactions.py -v`
Expected: PASS (3 tests). If `test_seed_produces_expected_scale` fails on `payment_count > 0` or similar, double check `_seed_payments` is being reached — a common mistake is forgetting to add the new imports/repository instances to `__init__`.

- [ ] **Step 5: Run ruff and mypy**

Run (from `backend/`): `.venv/Scripts/python -m ruff check . ../ai_platform ../domains && .venv/Scripts/python -m mypy app alembic ../ai_platform ../domains`
Expected: clean. A likely finding: unused `DepartmentModel`/`CustomerModel` imports if not referenced directly by type — keep only what's used in type hints/isinstance checks.

- [ ] **Step 6: Commit**

```bash
git add domains/finance/simulator/generator.py backend/tests/test_simulator_transactions.py
git commit -m "feat: add transactional simulator generation (POs, invoices, duplicates, payments, expense claims)"
```

---

## Task 11: `seed.py` CLI

**Files:**
- Create: `domains/finance/simulator/seed.py`
- Test: `backend/tests/test_seed_cli.py`

**Interfaces:**
- Consumes: `SimulatorSeeder` (Task 10), `get_engine`/`get_sessionmaker` from `app.db.session`.
- Produces: `async def run_seed(reset: bool, seed: int) -> None` (the testable core) and `def main() -> None` (argparse wrapper, `if __name__ == "__main__": main()`). Invoked as `python -m domains.finance.simulator.seed --reset`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_seed_cli.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import CustomerModel
from domains.finance.simulator.seed import run_seed


@pytest.mark.asyncio
async def test_run_seed_populates_customers(clean_db: None, db_session: AsyncSession) -> None:
    await run_seed(reset=True, seed=42)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as verify_session:
        count = (
            await verify_session.execute(select(func.count()).select_from(CustomerModel))
        ).scalar_one()
    assert count == 25


@pytest.mark.asyncio
async def test_run_seed_refuses_without_reset_when_data_exists(
    clean_db: None, db_session: AsyncSession
) -> None:
    await run_seed(reset=True, seed=42)

    with pytest.raises(SystemExit):
        await run_seed(reset=False, seed=42)
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_seed_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.simulator.seed'`

- [ ] **Step 3: Write `domains/finance/simulator/seed.py`**

```python
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.db.session import get_engine, get_sessionmaker
from domains.finance.simulator.constants import DEFAULT_SEED
from domains.finance.simulator.generator import SimulatorSeeder

FINANCE_TABLES = (
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


async def run_seed(reset: bool, seed: int) -> None:
    engine = get_engine()
    if reset:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE TABLE {', '.join(FINANCE_TABLES)} CASCADE"))
    else:
        async with engine.connect() as conn:
            existing = await conn.execute(text("SELECT COUNT(*) FROM finance.customers"))
            if existing.scalar_one() > 0:
                print(
                    "finance.customers already has data. Re-run with --reset to replace it.",
                    file=sys.stderr,
                )
                sys.exit(1)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        seeder = SimulatorSeeder(session, seed=seed)
        await seeder.seed()
        await session.commit()
    print(f"Seeded Northwind Manufacturing Ltd. (seed={seed}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Finance Simulation Environment.")
    parser.add_argument(
        "--reset", action="store_true", help="Truncate finance tables before seeding."
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})."
    )
    args = parser.parse_args()
    asyncio.run(run_seed(reset=args.reset, seed=args.seed))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_seed_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Manually verify the actual CLI command from the acceptance criteria**

Run (from `backend/`): `.venv/Scripts/python -m domains.finance.simulator.seed --reset`
Expected: prints `Seeded Northwind Manufacturing Ltd. (seed=42).` with no errors. (This requires `domains` to be on `sys.path` — it is, via the repo-root `.pth` file the editable install already wrote to `.venv/Lib/site-packages`; confirm with `.venv/Scripts/python -c "import domains; print('ok')"` first if this step fails.)

- [ ] **Step 6: Commit**

```bash
git add domains/finance/simulator/seed.py backend/tests/test_seed_cli.py
git commit -m "feat: add seed.py CLI (python -m domains.finance.simulator.seed --reset)"
```

---

## Task 12: `consistency_check.py`

**Files:**
- Create: `domains/finance/simulator/consistency_check.py`
- Test: `backend/tests/test_consistency_check.py`

**Interfaces:**
- Consumes: all finance models, `SIMULATION_TODAY` from `domains.finance.simulator.constants`.
- Produces: `async def run_consistency_check(db: AsyncSession) -> list[str]` (importable directly by tests) and an `if __name__ == "__main__"` CLI entry printing violations and exiting non-zero if any exist. Invoked as `python -m domains.finance.simulator.consistency_check`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_consistency_check.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.simulator.consistency_check import run_consistency_check
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_freshly_seeded_data_has_no_violations(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert violations == []


@pytest.mark.asyncio
async def test_detects_a_deliberately_broken_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-0001", company_name="Broken Co", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number="INV-9999", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    invoice.balance = Decimal("999.00")  # deliberately wrong -- should equal total (100) minus 0 payments
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("balance" in v for v in violations)
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_consistency_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.finance.simulator.consistency_check'`

- [ ] **Step 3: Write `domains/finance/simulator/consistency_check.py`**

```python
from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorModel,
)
from domains.finance.simulator.constants import SIMULATION_TODAY


async def run_consistency_check(db: AsyncSession) -> list[str]:
    violations: list[str] = []

    customer_ids = set((await db.execute(select(CustomerModel.id))).scalars().all())
    vendor_ids = set((await db.execute(select(VendorModel.id))).scalars().all())
    product_ids = set((await db.execute(select(ProductModel.id))).scalars().all())
    department_ids = set((await db.execute(select(DepartmentModel.id))).scalars().all())
    purchase_orders = {po.id: po for po in (await db.execute(select(PurchaseOrderModel))).scalars().all()}
    invoices = list((await db.execute(select(InvoiceModel))).scalars().all())
    invoice_ids = {invoice.id for invoice in invoices}

    for invoice in invoices:
        if invoice.customer_id not in customer_ids:
            violations.append(
                f"Invoice {invoice.invoice_number} references missing customer {invoice.customer_id}"
            )
        if invoice.purchase_order_id is not None and invoice.purchase_order_id not in purchase_orders:
            violations.append(
                f"Invoice {invoice.invoice_number} references missing purchase order "
                f"{invoice.purchase_order_id}"
            )

    for po in purchase_orders.values():
        if po.vendor_id not in vendor_ids:
            violations.append(f"Purchase order {po.po_number} references missing vendor {po.vendor_id}")

    invoice_items = (await db.execute(select(InvoiceItemModel))).scalars().all()
    for item in invoice_items:
        if item.invoice_id not in invoice_ids:
            violations.append(f"Invoice item {item.id} references missing invoice {item.invoice_id}")
        if item.product_id not in product_ids:
            violations.append(f"Invoice item {item.id} references missing product {item.product_id}")

    po_items = (await db.execute(select(PurchaseOrderItemModel))).scalars().all()
    for item in po_items:
        if item.purchase_order_id not in purchase_orders:
            violations.append(
                f"Purchase order item {item.id} references missing purchase order "
                f"{item.purchase_order_id}"
            )
        if item.product_id not in product_ids:
            violations.append(f"Purchase order item {item.id} references missing product {item.product_id}")

    employees = (await db.execute(select(EmployeeModel))).scalars().all()
    for employee in employees:
        if employee.department_id not in department_ids:
            violations.append(
                f"Employee {employee.employee_code} references missing department "
                f"{employee.department_id}"
            )

    payments = (await db.execute(select(PaymentModel))).scalars().all()
    payments_by_invoice: dict[uuid.UUID, Decimal] = {}
    for payment in payments:
        if payment.invoice_id not in invoice_ids:
            violations.append(f"Payment {payment.id} references missing invoice {payment.invoice_id}")
            continue
        payments_by_invoice[payment.invoice_id] = (
            payments_by_invoice.get(payment.invoice_id, Decimal("0")) + payment.amount
        )

    for invoice in invoices:
        paid_total = payments_by_invoice.get(invoice.id, Decimal("0"))
        expected_balance = invoice.total - paid_total
        if invoice.balance != expected_balance:
            violations.append(
                f"Invoice {invoice.invoice_number} balance {invoice.balance} != total "
                f"{invoice.total} - payments {paid_total} = {expected_balance}"
            )

        if invoice.status == "cancelled":
            continue
        is_past_due_unpaid = invoice.due_date < SIMULATION_TODAY and invoice.balance > 0
        if invoice.status != "draft" and is_past_due_unpaid and invoice.status != "overdue":
            violations.append(
                f"Invoice {invoice.invoice_number} is past due with balance {invoice.balance} "
                f"but status is {invoice.status!r}, expected 'overdue'"
            )
        if invoice.status == "overdue" and not is_past_due_unpaid:
            violations.append(
                f"Invoice {invoice.invoice_number} has status 'overdue' but its due date/balance "
                "don't justify it"
            )

    return violations


async def _main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        violations = await run_consistency_check(session)
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        print(f"\n{len(violations)} consistency violation(s) found.", file=sys.stderr)
        sys.exit(1)
    print("Consistency check passed: 0 violations.")


if __name__ == "__main__":
    asyncio.run(_main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_consistency_check.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Manually verify the actual CLI command from the acceptance criteria**

Run (from `backend/`, after re-seeding with `--reset` since Task 11's tests may have left the DB in a mixed state):
```bash
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.consistency_check
```
Expected: `Consistency check passed: 0 violations.` and exit code `0` (check with `echo $?` in bash or `echo %errorlevel%` in cmd).

- [ ] **Step 6: Commit**

```bash
git add domains/finance/simulator/consistency_check.py backend/tests/test_consistency_check.py
git commit -m "feat: add consistency_check.py"
```

---

## Task 13: Seed repeatability test

**Files:**
- Test: `backend/tests/test_seed_repeatability.py`

**Interfaces:**
- Consumes: `SimulatorSeeder` (Task 10).
- Produces: nothing new — this is a pure test task proving the milestone's "same seed → same data" requirement holds across a full truncate-and-reseed cycle, not just within a single generator instance (which Task 9's determinism test already covered for master data only).

- [ ] **Step 1: Write the test**

Create `backend/tests/test_seed_repeatability.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    CustomerModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderModel,
    VendorModel,
)
from domains.finance.simulator.generator import SimulatorSeeder

FINANCE_TABLES = (
    "finance.payments", "finance.invoice_items", "finance.invoices",
    "finance.purchase_order_items", "finance.purchase_orders", "finance.expense_claims",
    "finance.employees", "finance.departments", "finance.products",
    "finance.customers", "finance.vendors",
)


async def _snapshot(db_session: AsyncSession) -> dict[str, object]:
    counts = {}
    for model in (
        CustomerModel, VendorModel, ProductModel, EmployeeModel,
        PurchaseOrderModel, InvoiceModel, PaymentModel, ExpenseClaimModel,
    ):
        counts[model.__tablename__] = (
            await db_session.execute(select(func.count()).select_from(model))
        ).scalar_one()

    invoiced_by_customer: dict[str, Decimal] = {}
    rows = (
        await db_session.execute(
            select(CustomerModel.customer_code, InvoiceModel.total)
            .join(InvoiceModel, InvoiceModel.customer_id == CustomerModel.id)
        )
    ).all()
    for customer_code, total in rows:
        invoiced_by_customer[customer_code] = invoiced_by_customer.get(customer_code, Decimal("0")) + total

    return {"counts": counts, "invoiced_by_customer": invoiced_by_customer}


@pytest.mark.asyncio
async def test_same_seed_produces_identical_data(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder_a = SimulatorSeeder(db_session, seed=42)
    await seeder_a.seed()
    await db_session.commit()
    snapshot_a = await _snapshot(db_session)

    async with db_session.begin():
        await db_session.execute(text(f"TRUNCATE TABLE {', '.join(FINANCE_TABLES)} CASCADE"))

    seeder_b = SimulatorSeeder(db_session, seed=42)
    await seeder_b.seed()
    await db_session.commit()
    snapshot_b = await _snapshot(db_session)

    assert snapshot_a == snapshot_b
```

- [ ] **Step 2: Run test to verify it passes**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_seed_repeatability.py -v`
Expected: PASS. If it fails, the most likely cause is a source of non-determinism in `generator.py` — grep for any `datetime.now()`, `date.today()`, `uuid.uuid4()` used for anything other than a primary key, or dict iteration order depending on insertion order across runs (dicts are insertion-ordered in Python 3.7+, so this is unlikely, but double check `PRODUCT_CATALOG` iteration).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_seed_repeatability.py
git commit -m "test: verify seed repeatability across a full truncate-and-reseed cycle"
```

---

## Task 14: Full verification pass and HANDOFF.md update

**Files:**
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: nothing new — this task only runs and verifies everything built in Tasks 1-13.

- [ ] **Step 1: Run the full backend test suite**

Run (from `backend/`): `.venv/Scripts/python -m pytest -v`
Expected: all tests PASS (Milestones 1-3's pre-existing tests plus every test added in this plan).

- [ ] **Step 2: Run lint and type checks**

Run (from `backend/`):
```bash
.venv/Scripts/python -m ruff check . ../ai_platform ../domains
.venv/Scripts/python -m mypy app alembic ../ai_platform ../domains
```
Expected: both clean.

- [ ] **Step 3: Re-verify the acceptance criteria end to end from a clean slate**

Run (from `backend/`):
```bash
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python -m domains.finance.simulator.consistency_check
```
Expected: `Seeded Northwind Manufacturing Ltd. (seed=42).` then `Consistency check passed: 0 violations.` — this is the milestone's literal acceptance criterion.

- [ ] **Step 4: Spot-check the seeded data with a raw query**

Run (from `backend/`):
```bash
.venv/Scripts/python -c "
import asyncio
from sqlalchemy import text
from app.db.session import get_engine

async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        for label, query in [
            ('customers', 'SELECT count(*) FROM finance.customers'),
            ('invoices', 'SELECT count(*) FROM finance.invoices'),
            ('overdue', \"SELECT count(*) FROM finance.invoices WHERE status = 'overdue'\"),
            ('payments', 'SELECT count(*) FROM finance.payments'),
        ]:
            result = await conn.execute(text(query))
            print(label, result.scalar_one())
    await engine.dispose()

asyncio.run(main())
"
```
Expected: `customers 25`, `invoices` around 205 (200 + 5 duplicates), `overdue` some positive number, `payments` some positive number well below the invoice count (since ~70% coverage across ~205 invoices, minus the drafts/cancelled excluded from payment eligibility).

- [ ] **Step 5: Update `HANDOFF.md`**

Update the header line and rewrite the sections to reflect Milestone 4 completion, following the exact structure of the existing Milestone 3 entry (§1 Current State, §2 Work Completed, §3 In-Progress, §4 Decisions Made, §5 Known Issues, §6 Do NOT Do, §7 Next Steps). At minimum:
- Change line 2 to: `Last updated: <today's date> | Current milestone: 4 — Finance Simulation Environment | Status: complete`
- §1: note `finance` + `evaluation` schemas exist, seed/consistency-check commands verified, full test suite pass count.
- §2: summarize the 11 models, 5 repositories, `SimulatorSeeder`, `seed.py`/`consistency_check.py` CLIs, and the `compute_invoice_status` priority rule as the one real piece of business logic in this milestone.
- §4: record the `SIMULATION_TODAY` fixed-anchor decision and the adapter-layer/persona/scenario-pack scope exclusions from the design spec, so the next session doesn't reintroduce them prematurely.
- §7: point at Milestone 5 (Finance Tool Architecture / Accounts Receivable tools) per the existing roadmap this plan didn't change.

- [ ] **Step 6: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: update HANDOFF.md for Milestone 4 completion"
```

---

## Self-Review Notes

**Spec coverage:** All 11 tables (§1 of spec) → Tasks 1-4. Repositories (§4 of spec) → Tasks 5-8. Seed generator (§3 of spec) → Tasks 9-11. Consistency check (§3 of spec) → Task 12. Testing plan (§5 of spec) → Tasks 9, 10, 13, plus repository tests in Tasks 5-8. Acceptance criteria → Task 14.

**Type consistency verified:** `compute_invoice_status` signature (Task 7) is identical everywhere it's called: `PaymentRepository.record_payment` (Task 8), `_seed_invoices`/`_seed_duplicate_invoices` (Task 10). `SimulatorSeeder._seed_customers()` returns `tuple[list[CustomerModel], dict[uuid.UUID, str]]` consistently from Task 9 (definition) through Task 10 (`seed()` unpacking it) and Task 9's own test. `record_payment`'s `today: date | None` parameter is threaded consistently from Task 8's tests through Task 10's `_seed_payments` call.
