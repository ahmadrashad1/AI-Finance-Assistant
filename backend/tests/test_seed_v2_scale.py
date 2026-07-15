from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    BankAccountModel,
    BankTransactionModel,
    BudgetModel,
    ClosePeriodModel,
    CloseTaskModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    FixedAssetModel,
    PayrollRunModel,
    PurchaseOrderModel,
    PurchaseRequisitionModel,
    TaxPeriodModel,
    TaxRateModel,
)
from domains.finance.simulation import simulation_today
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2


@pytest.fixture
async def seeded_company(clean_db: None, db_session: AsyncSession) -> dict:
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()
    return expectations


async def _count(db_session: AsyncSession, model: type) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(model))
    ).scalar_one()


@pytest.mark.asyncio
async def test_seed_scale_matches_prd_chapter_19(
    seeded_company: dict, db_session: AsyncSession
) -> None:
    assert 6 <= await _count(db_session, DepartmentModel) <= 8
    assert 40 <= await _count(db_session, EmployeeModel) <= 60
    assert 60 <= await _count(db_session, PurchaseRequisitionModel) <= 80
    assert await _count(db_session, PurchaseOrderModel) >= 40
    assert 250 <= await _count(db_session, ExpenseClaimModel) <= 350
    assert 2 <= await _count(db_session, BankAccountModel) <= 3
    assert 600 <= await _count(db_session, BankTransactionModel) <= 900
    assert 40 <= await _count(db_session, FixedAssetModel) <= 60
    assert await _count(db_session, PayrollRunModel) == 18
    assert await _count(db_session, ClosePeriodModel) == 18
    assert await _count(db_session, TaxPeriodModel) == 6
    assert await _count(db_session, TaxRateModel) >= 1
    # Budget lines: every department x category x month of the window.
    departments = await _count(db_session, DepartmentModel)
    assert await _count(db_session, BudgetModel) == departments * 7 * 18


@pytest.mark.asyncio
async def test_most_recent_close_period_is_open(
    seeded_company: dict, db_session: AsyncSession
) -> None:
    periods = (
        await db_session.execute(
            select(ClosePeriodModel).order_by(ClosePeriodModel.period)
        )
    ).scalars().all()
    assert [p.status for p in periods[:-1]] == ["closed"] * (len(periods) - 1)
    assert periods[-1].status == "open"
    statuses = {
        task.status
        for task in (
            await db_session.execute(
                select(CloseTaskModel).where(
                    CloseTaskModel.close_period_id == periods[-1].id
                )
            )
        ).scalars().all()
    }
    assert {"completed", "in_progress", "blocked"} <= statuses


@pytest.mark.asyncio
async def test_expectations_cover_every_planted_anomaly(seeded_company: dict) -> None:
    expected_keys = {
        "duplicate_invoices",
        "over_limit_expense_claims",
        "missing_receipt_expense_claims",
        "late_submission_expense_claims",
        "self_approved_expense_claims",
        "duplicate_expense_claims",
        "unmatched_bank_transactions",
        "unmirrored_internal_payments",
        "maverick_purchase_orders",
        "price_variance_products",
        "deteriorating_customer",
        "over_budget_departments",
        "under_budget_department",
        "category_overspend",
        "fully_depreciated_assets_in_use",
        "unapproved_payment_above_threshold",
    }
    assert expected_keys <= set(seeded_company.keys())
    assert seeded_company["self_approved_expense_claims"]["count"] == 1
    assert seeded_company["unmatched_bank_transactions"]["count"] >= 1
    assert seeded_company["maverick_purchase_orders"]["count"] >= 1
    assert seeded_company["simulation_date"] == simulation_today().isoformat()
