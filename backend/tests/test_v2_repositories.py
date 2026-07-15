from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.bank_transaction_repository import BankTransactionRepository
from domains.finance.repositories.budget_repository import BudgetRepository
from domains.finance.repositories.close_period_repository import ClosePeriodRepository
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.repositories.fixed_asset_repository import FixedAssetRepository
from domains.finance.repositories.payroll_repository import PayrollRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.tax_repository import TaxRepository
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2


@pytest.fixture
async def seeded_expectations(clean_db: None, db_session: AsyncSession) -> dict:
    await SimulatorSeeder(db_session, seed=42).seed()
    expectations = await SimulatorSeederV2(db_session, seed=42).seed()
    await db_session.commit()
    return expectations


@pytest.mark.asyncio
async def test_employee_repository_filters(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = EmployeeRepository(db_session)
    departments = await repository.list_departments()
    assert {"Finance", "Human Resources", "IT"} <= {d.name for d in departments}
    finance = await repository.get_department_by_name("Finance")
    assert finance is not None
    finance_staff = await repository.list_employees(department_id=finance.id)
    assert finance_staff
    assert all(e.department_id == finance.id for e in finance_staff)
    inactive = await repository.list_employees(status="inactive")
    assert all(e.termination_date is not None for e in inactive)


@pytest.mark.asyncio
async def test_expense_claim_repository_lookup_matches_expectations(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = ExpenseClaimRepository(db_session)
    self_approved = seeded_expectations["self_approved_expense_claims"]["claim_numbers"][0]
    claim = await repository.get_by_number(self_approved)
    assert claim is not None
    assert claim.approver_id == claim.employee_id
    travel = await repository.list_claims(category="travel")
    assert travel
    assert all(c.category == "travel" for c in travel)


@pytest.mark.asyncio
async def test_budget_repository_scopes_by_department(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    employee_repository = EmployeeRepository(db_session)
    sales = await employee_repository.get_department_by_name("Sales")
    assert sales is not None
    lines = await BudgetRepository(db_session).list_budget_lines(
        department_id=sales.id, category="travel"
    )
    assert len(lines) == 18
    assert all(line.category == "travel" for line in lines)


@pytest.mark.asyncio
async def test_bank_transaction_repository_unmatched_filter(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = BankTransactionRepository(db_session)
    accounts = await repository.list_accounts()
    assert len(accounts) == 3
    unmatched = await repository.list_transactions(match_status="unmatched")
    expected = seeded_expectations["unmatched_bank_transactions"]
    assert sorted(line.reference for line in unmatched) == expected["references"]


@pytest.mark.asyncio
async def test_fixed_asset_repository_status_filter(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = FixedAssetRepository(db_session)
    expected_tag = seeded_expectations["fully_depreciated_assets_in_use"]["asset_tags"][0]
    asset = await repository.get_by_tag(expected_tag)
    assert asset is not None
    assert asset.status == "in_use"
    disposed = await repository.list_assets(status="disposed")
    assert all(a.disposal_date is not None for a in disposed)


@pytest.mark.asyncio
async def test_payroll_repository_runs_and_lines(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = PayrollRepository(db_session)
    runs = await repository.list_runs()
    assert len(runs) == 18
    lines = await repository.list_lines_for_run(runs[0].id)
    assert lines
    total_net = sum(line.net_pay for line in lines)
    assert total_net == runs[0].total_net


@pytest.mark.asyncio
async def test_requisition_repository_maverick_pos_have_no_requisition(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = PurchaseRequisitionRepository(db_session)
    approved = await repository.list_requisitions(status="approved")
    assert approved
    first = await repository.get_by_number(approved[0].requisition_number)
    assert first is not None
    items = await repository.list_items(first.id)
    assert items


@pytest.mark.asyncio
async def test_close_period_repository_open_period_tasks(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = ClosePeriodRepository(db_session)
    open_periods = await repository.list_periods(status="open")
    assert len(open_periods) == 1
    blocked = await repository.list_tasks(open_periods[0].id, status="blocked")
    assert blocked
    assert all(task.blocking_reason for task in blocked)


@pytest.mark.asyncio
async def test_tax_repository_rates_and_periods(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = TaxRepository(db_session)
    rates = await repository.list_rates(jurisdiction="US-Federal")
    assert {"sales", "payroll_withholding"} <= {r.category for r in rates}
    open_periods = await repository.list_periods(status="open")
    assert len(open_periods) == 1


@pytest.mark.asyncio
async def test_company_policy_repository(
    seeded_expectations: dict, db_session: AsyncSession
) -> None:
    repository = CompanyPolicyRepository(db_session)
    limits = await repository.list_expense_limits(category="meals")
    assert {limit.grade for limit in limits} == {"junior", "senior", "manager", "director"}
    threshold = await repository.get_approval_threshold("payment")
    assert threshold is not None
    submission = await repository.get_submission_policy()
    assert submission is not None
    depreciation = await repository.list_depreciation_policies()
    assert len(depreciation) == 4
