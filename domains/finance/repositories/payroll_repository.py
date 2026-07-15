from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import PayrollLineModel, PayrollRunModel


class PayrollRepository:
    """Read-only access to payroll runs and lines. Analysis lives in services."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_runs(
        self, *, period_from: date | None = None, period_to: date | None = None
    ) -> list[PayrollRunModel]:
        conditions: list[ColumnElement[bool]] = []
        if period_from is not None:
            conditions.append(PayrollRunModel.period >= period_from)
        if period_to is not None:
            conditions.append(PayrollRunModel.period <= period_to)
        stmt = select(PayrollRunModel).where(*conditions).order_by(PayrollRunModel.period)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_run_by_period(self, period: date) -> PayrollRunModel | None:
        stmt = select(PayrollRunModel).where(PayrollRunModel.period == period)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_lines_for_run(self, payroll_run_id: uuid.UUID) -> list[PayrollLineModel]:
        stmt = (
            select(PayrollLineModel)
            .where(PayrollLineModel.payroll_run_id == payroll_run_id)
            .order_by(PayrollLineModel.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_lines_for_employee(
        self, employee_id: uuid.UUID
    ) -> list[PayrollLineModel]:
        stmt = (
            select(PayrollLineModel)
            .where(PayrollLineModel.employee_id == employee_id)
            .order_by(PayrollLineModel.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())
