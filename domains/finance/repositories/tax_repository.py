from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import TaxPeriodModel, TaxRateModel


class TaxRepository:
    """Read-only access to tax rates and filing periods. Tax positions are
    computed from invoices and vendor payments by a service -- never stored."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_rates(
        self, *, jurisdiction: str | None = None, effective_on: date | None = None
    ) -> list[TaxRateModel]:
        conditions: list[ColumnElement[bool]] = []
        if jurisdiction is not None:
            conditions.append(TaxRateModel.jurisdiction == jurisdiction)
        if effective_on is not None:
            conditions.append(TaxRateModel.effective_from <= effective_on)
            conditions.append(
                (TaxRateModel.effective_to.is_(None))
                | (TaxRateModel.effective_to >= effective_on)
            )
        stmt = (
            select(TaxRateModel)
            .where(*conditions)
            .order_by(TaxRateModel.jurisdiction, TaxRateModel.category)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_periods(self, *, status: str | None = None) -> list[TaxPeriodModel]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(TaxPeriodModel.status == status)
        stmt = select(TaxPeriodModel).where(*conditions).order_by(TaxPeriodModel.period)
        return list((await self._db.execute(stmt)).scalars().all())
