from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import BudgetModel


class BudgetRepository:
    """Read-only access to budget lines. Variance math lives in services."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_budget_lines(
        self,
        *,
        department_id: uuid.UUID | None = None,
        category: str | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
    ) -> list[BudgetModel]:
        conditions: list[ColumnElement[bool]] = []
        if department_id is not None:
            conditions.append(BudgetModel.department_id == department_id)
        if category is not None:
            conditions.append(BudgetModel.category == category)
        if period_from is not None:
            conditions.append(BudgetModel.period >= period_from)
        if period_to is not None:
            conditions.append(BudgetModel.period <= period_to)
        stmt = (
            select(BudgetModel)
            .where(*conditions)
            .order_by(BudgetModel.period, BudgetModel.category)
        )
        return list((await self._db.execute(stmt)).scalars().all())
