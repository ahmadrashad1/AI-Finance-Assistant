from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import ClosePeriodModel, CloseTaskModel


class ClosePeriodRepository:
    """Read-only access to financial close periods and their task checklists."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_periods(self, *, status: str | None = None) -> list[ClosePeriodModel]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(ClosePeriodModel.status == status)
        stmt = select(ClosePeriodModel).where(*conditions).order_by(ClosePeriodModel.period)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_period(self, period: date) -> ClosePeriodModel | None:
        stmt = select(ClosePeriodModel).where(ClosePeriodModel.period == period)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_tasks(
        self, close_period_id: uuid.UUID, *, status: str | None = None
    ) -> list[CloseTaskModel]:
        conditions: list[ColumnElement[bool]] = [
            CloseTaskModel.close_period_id == close_period_id
        ]
        if status is not None:
            conditions.append(CloseTaskModel.status == status)
        stmt = select(CloseTaskModel).where(*conditions).order_by(CloseTaskModel.task_name)
        return list((await self._db.execute(stmt)).scalars().all())
