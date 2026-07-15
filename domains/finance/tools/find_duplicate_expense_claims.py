from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class FindDuplicateExpenseClaimsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class DuplicateClaimOut(BaseModel):
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


class DuplicateClaimGroupOut(BaseModel):
    claims: list[DuplicateClaimOut]


class FindDuplicateExpenseClaimsResult(BaseModel):
    groups: list[DuplicateClaimGroupOut]


async def find_duplicate_expense_claims_handler(
    params: FindDuplicateExpenseClaimsParams, context: ToolContext
) -> FindDuplicateExpenseClaimsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    groups = await service.find_duplicate_expense_claims(
        employee_id=params.employee_id, date_from=params.date_from, date_to=params.date_to
    )
    return FindDuplicateExpenseClaimsResult(
        groups=[
            DuplicateClaimGroupOut(
                claims=[DuplicateClaimOut(**claim.__dict__) for claim in group.claims]
            )
            for group in groups
        ]
    )


FIND_DUPLICATE_EXPENSE_CLAIMS_TOOL = ToolSpec(
    name="find_duplicate_expense_claims",
    description=(
        "Detects likely duplicate expense claims: same employee, same "
        "category, same amount, and same expense date, submitted more "
        "than once. Returns groups of matching claims. Optionally filter "
        "by employee_id (business code) and/or date_from/date_to. This "
        "is a duplicate-submission check, not a policy check - use "
        "get_expense_policy_violations for over-limit/missing-receipt/"
        "late-submission/self-approved claims instead. Use this for "
        "'is anyone submitting duplicate expense claims?' or 'has EMP-"
        "0015 double-submitted anything?'."
    ),
    parameters_model=FindDuplicateExpenseClaimsParams,
    result_model=FindDuplicateExpenseClaimsResult,
    handler=find_duplicate_expense_claims_handler,
)
