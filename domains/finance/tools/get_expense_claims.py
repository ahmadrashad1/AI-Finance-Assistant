from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetExpenseClaimsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str | None = None
    department_id: str | None = None
    status: str | None = None
    category: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    minimum_amount: Decimal | None = Field(default=None, ge=0)
    claim_number: str | None = None


class ExpenseClaimOut(BaseModel):
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


class GetExpenseClaimsResult(BaseModel):
    claims: list[ExpenseClaimOut]


def _service(context: ToolContext) -> ExpenseService:
    return ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )


def _to_out(record: object) -> ExpenseClaimOut:
    return ExpenseClaimOut(**record.__dict__)


async def get_expense_claims_handler(
    params: GetExpenseClaimsParams, context: ToolContext
) -> GetExpenseClaimsResult:
    records = await _service(context).get_expense_claims(
        employee_id=params.employee_id,
        department_id=params.department_id,
        status=params.status,
        category=params.category,
        date_from=params.date_from,
        date_to=params.date_to,
        minimum_amount=params.minimum_amount,
        claim_number=params.claim_number,
    )
    return GetExpenseClaimsResult(claims=[_to_out(record) for record in records])


GET_EXPENSE_CLAIMS_TOOL = ToolSpec(
    name="get_expense_claims",
    description=(
        "Returns individual employee expense claim records (travel, "
        "meals, supplies, software, training, etc.), each with its "
        "recomputed policy_violations list (empty if compliant). "
        "Optionally filter by employee_id (business code, e.g. "
        "'EMP-0015'), department_id (department name, e.g. 'Sales'), "
        "status ('submitted'/'approved'/'rejected'/'reimbursed'), "
        "category, date_from/date_to (expense date range - call "
        "resolve_date_range first for a relative expression), "
        "minimum_amount, or claim_number (an exact claim like "
        "'EXP-01234', for a single-claim lookup - returns an empty list, "
        "not an error, if that claim doesn't exist). Does NOT return "
        "departmental spend totals; use get_expense_summary_by_department "
        "for that. Does NOT pre-filter to only claims that broke a "
        "policy; use get_expense_policy_violations for that narrower "
        "question."
    ),
    parameters_model=GetExpenseClaimsParams,
    result_model=GetExpenseClaimsResult,
    handler=get_expense_claims_handler,
)
