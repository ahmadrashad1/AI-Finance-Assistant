from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import VendorInvoiceModel


def compute_vendor_invoice_status(
    *,
    total: Decimal,
    amount_paid: Decimal,
    due_date: date,
    as_of: date,
    current_status: str,
) -> str:
    """Derives a vendor invoice's status from its balance and due date.

    Identical priority rule to `compute_invoice_status` (the AR side):
    cancelled/draft preserved, then paid > overdue > partially_paid > sent.
    """
    if current_status in ("cancelled", "draft"):
        return current_status
    balance = total - amount_paid
    if balance <= 0:
        return "paid"
    if due_date < as_of:
        return "overdue"
    if amount_paid > 0:
        return "partially_paid"
    return "sent"


class VendorInvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        vendor_invoice_number: str,
        vendor_id: uuid.UUID,
        purchase_order_id: uuid.UUID | None,
        issue_date: date,
        due_date: date,
        status: str,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
    ) -> VendorInvoiceModel:
        invoice = VendorInvoiceModel(
            id=uuid.uuid4(),
            vendor_invoice_number=vendor_invoice_number,
            vendor_id=vendor_id,
            purchase_order_id=purchase_order_id,
            issue_date=issue_date,
            due_date=due_date,
            status=status,
            subtotal=subtotal,
            tax=tax,
            total=total,
            amount_paid=Decimal("0"),
            balance=total,
        )
        self._db.add(invoice)
        await self._db.flush()
        return invoice

    async def get_by_id(self, vendor_invoice_id: uuid.UUID) -> VendorInvoiceModel | None:
        return await self._db.get(VendorInvoiceModel, vendor_invoice_id)

    async def get_by_number(self, vendor_invoice_number: str) -> VendorInvoiceModel | None:
        stmt = select(VendorInvoiceModel).where(
            VendorInvoiceModel.vendor_invoice_number == vendor_invoice_number
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_id: uuid.UUID) -> list[VendorInvoiceModel]:
        stmt = (
            select(VendorInvoiceModel)
            .where(VendorInvoiceModel.vendor_id == vendor_id)
            .order_by(VendorInvoiceModel.issue_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_statuses(
        self,
        *,
        statuses: Sequence[str],
        vendor_id: uuid.UUID | None = None,
        minimum_balance: Decimal | None = None,
    ) -> list[VendorInvoiceModel]:
        conditions: list[ColumnElement[bool]] = [VendorInvoiceModel.status.in_(statuses)]
        if vendor_id is not None:
            conditions.append(VendorInvoiceModel.vendor_id == vendor_id)
        if minimum_balance is not None:
            conditions.append(VendorInvoiceModel.balance >= minimum_balance)
        stmt = (
            select(VendorInvoiceModel)
            .where(*conditions)
            .order_by(VendorInvoiceModel.due_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
