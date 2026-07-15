from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.services.expense_service import ExpenseService


class GetPendingExpenseApprovalsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: str | None = None
    older_than_days: int | None = Field(default=None, ge=0)


class PendingExpenseClaimOut(BaseModel):
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


class GetPendingExpenseApprovalsResult(BaseModel):
    claims: list[PendingExpenseClaimOut]


async def get_pending_expense_approvals_handler(
    params: GetPendingExpenseApprovalsParams, context: ToolContext
) -> GetPendingExpenseApprovalsResult:
    service = ExpenseService(
        ExpenseClaimRepository(context.db),
        EmployeeRepository(context.db),
        CompanyPolicyRepository(context.db),
    )
    records = await service.get_pending_expense_approvals(
        department_id=params.department_id, older_than_days=params.older_than_days
    )
    return GetPendingExpenseApprovalsResult(
        claims=[PendingExpenseClaimOut(**record.__dict__) for record in records]
    )


GET_PENDING_EXPENSE_APPROVALS_TOOL = ToolSpec(
    name="get_pending_expense_approvals",
    description=(
        "Returns expense claims still awaiting approval (status "
        "'submitted'), sorted oldest-submitted first so the longest "
        "waits are highlighted. Optionally filter by department_id "
        "(department name, e.g. 'Finance') and/or older_than_days (only "
        "claims submitted at least that many days ago). Use this for "
        "'which expense claims are still waiting for approval?' or "
        "'what's sitting in someone's inbox waiting on a manager?' - "
        "not for already-decided claims (approved/rejected/reimbursed), "
        "which get_expense_claims can filter to by status instead."
    ),
    parameters_model=GetPendingExpenseApprovalsParams,
    result_model=GetPendingExpenseApprovalsResult,
    handler=get_pending_expense_approvals_handler,
)
