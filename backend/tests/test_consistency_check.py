from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from domains.finance.models import (
    BankTransactionModel,
    ClosePeriodModel,
    ExpenseClaimModel,
    FixedAssetModel,
    PayrollRunModel,
    PurchaseOrderModel,
)
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.simulator.consistency_check import run_consistency_check
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2


@pytest.fixture
async def seeded_expectations(clean_db: None, db_session: AsyncSession) -> dict:
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()
    return expectations


@pytest.mark.asyncio
async def test_freshly_seeded_data_has_no_violations(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    violations = await run_consistency_check(db_session, seeded_expectations)
    assert violations == []


@pytest.mark.asyncio
async def test_detects_self_approved_claim_outside_expectations(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    claim = (
        await db_session.execute(
            select(ExpenseClaimModel).where(ExpenseClaimModel.status == "approved")
            .order_by(ExpenseClaimModel.claim_number)
        )
    ).scalars().first()
    assert claim is not None
    claim.approver_id = claim.employee_id
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("Self-approved claims" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_payroll_totals_that_disagree_with_lines(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    run = (
        await db_session.execute(select(PayrollRunModel).order_by(PayrollRunModel.period))
    ).scalars().first()
    assert run is not None
    run.total_net = run.total_net + Decimal("1.00")
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("totals disagree" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_matched_bank_transaction_without_a_link(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    line = (
        await db_session.execute(
            select(BankTransactionModel).where(
                BankTransactionModel.matched_payment_id.is_not(None)
            )
        )
    ).scalars().first()
    assert line is not None
    line.matched_payment_id = None
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("'matched' but has 0 match links" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_a_maverick_po_that_is_not_in_expectations(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    po = (
        await db_session.execute(
            select(PurchaseOrderModel)
            .where(PurchaseOrderModel.requisition_id.is_not(None))
            .order_by(PurchaseOrderModel.po_number)
        )
    ).scalars().first()
    assert po is not None
    po.requisition_id = None
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("Maverick POs" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_an_asset_with_salvage_above_cost(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    asset = (
        await db_session.execute(
            select(FixedAssetModel).order_by(FixedAssetModel.asset_tag)
        )
    ).scalars().first()
    assert asset is not None
    asset.salvage_value = asset.purchase_cost + Decimal("1.00")
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("salvage >= cost" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_two_open_close_periods(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    periods = (
        await db_session.execute(
            select(ClosePeriodModel).order_by(ClosePeriodModel.period)
        )
    ).scalars().all()
    periods[0].status = "open"
    periods[0].closed_date = None
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("is not closed" in v for v in violations)


@pytest.mark.asyncio
async def test_detects_policy_violation_drift_on_a_claim(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    over_limit_numbers = seeded_expectations["over_limit_expense_claims"]["claim_numbers"]
    claim = (
        await db_session.execute(
            select(ExpenseClaimModel).where(
                ExpenseClaimModel.claim_number == over_limit_numbers[0]
            )
        )
    ).scalars().one()
    claim.policy_violations = []
    await db_session.flush()

    violations = await run_consistency_check(db_session, seeded_expectations)
    assert any("policy_violations" in v and claim.claim_number in v for v in violations)


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
