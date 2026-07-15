from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    ApprovalThresholdPolicyModel,
    DepreciationPolicyModel,
    ExpenseLimitPolicyModel,
    ExpenseSubmissionPolicyModel,
)


class CompanyPolicyRepository:
    """Read-only access to company policy records. Policies are data, never
    prompt text; the rules that apply them live in services."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_expense_limits(
        self, *, category: str | None = None, grade: str | None = None
    ) -> list[ExpenseLimitPolicyModel]:
        stmt = select(ExpenseLimitPolicyModel)
        if category is not None:
            stmt = stmt.where(ExpenseLimitPolicyModel.category == category)
        if grade is not None:
            stmt = stmt.where(ExpenseLimitPolicyModel.grade == grade)
        stmt = stmt.order_by(ExpenseLimitPolicyModel.category, ExpenseLimitPolicyModel.grade)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_approval_threshold(
        self, subject: str
    ) -> ApprovalThresholdPolicyModel | None:
        stmt = select(ApprovalThresholdPolicyModel).where(
            ApprovalThresholdPolicyModel.subject == subject
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_submission_policy(self) -> ExpenseSubmissionPolicyModel | None:
        return (
            await self._db.execute(select(ExpenseSubmissionPolicyModel))
        ).scalars().first()

    async def list_depreciation_policies(self) -> list[DepreciationPolicyModel]:
        stmt = select(DepreciationPolicyModel).order_by(DepreciationPolicyModel.asset_class)
        return list((await self._db.execute(stmt)).scalars().all())
