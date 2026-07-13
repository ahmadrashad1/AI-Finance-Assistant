from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from domains.finance.models import InvoiceModel


def compute_invoice_status(
    *,
    total: Decimal,
    amount_paid: Decimal,
    due_date: date,
    as_of: date,
    current_status: str,
) -> str:
    """Derives an invoice's status from its balance and due date.

    `cancelled` and `draft` are manually-controlled states never overridden
    by balance/due-date math; every other status is derived, in priority
    order: paid > overdue > partially_paid > sent. A partially-paid invoice
    that is also past due is `overdue`, not `partially_paid` (see design
    spec's "Status determination rule").
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


class InvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        invoice_number: str,
        customer_id: uuid.UUID,
        purchase_order_id: uuid.UUID | None,
        issue_date: date,
        due_date: date,
        status: str,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
        currency: str = "USD",
    ) -> InvoiceModel:
        invoice = InvoiceModel(
            id=uuid.uuid4(),
            invoice_number=invoice_number,
            customer_id=customer_id,
            purchase_order_id=purchase_order_id,
            issue_date=issue_date,
            due_date=due_date,
            status=status,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            amount_paid=Decimal("0"),
            balance=total,
        )
        self._db.add(invoice)
        await self._db.flush()
        return invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> InvoiceModel | None:
        return await self._db.get(InvoiceModel, invoice_id)

    async def get_by_number(self, invoice_number: str) -> InvoiceModel | None:
        stmt = select(InvoiceModel).where(InvoiceModel.invoice_number == invoice_number)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: uuid.UUID) -> list[InvoiceModel]:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.customer_id == customer_id)
            .order_by(InvoiceModel.issue_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_overdue(self, as_of: date) -> list[InvoiceModel]:
        stmt = (
            select(InvoiceModel)
            .where(InvoiceModel.status == "overdue", InvoiceModel.due_date < as_of)
            .order_by(InvoiceModel.due_date)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_statuses(
        self,
        *,
        statuses: Sequence[str],
        customer_id: uuid.UUID | None = None,
        minimum_balance: Decimal | None = None,
    ) -> list[InvoiceModel]:
        conditions: list[ColumnElement[bool]] = [InvoiceModel.status.in_(statuses)]
        if customer_id is not None:
            conditions.append(InvoiceModel.customer_id == customer_id)
        if minimum_balance is not None:
            conditions.append(InvoiceModel.balance >= minimum_balance)
        stmt = select(InvoiceModel).where(*conditions).order_by(InvoiceModel.due_date)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def find_potential_duplicate_groups(
        self, *, invoice_number: str | None = None
    ) -> list[list[InvoiceModel]]:
        """Groups invoices by (customer_id, total) where the group has
        more than one member and every member's issue_date falls within
        7 days of the group's earliest issue_date - a deterministic
        proxy for "the same invoice entered twice," not a fuzzy/LLM
        judgment call. With invoice_number given, only that invoice's
        own group (possibly empty) is considered.
        """
        conditions: list[ColumnElement[bool]] = [InvoiceModel.status != "cancelled"]
        if invoice_number is not None:
            target = await self.get_by_number(invoice_number)
            if target is None:
                return []
            conditions.append(InvoiceModel.customer_id == target.customer_id)
            conditions.append(InvoiceModel.total == target.total)

        stmt = (
            select(InvoiceModel)
            .where(*conditions)
            .order_by(InvoiceModel.customer_id, InvoiceModel.total, InvoiceModel.issue_date)
        )
        result = await self._db.execute(stmt)
        invoices = list(result.scalars().all())

        groups: list[list[InvoiceModel]] = []
        current_group: list[InvoiceModel] = []
        for invoice in invoices:
            starts_new_group = current_group and (
                invoice.customer_id != current_group[-1].customer_id
                or invoice.total != current_group[-1].total
                or (invoice.issue_date - current_group[0].issue_date).days > 7
            )
            if starts_new_group:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = []
            current_group.append(invoice)
        if len(current_group) > 1:
            groups.append(current_group)
        return groups

    async def search(
        self,
        *,
        invoice_number: str | None = None,
        customer_id: uuid.UUID | None = None,
        status: str | None = None,
        minimum_amount: Decimal | None = None,
        maximum_amount: Decimal | None = None,
        due_before: date | None = None,
        due_after: date | None = None,
    ) -> list[InvoiceModel]:
        conditions: list[ColumnElement[bool]] = []
        if invoice_number is not None:
            conditions.append(InvoiceModel.invoice_number == invoice_number)
        if customer_id is not None:
            conditions.append(InvoiceModel.customer_id == customer_id)
        if status is not None:
            conditions.append(InvoiceModel.status == status)
        if minimum_amount is not None:
            conditions.append(InvoiceModel.total >= minimum_amount)
        if maximum_amount is not None:
            conditions.append(InvoiceModel.total <= maximum_amount)
        if due_before is not None:
            conditions.append(InvoiceModel.due_date < due_before)
        if due_after is not None:
            conditions.append(InvoiceModel.due_date > due_after)
        stmt = select(InvoiceModel).where(*conditions).order_by(InvoiceModel.due_date)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
