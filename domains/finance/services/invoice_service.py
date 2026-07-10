from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository

UNPAID_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class UnpaidInvoice:
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class InvoiceService:
    """Business logic for accounts-receivable invoice queries.

    Defines what "unpaid" means (UNPAID_STATUSES), computes
    days_outstanding, and orders results by materiality (largest balance
    first) - InvoiceRepository only knows how to filter rows by status/
    customer/balance, never what those filters mean in business terms.
    """

    def __init__(
        self, invoice_repository: InvoiceRepository, customer_repository: CustomerRepository
    ) -> None:
        self._invoice_repository = invoice_repository
        self._customer_repository = customer_repository

    async def get_unpaid_invoices(
        self,
        *,
        customer_id: str | None = None,
        minimum_amount: Decimal | None = None,
        as_of: date | None = None,
    ) -> list[UnpaidInvoice]:
        resolved_customer_id: uuid.UUID | None = None
        if customer_id is not None:
            customer = await self._customer_repository.get_by_code(customer_id)
            if customer is None:
                raise ValueError(f"Customer not found: {customer_id}")
            resolved_customer_id = customer.id

        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._invoice_repository.list_by_statuses(
            statuses=UNPAID_STATUSES,
            customer_id=resolved_customer_id,
            minimum_balance=minimum_amount,
        )
        customers = await self._customer_repository.list_all()
        customer_names = {customer.id: customer.company_name for customer in customers}

        results = [
            UnpaidInvoice(
                invoice_number=invoice.invoice_number,
                customer_name=customer_names.get(invoice.customer_id, "Unknown customer"),
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                total=invoice.total,
                balance=invoice.balance,
                days_outstanding=max(0, (effective_as_of - invoice.due_date).days),
                status=invoice.status,
            )
            for invoice in invoices
        ]
        results.sort(key=lambda result: result.balance, reverse=True)
        return results
