from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetCashPositionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCashPositionResult(BaseModel):
    balance: Decimal
    as_of_date: date


async def get_cash_position_handler(
    params: GetCashPositionParams, context: ToolContext
) -> GetCashPositionResult:
    service = VendorService(
        VendorInvoiceRepository(context.db),
        VendorRepository(context.db),
        CashRepository(context.db),
    )
    position = await service.get_cash_position()
    return GetCashPositionResult(balance=position.balance, as_of_date=position.as_of_date)


GET_CASH_POSITION_TOOL = ToolSpec(
    name="get_cash_position",
    description=(
        "Returns the company's current cash balance (as of today) from "
        "its bank account ledger. Takes no parameters. Use this whenever "
        "the user asks about cash on hand, available cash, or how much "
        "money the company has, however phrased - e.g. 'What's our cash "
        "position?', 'How much cash do we have?', or as one of several "
        "tools when reasoning about which bills to pay first (combine "
        "with get_vendor_invoices for that)."
    ),
    parameters_model=GetCashPositionParams,
    result_model=GetCashPositionResult,
    handler=get_cash_position_handler,
)
