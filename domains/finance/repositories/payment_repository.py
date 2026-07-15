from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import InvoiceModel, PaymentModel
from domains.finance.repositories.invoice_repository import compute_invoice_status
from domains.finance.simulation import simulation_today


class PaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_payment(
        self,
        *,
        invoice_id: uuid.UUID,
        payment_date: date,
        amount: Decimal,
        payment_method: str,
        reference_number: str | None = None,
        today: date | None = None,
    ) -> PaymentModel:
        invoice = await self._db.get(InvoiceModel, invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} does not exist")

        payment = PaymentModel(
            id=uuid.uuid4(),
            invoice_id=invoice_id,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
        )
        self._db.add(payment)

        as_of = today if today is not None else simulation_today()
        invoice.amount_paid = invoice.amount_paid + amount
        invoice.balance = invoice.total - invoice.amount_paid
        invoice.status = compute_invoice_status(
            total=invoice.total,
            amount_paid=invoice.amount_paid,
            due_date=invoice.due_date,
            as_of=as_of,
            current_status=invoice.status,
        )

        await self._db.flush()
        return payment

    async def list_by_invoice(self, invoice_id: uuid.UUID) -> list[PaymentModel]:
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.invoice_id == invoice_id)
            .order_by(PaymentModel.payment_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
