from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpensePolicyViolationsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class PolicyViolatingClaimOut(BaseModel):
    claim_number: str
    employee_code: str
    employee_name: str
    department_name: str | None
    category: str
    amount: Decimal
    currency: str
    description: str
    expense_date: date | None
    submitted_date: date
    receipt_attached: bool
    status: str
    approver_code: str | None
    approved_date: date | None
    policy_violations: list[str]


class GetExpensePolicyViolationsResult(BaseModel):
    claims: list[PolicyViolatingClaimOut]


async def get_expense_policy_violations_handler(
    params: GetExpensePolicyViolationsParams, context: ToolContext
) -> GetExpensePolicyViolationsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    records = await service.get_expense_policy_violations(
        department_id=params.department_id, date_from=params.date_from, date_to=params.date_to
    )
    return GetExpensePolicyViolationsResult(
        claims=[PolicyViolatingClaimOut(**record.__dict__) for record in records]
    )


GET_EXPENSE_POLICY_VIOLATIONS_TOOL = ToolSpec(
    name="get_expense_policy_violations",
    description=(
        "Returns ONLY expense claims that breach a company policy: over "
        "their category/grade spending limit, missing a required "
        "receipt, submitted after the deadline, or self-approved (the "
        "claimant approved their own claim). Each result's "
        "policy_violations field lists which of those apply. Optionally "
        "filter by department_id (department name) and/or date_from/"
        "date_to (expense date range - call resolve_date_range first for "
        "a relative expression like 'this quarter'). Does NOT return "
        "compliant claims; use get_expense_claims for the full, "
        "unfiltered list."
    ),
    parameters_model=GetExpensePolicyViolationsParams,
    result_model=GetExpensePolicyViolationsResult,
    handler=get_expense_policy_violations_handler,
)
