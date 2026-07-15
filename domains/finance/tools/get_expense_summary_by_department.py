from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpenseSummaryByDepartmentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None


class DepartmentCategorySpendOut(BaseModel):
    department_name: str
    category: str
    total_amount: Decimal
    claim_count: int


class GetExpenseSummaryByDepartmentResult(BaseModel):
    breakdown: list[DepartmentCategorySpendOut]
    grand_total: Decimal


async def get_expense_summary_by_department_handler(
    params: GetExpenseSummaryByDepartmentParams, context: ToolContext
) -> GetExpenseSummaryByDepartmentResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    rows = await service.get_expense_summary_by_department(
        date_from=params.date_from, date_to=params.date_to, category=params.category
    )
    breakdown = [DepartmentCategorySpendOut(**row.__dict__) for row in rows]
    grand_total = sum((row.total_amount for row in breakdown), Decimal("0"))
    return GetExpenseSummaryByDepartmentResult(breakdown=breakdown, grand_total=grand_total)


GET_EXPENSE_SUMMARY_BY_DEPARTMENT_TOOL = ToolSpec(
    name="get_expense_summary_by_department",
    description=(
        "Returns total expense spend aggregated by department and "
        "category (excludes rejected claims, since that spend never "
        "happened), plus a grand total. Optionally filter by date_from/"
        "date_to (expense date range - call resolve_date_range first for "
        "a relative expression) and/or category. Does NOT return "
        "individual claim records; use get_expense_claims for that. "
        "Does NOT compare spend against a budget - no budget tool exists "
        "yet. Use this for 'how much did Sales spend on travel last "
        "month?' or 'break down our expense spend by department'."
    ),
    parameters_model=GetExpenseSummaryByDepartmentParams,
    result_model=GetExpenseSummaryByDepartmentResult,
    handler=get_expense_summary_by_department_handler,
)
