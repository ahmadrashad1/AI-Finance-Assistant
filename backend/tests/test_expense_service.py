from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseLimitPolicyModel,
    ExpenseSubmissionPolicyModel,
)
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


def _service(db_session: AsyncSession) -> ExpenseService:
    return ExpenseService(
        ExpenseClaimRepository(db_session),
        EmployeeRepository(db_session),
        CompanyPolicyRepository(db_session),
    )


async def _make_department(db_session: AsyncSession, name: str) -> DepartmentModel:
    department = DepartmentModel(id=uuid.uuid4(), name=name)
    db_session.add(department)
    await db_session.flush()
    return department


async def _make_employee(
    db_session: AsyncSession, code: str, department: DepartmentModel, grade: str = "junior"
) -> EmployeeModel:
    employee = EmployeeModel(
        id=uuid.uuid4(), employee_code=code, full_name=f"Employee {code}",
        department_id=department.id, role="Analyst", email=f"{code.lower()}@example.com",
        status="active", grade=grade, salary=Decimal("60000"), hire_date=date(2024, 1, 1),
    )
    db_session.add(employee)
    await db_session.flush()
    return employee


def _make_claim(
    *, number: str, employee: EmployeeModel, department: DepartmentModel, category: str = "meals",
    amount: Decimal = Decimal("100.00"), expense_date: date = date(2026, 6, 1),
    submitted_date: date = date(2026, 6, 2), receipt_attached: bool = True,
    status: str = "submitted", approver_id: uuid.UUID | None = None,
) -> ExpenseClaimModel:
    return ExpenseClaimModel(
        id=uuid.uuid4(), claim_number=number, employee_id=employee.id,
        department_id=department.id, category=category, amount=amount, currency="USD",
        description="Expense", expense_date=expense_date, submitted_date=submitted_date,
        receipt_attached=receipt_attached, status=status, approver_id=approver_id,
        policy_violations=[],
    )


@pytest.mark.asyncio
async def test_get_expense_claims_filters_by_department(
    clean_db: None, db_session: AsyncSession
) -> None:
    sales = await _make_department(db_session, "Sales")
    it = await _make_department(db_session, "IT")
    employee_a = await _make_employee(db_session, "EMP-1001", sales)
    employee_b = await _make_employee(db_session, "EMP-1002", it)
    db_session.add(_make_claim(number="EXP-1001", employee=employee_a, department=sales))
    db_session.add(_make_claim(number="EXP-1002", employee=employee_b, department=it))
    await db_session.commit()

    records = await _service(db_session).get_expense_claims(department_id="Sales")

    assert [r.claim_number for r in records] == ["EXP-1001"]
    assert records[0].department_name == "Sales"


@pytest.mark.asyncio
async def test_get_expense_claims_by_claim_number_returns_single_match(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1010", dept)
    db_session.add(_make_claim(number="EXP-2001", employee=employee, department=dept))
    await db_session.commit()

    records = await _service(db_session).get_expense_claims(claim_number="EXP-2001")
    assert [r.claim_number for r in records] == ["EXP-2001"]


@pytest.mark.asyncio
async def test_get_expense_claims_by_unknown_claim_number_returns_empty(
    clean_db: None, db_session: AsyncSession
) -> None:
    records = await _service(db_session).get_expense_claims(claim_number="EXP-99999")
    assert records == []


@pytest.mark.asyncio
async def test_get_expense_claims_unknown_department_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Department not found"):
        await _service(db_session).get_expense_claims(department_id="Marketing")


@pytest.mark.asyncio
async def test_policy_violations_recomputes_over_limit_and_self_approved(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1020", dept, grade="junior")
    db_session.add(
        ExpenseLimitPolicyModel(
            id=uuid.uuid4(), category="travel", grade="junior", per_claim_limit=Decimal("500.00")
        )
    )
    db_session.add(
        ExpenseSubmissionPolicyModel(
            id=uuid.uuid4(), receipt_required_above=Decimal("50.00"), submission_deadline_days=7
        )
    )
    over_limit_claim = _make_claim(
        number="EXP-3001", employee=employee, department=dept, category="travel",
        amount=Decimal("900.00"), status="approved", approver_id=employee.id,
    )
    db_session.add(over_limit_claim)
    await db_session.commit()

    records = await _service(db_session).get_expense_policy_violations()

    assert len(records) == 1
    assert records[0].claim_number == "EXP-3001"
    assert set(records[0].policy_violations) == {"over_limit", "self_approved"}


@pytest.mark.asyncio
async def test_policy_violations_detects_missing_receipt_and_late_submission(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1030", dept)
    db_session.add(
        ExpenseSubmissionPolicyModel(
            id=uuid.uuid4(), receipt_required_above=Decimal("50.00"), submission_deadline_days=7
        )
    )
    claim = _make_claim(
        number="EXP-3002", employee=employee, department=dept, amount=Decimal("200.00"),
        receipt_attached=False, expense_date=date(2026, 1, 1), submitted_date=date(2026, 1, 20),
    )
    db_session.add(claim)
    await db_session.commit()

    records = await _service(db_session).get_expense_policy_violations()
    assert set(records[0].policy_violations) == {"missing_receipt", "late_submission"}


@pytest.mark.asyncio
async def test_clean_claim_has_no_violations_and_is_excluded(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1040", dept)
    db_session.add(_make_claim(number="EXP-3003", employee=employee, department=dept))
    await db_session.commit()

    violations = await _service(db_session).get_expense_policy_violations()
    assert violations == []


@pytest.mark.asyncio
async def test_pending_approvals_filters_submitted_and_older_than_days(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1050", dept)
    old_claim = _make_claim(
        number="EXP-4001", employee=employee, department=dept,
        submitted_date=date(2026, 1, 1), status="submitted",
    )
    recent_claim = _make_claim(
        number="EXP-4002", employee=employee, department=dept,
        submitted_date=date(2026, 7, 1), status="submitted",
    )
    approved_claim = _make_claim(
        number="EXP-4003", employee=employee, department=dept,
        submitted_date=date(2026, 1, 1), status="approved", approver_id=employee.id,
    )
    for claim in (old_claim, recent_claim, approved_claim):
        db_session.add(claim)
    await db_session.commit()

    all_pending = await _service(db_session).get_pending_expense_approvals()
    assert {r.claim_number for r in all_pending} == {"EXP-4001", "EXP-4002"}
    assert all_pending[0].claim_number == "EXP-4001"  # oldest first

    old_only = await _service(db_session).get_pending_expense_approvals(older_than_days=60)
    assert [r.claim_number for r in old_only] == ["EXP-4001"]


@pytest.mark.asyncio
async def test_summary_by_department_excludes_rejected_and_aggregates(
    clean_db: None, db_session: AsyncSession
) -> None:
    sales = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1060", sales)
    db_session.add(
        _make_claim(
            number="EXP-5001", employee=employee, department=sales, category="travel",
            amount=Decimal("100.00"),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-5002", employee=employee, department=sales, category="travel",
            amount=Decimal("50.00"),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-5003", employee=employee, department=sales, category="travel",
            amount=Decimal("999.00"), status="rejected",
        )
    )
    await db_session.commit()

    summary = await _service(db_session).get_expense_summary_by_department()
    assert len(summary) == 1
    assert summary[0].department_name == "Sales"
    assert summary[0].category == "travel"
    assert summary[0].total_amount == Decimal("150.00")
    assert summary[0].claim_count == 2


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_matches_exact_quadruple(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1070", dept)
    db_session.add(
        _make_claim(
            number="EXP-6002", employee=employee, department=dept, category="software",
            amount=Decimal("40.00"), expense_date=date(2026, 3, 1),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-6001", employee=employee, department=dept, category="software",
            amount=Decimal("40.00"), expense_date=date(2026, 3, 1),
        )
    )
    db_session.add(
        _make_claim(
            number="EXP-6003", employee=employee, department=dept, category="software",
            amount=Decimal("41.00"), expense_date=date(2026, 3, 1),
        )
    )
    await db_session.commit()

    groups = await _service(db_session).find_duplicate_expense_claims()
    assert len(groups) == 1
    assert [c.claim_number for c in groups[0].claims] == ["EXP-6001", "EXP-6002"]


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_no_duplicates_returns_empty(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = await _make_department(db_session, "Sales")
    employee = await _make_employee(db_session, "EMP-1080", dept)
    db_session.add(_make_claim(number="EXP-6010", employee=employee, department=dept))
    await db_session.commit()

    assert await _service(db_session).find_duplicate_expense_claims() == []
