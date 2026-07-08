from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models.expenses import ExpenseClaimModel
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
    # Deliberately wrong -- should equal total (100) minus 0 payments.
    invoice.balance = Decimal("999.00")
    await db_session.commit()

    violations = await run_consistency_check(db_session)
    assert any("balance" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_an_expense_claim_with_a_missing_employee(
    clean_db: None, db_session: AsyncSession
) -> None:
    # The `employee_id` FK is enforced at the DB level, so a genuinely
    # orphaned row can't be inserted through the ORM as-is. Drop the
    # constraint within this session's (uncommitted) transaction only --
    # never `commit()` here, so the `db_session` fixture's teardown rolls
    # both the ALTER TABLE and the INSERT back automatically, leaving the
    # schema untouched for every other test even if an assertion below
    # fails.
    await db_session.execute(
        text(
            "ALTER TABLE finance.expense_claims "
            "DROP CONSTRAINT expense_claims_employee_id_fkey"
        )
    )
    missing_employee_id = uuid.uuid4()
    claim = ExpenseClaimModel(
        claim_number="EXP-9999",
        employee_id=missing_employee_id,
        category="Travel",
        amount=Decimal("50.00"),
        description="Taxi fare",
        submitted_date=date(2026, 1, 1),
        status="submitted",
    )
    db_session.add(claim)
    await db_session.flush()

    violations = await run_consistency_check(db_session)
    assert any(
        "EXP-9999" in v and str(missing_employee_id) in v for v in violations
    )
