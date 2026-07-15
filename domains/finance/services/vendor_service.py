from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.simulation import simulation_today

OUTSTANDING_VENDOR_INVOICE_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class VendorBalance:
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_invoice_count: int
    oldest_due_date: date | None


@dataclass(frozen=True)
class CashPosition:
    balance: Decimal
    as_of_date: date


@dataclass(frozen=True)
class VendorInvoiceRecord:
    vendor_invoice_number: str
    vendor_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_until_due: int
    status: str


class VendorService:
    """Business logic for accounts-payable vendor obligations and the
    company's cash position.

    get_vendor_balance sums a vendor's outstanding vendor_invoices.balance
    (status sent/partially_paid/overdue - the AP mirror of AR's
    UNPAID_STATUSES). get_cash_position reports the company's real cash
    ledger balance as of a date (defaults to today - a live, ongoing
    figure, same reasoning as InvoiceService.get_unpaid_invoices's as_of
    default).
    """

    def __init__(
        self,
        vendor_invoice_repository: VendorInvoiceRepository,
        vendor_repository: VendorRepository,
        cash_repository: CashRepository,
    ) -> None:
        self._vendor_invoice_repository = vendor_invoice_repository
        self._vendor_repository = vendor_repository
        self._cash_repository = cash_repository

    async def get_vendor_balance(self, *, vendor_name: str) -> VendorBalance:
        vendor = await self._vendor_repository.get_by_name(vendor_name)
        if vendor is None:
            raise ValueError(f"Vendor not found: {vendor_name}")

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES, vendor_id=vendor.id
        )
        total_outstanding = sum((invoice.balance for invoice in invoices), Decimal("0"))
        oldest_due_date = min((invoice.due_date for invoice in invoices), default=None)

        return VendorBalance(
            vendor_code=vendor.vendor_code,
            vendor_name=vendor.company_name,
            total_outstanding=total_outstanding,
            open_invoice_count=len(invoices),
            oldest_due_date=oldest_due_date,
        )

    async def get_cash_position(self, as_of: date | None = None) -> CashPosition:
        effective_as_of = as_of if as_of is not None else simulation_today()
        balance = await self._cash_repository.get_balance_as_of(effective_as_of)
        return CashPosition(balance=balance, as_of_date=effective_as_of)

    async def list_outstanding_vendor_invoices(
        self, *, vendor_id: str | None = None, as_of: date | None = None
    ) -> list[VendorInvoiceRecord]:
        resolved_vendor_id: uuid.UUID | None = None
        if vendor_id is not None:
            vendor = await self._vendor_repository.get_by_code(vendor_id)
            if vendor is None:
                raise ValueError(f"Vendor not found: {vendor_id}")
            resolved_vendor_id = vendor.id

        effective_as_of = as_of if as_of is not None else simulation_today()

        invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=OUTSTANDING_VENDOR_INVOICE_STATUSES, vendor_id=resolved_vendor_id
        )
        vendors = await self._vendor_repository.list_all()
        vendor_names = {vendor.id: vendor.company_name for vendor in vendors}

        records = [
            VendorInvoiceRecord(
                vendor_invoice_number=invoice.vendor_invoice_number,
                vendor_name=vendor_names.get(invoice.vendor_id, "Unknown vendor"),
                issue_date=invoice.issue_date,
                due_date=invoice.due_date,
                total=invoice.total,
                balance=invoice.balance,
                days_until_due=(invoice.due_date - effective_as_of).days,
                status=invoice.status,
            )
            for invoice in invoices
        ]
        records.sort(key=lambda record: record.due_date)
        return records
