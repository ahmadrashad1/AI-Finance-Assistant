from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import FixedAssetModel


class FixedAssetRepository:
    """Read-only access to fixed assets. Depreciation and net book value are
    computed by services from the simulation date -- never here."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_tag(self, asset_tag: str) -> FixedAssetModel | None:
        stmt = select(FixedAssetModel).where(FixedAssetModel.asset_tag == asset_tag)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_assets(
        self,
        *,
        asset_class: str | None = None,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[FixedAssetModel]:
        conditions: list[ColumnElement[bool]] = []
        if asset_class is not None:
            conditions.append(FixedAssetModel.asset_class == asset_class)
        if department_id is not None:
            conditions.append(FixedAssetModel.department_id == department_id)
        if status is not None:
            conditions.append(FixedAssetModel.status == status)
        stmt = select(FixedAssetModel).where(*conditions).order_by(FixedAssetModel.asset_tag)
        return list((await self._db.execute(stmt)).scalars().all())
