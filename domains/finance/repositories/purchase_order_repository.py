from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import PurchaseOrderModel


class PurchaseOrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        po_number: str,
        vendor_id: uuid.UUID,
        order_date: date,
        status: str,
        total_amount: Decimal,
        approved_by: uuid.UUID | None = None,
        approved_at: datetime | None = None,
    ) -> PurchaseOrderModel:
        purchase_order = PurchaseOrderModel(
            id=uuid.uuid4(),
            po_number=po_number,
            vendor_id=vendor_id,
            order_date=order_date,
            status=status,
            approved_by=approved_by,
            approved_at=approved_at,
            total_amount=total_amount,
        )
        self._db.add(purchase_order)
        await self._db.flush()
        return purchase_order

    async def get_by_id(self, purchase_order_id: uuid.UUID) -> PurchaseOrderModel | None:
        return await self._db.get(PurchaseOrderModel, purchase_order_id)

    async def get_by_number(self, po_number: str) -> PurchaseOrderModel | None:
        stmt = select(PurchaseOrderModel).where(PurchaseOrderModel.po_number == po_number)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_id: uuid.UUID) -> list[PurchaseOrderModel]:
        stmt = (
            select(PurchaseOrderModel)
            .where(PurchaseOrderModel.vendor_id == vendor_id)
            .order_by(PurchaseOrderModel.order_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
