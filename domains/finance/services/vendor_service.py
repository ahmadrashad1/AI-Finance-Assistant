from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository

OUTSTANDING_PO_STATUSES: Final[tuple[str, ...]] = ("approved", "received")


@dataclass(frozen=True)
class VendorBalance:
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_purchase_order_count: int
    oldest_order_date: date | None


class VendorService:
    """Business logic for accounts-payable vendor obligations.

    get_vendor_balance approximates a vendor's outstanding balance as the
    sum of total_amount across their purchase orders in an "outstanding"
    status (approved or received - not draft or cancelled). This is a
    documented approximation, not a true AP ledger: the finance simulator
    has no vendor-invoice or vendor-payment tables (Milestone 4 only built
    the AR side), so there is nothing to net a PO's total_amount against.
    """

    def __init__(
        self,
        purchase_order_repository: PurchaseOrderRepository,
        vendor_repository: VendorRepository,
    ) -> None:
        self._purchase_order_repository = purchase_order_repository
        self._vendor_repository = vendor_repository

    async def get_vendor_balance(self, *, vendor_name: str) -> VendorBalance:
        vendor = await self._vendor_repository.get_by_name(vendor_name)
        if vendor is None:
            raise ValueError(f"Vendor not found: {vendor_name}")

        purchase_orders = await self._purchase_order_repository.list_by_statuses(
            statuses=OUTSTANDING_PO_STATUSES, vendor_id=vendor.id
        )
        total_outstanding = sum(
            (purchase_order.total_amount for purchase_order in purchase_orders), Decimal("0")
        )
        oldest_order_date = min(
            (purchase_order.order_date for purchase_order in purchase_orders), default=None
        )

        return VendorBalance(
            vendor_code=vendor.vendor_code,
            vendor_name=vendor.company_name,
            total_outstanding=total_outstanding,
            open_purchase_order_count=len(purchase_orders),
            oldest_order_date=oldest_order_date,
        )
