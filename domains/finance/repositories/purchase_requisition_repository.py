from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import PurchaseRequisitionModel, RequisitionItemModel


class PurchaseRequisitionRepository:
    """Read-only access to purchase requisitions and their items."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_number(self, requisition_number: str) -> PurchaseRequisitionModel | None:
        stmt = select(PurchaseRequisitionModel).where(
            PurchaseRequisitionModel.requisition_number == requisition_number
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_requisitions(
        self,
        *,
        status: str | None = None,
        department_id: uuid.UUID | None = None,
        requester_employee_id: uuid.UUID | None = None,
    ) -> list[PurchaseRequisitionModel]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(PurchaseRequisitionModel.status == status)
        if department_id is not None:
            conditions.append(PurchaseRequisitionModel.department_id == department_id)
        if requester_employee_id is not None:
            conditions.append(
                PurchaseRequisitionModel.requester_employee_id == requester_employee_id
            )
        stmt = (
            select(PurchaseRequisitionModel)
            .where(*conditions)
            .order_by(PurchaseRequisitionModel.requisition_number)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_items(self, requisition_id: uuid.UUID) -> list[RequisitionItemModel]:
        stmt = (
            select(RequisitionItemModel)
            .where(RequisitionItemModel.requisition_id == requisition_id)
            .order_by(RequisitionItemModel.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())
