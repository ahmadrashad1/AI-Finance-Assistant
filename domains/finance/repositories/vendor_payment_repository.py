from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import VendorInvoiceModel, VendorPaymentModel
from domains.finance.repositories.vendor_invoice_repository import compute_vendor_invoice_status


class VendorPaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_payment(
        self,
        *,
        vendor_invoice_id: uuid.UUID,
        payment_date: date,
        amount: Decimal,
        payment_method: str,
        reference_number: str | None = None,
        today: date | None = None,
    ) -> VendorPaymentModel:
        invoice = await self._db.get(VendorInvoiceModel, vendor_invoice_id)
        if invoice is None:
            raise ValueError(f"Vendor invoice {vendor_invoice_id} does not exist")

        payment = VendorPaymentModel(
            id=uuid.uuid4(),
            vendor_invoice_id=vendor_invoice_id,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
        )
        self._db.add(payment)

        as_of = today if today is not None else date.today()
        invoice.amount_paid = invoice.amount_paid + amount
        invoice.balance = invoice.total - invoice.amount_paid
        invoice.status = compute_vendor_invoice_status(
            total=invoice.total,
            amount_paid=invoice.amount_paid,
            due_date=invoice.due_date,
            as_of=as_of,
            current_status=invoice.status,
        )

        await self._db.flush()
        return payment

    async def list_by_vendor_invoice(
        self, vendor_invoice_id: uuid.UUID
    ) -> list[VendorPaymentModel]:
        stmt = (
            select(VendorPaymentModel)
            .where(VendorPaymentModel.vendor_invoice_id == vendor_invoice_id)
            .order_by(VendorPaymentModel.payment_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
