from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository

OUTSTANDING_VENDOR_INVOICE_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")


@dataclass(frozen=True)
class VendorBalance:
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_invoice_count: int
    oldest_due_date: date | None


class VendorService:
    """Business logic for accounts-payable vendor obligations.

    get_vendor_balance sums a vendor's outstanding vendor_invoices.balance
    (status sent/partially_paid/overdue - the AP mirror of AR's
    UNPAID_STATUSES). Milestone 6 originally approximated this from
    purchase_orders.total_amount, before real vendor invoices existed;
    Milestone 7 replaced that approximation with the real ledger.
    """

    def __init__(
        self,
        vendor_invoice_repository: VendorInvoiceRepository,
        vendor_repository: VendorRepository,
    ) -> None:
        self._vendor_invoice_repository = vendor_invoice_repository
        self._vendor_repository = vendor_repository

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
