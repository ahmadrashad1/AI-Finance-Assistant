from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import DepartmentModel, EmployeeModel, ExpenseClaimModel
from domains.finance.tools.find_duplicate_expense_claims import (
    FindDuplicateExpenseClaimsParams,
    find_duplicate_expense_claims_handler,
)
from domains.finance.tools.get_expense_claims import (
    GetExpenseClaimsParams,
    get_expense_claims_handler,
)


@pytest.mark.asyncio
async def test_get_expense_claims_tool_returns_seeded_claim(
    clean_db: None, db_session: AsyncSession
) -> None:
    dept = DepartmentModel(id=uuid.uuid4(), name="Engineering")
    db_session.add(dept)
    await db_session.flush()
    employee = EmployeeModel(
        id=uuid.uuid4(), employee_code="EMP-9001", full_name="Test Employee",
        department_id=dept.id, role="Engineer", email="test@example.com", status="active",
        grade="senior", salary=Decimal("90000"), hire_date=date(2024, 1, 1),
    )
    db_session.add(employee)
    await db_session.flush()
    db_session.add(
        ExpenseClaimModel(
            id=uuid.uuid4(), claim_number="EXP-9001", employee_id=employee.id,
            department_id=dept.id, category="travel", amount=Decimal("300.00"), currency="USD",
            description="Flight", expense_date=date(2026, 6, 1), submitted_date=date(2026, 6, 2),
            receipt_attached=True, status="submitted", policy_violations=[],
        )
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_expense_claims_handler(
        GetExpenseClaimsParams(department_id="Engineering"), context
    )
    assert [c.claim_number for c in result.claims] == ["EXP-9001"]


@pytest.mark.asyncio
async def test_find_duplicate_expense_claims_tool_empty_db_returns_no_groups(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await find_duplicate_expense_claims_handler(
        FindDuplicateExpenseClaimsParams(), context
    )
    assert result.groups == []
