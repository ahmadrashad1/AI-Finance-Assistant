from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import ExpenseClaimModel


class ExpenseClaimRepository:
    """Read-only access to expense claims. Policy checking lives in services."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_number(self, claim_number: str) -> ExpenseClaimModel | None:
        stmt = select(ExpenseClaimModel).where(ExpenseClaimModel.claim_number == claim_number)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_claims(
        self,
        *,
        employee_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        category: str | None = None,
        status: str | None = None,
        expense_date_from: date | None = None,
        expense_date_to: date | None = None,
    ) -> list[ExpenseClaimModel]:
        conditions: list[ColumnElement[bool]] = []
        if employee_id is not None:
            conditions.append(ExpenseClaimModel.employee_id == employee_id)
        if department_id is not None:
            conditions.append(ExpenseClaimModel.department_id == department_id)
        if category is not None:
            conditions.append(ExpenseClaimModel.category == category)
        if status is not None:
            conditions.append(ExpenseClaimModel.status == status)
        if expense_date_from is not None:
            conditions.append(ExpenseClaimModel.expense_date >= expense_date_from)
        if expense_date_to is not None:
            conditions.append(ExpenseClaimModel.expense_date <= expense_date_to)
        stmt = (
            select(ExpenseClaimModel)
            .where(*conditions)
            .order_by(ExpenseClaimModel.claim_number)
        )
        return list((await self._db.execute(stmt)).scalars().all())
