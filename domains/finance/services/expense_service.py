from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from domains.finance.models import (
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseSubmissionPolicyModel,
)
from domains.finance.repositories.company_policy_repository import CompanyPolicyRepository
from domains.finance.repositories.employee_repository import EmployeeRepository
from domains.finance.repositories.expense_claim_repository import ExpenseClaimRepository
from domains.finance.simulation import simulation_today

NON_SPEND_STATUSES: Final[tuple[str, ...]] = ("rejected",)


@dataclass(frozen=True)
class ExpenseClaimRecord:
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


@dataclass(frozen=True)
class DepartmentCategorySpend:
    department_name: str
    category: str
    total_amount: Decimal
    claim_count: int


@dataclass(frozen=True)
class DuplicateExpenseGroup:
    claims: list[ExpenseClaimRecord]


class ExpenseService:
    """Business logic for expense claims: policy-violation recomputation
    (over_limit / missing_receipt / late_submission / self_approved) and
    duplicate-claim detection. Policy limits and submission rules are
    read from CompanyPolicyRepository (data, never prompt text) - this
    service is the only place that applies them.
    """

    def __init__(
        self,
        expense_claim_repository: ExpenseClaimRepository,
        employee_repository: EmployeeRepository,
        company_policy_repository: CompanyPolicyRepository,
    ) -> None:
        self._expense_claim_repository = expense_claim_repository
        self._employee_repository = employee_repository
        self._company_policy_repository = company_policy_repository

    async def _resolve_employee_id(self, employee_code: str | None) -> uuid.UUID | None:
        if employee_code is None:
            return None
        employee = await self._employee_repository.get_by_code(employee_code)
        if employee is None:
            raise ValueError(f"Employee not found: {employee_code}")
        return employee.id

    async def _resolve_department_id(self, department_name: str | None) -> uuid.UUID | None:
        if department_name is None:
            return None
        department = await self._employee_repository.get_department_by_name(department_name)
        if department is None:
            raise ValueError(f"Department not found: {department_name}")
        return department.id

    async def _lookup_maps(self) -> tuple[dict[uuid.UUID, EmployeeModel], dict[uuid.UUID, str]]:
        employees = await self._employee_repository.list_employees()
        employees_by_id = {employee.id: employee for employee in employees}
        departments = await self._employee_repository.list_departments()
        department_names = {department.id: department.name for department in departments}
        return employees_by_id, department_names

    async def _violation_inputs(
        self,
    ) -> tuple[dict[tuple[str, str], Decimal], ExpenseSubmissionPolicyModel | None]:
        limits = {
            (policy.category, policy.grade): policy.per_claim_limit
            for policy in await self._company_policy_repository.list_expense_limits()
        }
        submission_policy = await self._company_policy_repository.get_submission_policy()
        return limits, submission_policy

    def _compute_violations(
        self,
        claim: ExpenseClaimModel,
        employee: EmployeeModel | None,
        limits: dict[tuple[str, str], Decimal],
        submission_policy: ExpenseSubmissionPolicyModel | None,
    ) -> list[str]:
        violations: list[str] = []
        if employee is None or claim.expense_date is None:
            return violations
        limit = limits.get((claim.category, employee.grade or ""))
        if limit is not None and claim.amount > limit:
            violations.append("over_limit")
        if (
            submission_policy is not None
            and claim.amount > submission_policy.receipt_required_above
            and not claim.receipt_attached
        ):
            violations.append("missing_receipt")
        if submission_policy is not None and (
            claim.submitted_date - claim.expense_date
        ) > timedelta(days=submission_policy.submission_deadline_days):
            violations.append("late_submission")
        if (
            claim.approver_id is not None
            and claim.approver_id == claim.employee_id
            and claim.status in ("approved", "reimbursed")
        ):
            violations.append("self_approved")
        return violations

    def _to_record(
        self,
        claim: ExpenseClaimModel,
        employees_by_id: dict[uuid.UUID, EmployeeModel],
        department_names: dict[uuid.UUID, str],
        limits: dict[tuple[str, str], Decimal],
        submission_policy: ExpenseSubmissionPolicyModel | None,
    ) -> ExpenseClaimRecord:
        employee = employees_by_id.get(claim.employee_id)
        approver = employees_by_id.get(claim.approver_id) if claim.approver_id else None
        return ExpenseClaimRecord(
            claim_number=claim.claim_number,
            employee_code=employee.employee_code if employee else "Unknown employee",
            employee_name=employee.full_name if employee else "Unknown employee",
            department_name=(
                department_names.get(claim.department_id) if claim.department_id else None
            ),
            category=claim.category,
            amount=claim.amount,
            currency=claim.currency,
            description=claim.description,
            expense_date=claim.expense_date,
            submitted_date=claim.submitted_date,
            receipt_attached=claim.receipt_attached,
            status=claim.status,
            approver_code=approver.employee_code if approver else None,
            approved_date=claim.approved_date,
            policy_violations=self._compute_violations(
                claim, employee, limits, submission_policy
            ),
        )

    async def get_expense_claims(
        self,
        *,
        employee_id: str | None = None,
        department_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        minimum_amount: Decimal | None = None,
        claim_number: str | None = None,
    ) -> list[ExpenseClaimRecord]:
        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()

        if claim_number is not None:
            claim = await self._expense_claim_repository.get_by_number(claim_number)
            if claim is None:
                return []
            return [
                self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            ]

        resolved_employee_id = await self._resolve_employee_id(employee_id)
        resolved_department_id = await self._resolve_department_id(department_id)
        claims = await self._expense_claim_repository.list_claims(
            employee_id=resolved_employee_id,
            department_id=resolved_department_id,
            category=category,
            status=status,
            expense_date_from=date_from,
            expense_date_to=date_to,
        )
        if minimum_amount is not None:
            claims = [claim for claim in claims if claim.amount >= minimum_amount]

        return [
            self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            for claim in claims
        ]

    async def get_pending_expense_approvals(
        self, *, department_id: str | None = None, older_than_days: int | None = None
    ) -> list[ExpenseClaimRecord]:
        resolved_department_id = await self._resolve_department_id(department_id)
        claims = await self._expense_claim_repository.list_claims(
            department_id=resolved_department_id, status="submitted"
        )
        today = simulation_today()
        if older_than_days is not None:
            claims = [
                claim for claim in claims if (today - claim.submitted_date).days >= older_than_days
            ]
        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()
        records = [
            self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
            for claim in claims
        ]
        records.sort(key=lambda record: record.submitted_date)
        return records

    async def get_expense_policy_violations(
        self,
        *,
        department_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ExpenseClaimRecord]:
        records = await self.get_expense_claims(
            department_id=department_id, date_from=date_from, date_to=date_to
        )
        return [record for record in records if record.policy_violations]

    async def get_expense_summary_by_department(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        category: str | None = None,
    ) -> list[DepartmentCategorySpend]:
        claims = await self._expense_claim_repository.list_claims(
            category=category, expense_date_from=date_from, expense_date_to=date_to
        )
        claims = [claim for claim in claims if claim.status not in NON_SPEND_STATUSES]
        _, department_names = await self._lookup_maps()

        totals: dict[tuple[str, str], Decimal] = {}
        counts: dict[tuple[str, str], int] = {}
        for claim in claims:
            department_name = (
                department_names.get(claim.department_id) if claim.department_id else None
            ) or "Unassigned"
            key = (department_name, claim.category)
            totals[key] = totals.get(key, Decimal("0")) + claim.amount
            counts[key] = counts.get(key, 0) + 1

        results = [
            DepartmentCategorySpend(
                department_name=department_name,
                category=category_name,
                total_amount=totals[(department_name, category_name)],
                claim_count=counts[(department_name, category_name)],
            )
            for department_name, category_name in totals
        ]
        results.sort(key=lambda result: result.total_amount, reverse=True)
        return results

    async def find_duplicate_expense_claims(
        self,
        *,
        employee_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[DuplicateExpenseGroup]:
        resolved_employee_id = await self._resolve_employee_id(employee_id)
        claims = await self._expense_claim_repository.list_claims(
            employee_id=resolved_employee_id, expense_date_from=date_from, expense_date_to=date_to
        )
        groups: dict[tuple[uuid.UUID, str, Decimal, date | None], list[ExpenseClaimModel]] = {}
        for claim in claims:
            key = (claim.employee_id, claim.category, claim.amount, claim.expense_date)
            groups.setdefault(key, []).append(claim)

        employees_by_id, department_names = await self._lookup_maps()
        limits, submission_policy = await self._violation_inputs()
        result: list[DuplicateExpenseGroup] = []
        for members in groups.values():
            if len(members) < 2:
                continue
            records = [
                self._to_record(claim, employees_by_id, department_names, limits, submission_policy)
                for claim in sorted(members, key=lambda claim: claim.claim_number)
            ]
            result.append(DuplicateExpenseGroup(claims=records))
        result.sort(key=lambda group: group.claims[0].claim_number)
        return result
