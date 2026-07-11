from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetVendorBalanceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str


class GetVendorBalanceResult(BaseModel):
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    open_purchase_order_count: int
    oldest_order_date: date | None


async def get_vendor_balance_handler(
    params: GetVendorBalanceParams, context: ToolContext
) -> GetVendorBalanceResult:
    service = VendorService(PurchaseOrderRepository(context.db), VendorRepository(context.db))
    balance = await service.get_vendor_balance(vendor_name=params.vendor_name)
    return GetVendorBalanceResult(
        vendor_code=balance.vendor_code,
        vendor_name=balance.vendor_name,
        total_outstanding=balance.total_outstanding,
        open_purchase_order_count=balance.open_purchase_order_count,
        oldest_order_date=balance.oldest_order_date,
    )


GET_VENDOR_BALANCE_TOOL = ToolSpec(
    name="get_vendor_balance",
    description=(
        "Returns how much the company currently owes a single vendor: the "
        "total value of that vendor's open purchase orders (status "
        "'approved' or 'received' - not draft or cancelled), how many such "
        "purchase orders exist, and the order date of the oldest one. "
        "Requires vendor_name (the vendor's company name as the user says "
        "it, e.g. 'Summit Traders' - not a business code). Note: this "
        "reflects outstanding purchase-order commitments, not a "
        "reconciled accounts-payable ledger - the finance simulator does "
        "not yet track vendor invoices or vendor payments separately. Use "
        "this whenever the user asks how much is owed to a specific "
        "vendor, however phrased - e.g. 'What do we owe Summit Traders?' "
        "or \"What's our balance with Cascade Logistics?\""
    ),
    parameters_model=GetVendorBalanceParams,
    result_model=GetVendorBalanceResult,
    handler=get_vendor_balance_handler,
)
