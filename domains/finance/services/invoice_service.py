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


@dataclass(frozen=True)
class InvoiceRecord:
    """Shared result shape for search_invoices and get_overdue_invoices -
    structurally identical to UnpaidInvoice, but a distinct type so
    Milestone 5's UnpaidInvoice contract (and its existing tests/imports)
    stay untouched.
    """

    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


@dataclass(frozen=True)
class CustomerBalance:
    customer_code: str
    customer_name: str
    total_outstanding: Decimal
    unpaid_invoice_count: int
    oldest_due_date: date | None


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

    async def search_invoices(
        self,
        *,
        invoice_number: str | None = None,
        customer_id: str | None = None,
        status: str | None = None,
        minimum_amount: Decimal | None = None,
        maximum_amount: Decimal | None = None,
        due_before: date | None = None,
        due_after: date | None = None,
        as_of: date | None = None,
    ) -> list[InvoiceRecord]:
        resolved_customer_id: uuid.UUID | None = None
        if customer_id is not None:
            customer = await self._customer_repository.get_by_code(customer_id)
            if customer is None:
                raise ValueError(f"Customer not found: {customer_id}")
            resolved_customer_id = customer.id

        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._invoice_repository.search(
            invoice_number=invoice_number,
            customer_id=resolved_customer_id,
            status=status,
            minimum_amount=minimum_amount,
            maximum_amount=maximum_amount,
            due_before=due_before,
            due_after=due_after,
        )
        customers = await self._customer_repository.list_all()
        customer_names = {customer.id: customer.company_name for customer in customers}

        return [
            InvoiceRecord(
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

    async def get_overdue_invoices(
        self,
        *,
        customer_id: str | None = None,
        minimum_days: int | None = None,
        as_of: date | None = None,
    ) -> list[InvoiceRecord]:
        resolved_customer_id: uuid.UUID | None = None
        if customer_id is not None:
            customer = await self._customer_repository.get_by_code(customer_id)
            if customer is None:
                raise ValueError(f"Customer not found: {customer_id}")
            resolved_customer_id = customer.id

        effective_as_of = as_of if as_of is not None else date.today()

        invoices = await self._invoice_repository.list_by_statuses(
            statuses=("overdue",), customer_id=resolved_customer_id
        )
        customers = await self._customer_repository.list_all()
        customer_names = {customer.id: customer.company_name for customer in customers}

        records = [
            InvoiceRecord(
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
        if minimum_days is not None:
            records = [record for record in records if record.days_outstanding >= minimum_days]
        records.sort(key=lambda record: record.days_outstanding, reverse=True)
        return records

    async def get_customer_balance(self, *, customer_name: str) -> CustomerBalance:
        customer = await self._customer_repository.get_by_name(customer_name)
        if customer is None:
            raise ValueError(f"Customer not found: {customer_name}")

        invoices = await self._invoice_repository.list_by_statuses(
            statuses=UNPAID_STATUSES, customer_id=customer.id
        )
        total_outstanding = sum((invoice.balance for invoice in invoices), Decimal("0"))
        oldest_due_date = min((invoice.due_date for invoice in invoices), default=None)

        return CustomerBalance(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            total_outstanding=total_outstanding,
            unpaid_invoice_count=len(invoices),
            oldest_due_date=oldest_due_date,
        )
