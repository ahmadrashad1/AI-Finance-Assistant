from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService


class ForecastCashFlowParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weeks: int = Field(ge=1, le=26)


class CashFlowPeriodOut(BaseModel):
    period_start: date
    period_end: date
    opening_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    closing_balance: Decimal


class ForecastCashFlowResult(BaseModel):
    periods: list[CashFlowPeriodOut]


def _service(context: ToolContext) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    return CashFlowService(
        CashRepository(context.db),
        CustomerRepository(context.db),
        InvoiceRepository(context.db),
        VendorRepository(context.db),
        VendorInvoiceRepository(context.db),
        PurchaseRequisitionRepository(context.db),
        PurchaseOrderRepository(context.db),
        credit_service,
    )


async def forecast_cash_flow_handler(
    params: ForecastCashFlowParams, context: ToolContext
) -> ForecastCashFlowResult:
    forecast = await _service(context).forecast_cash_flow(weeks=params.weeks)
    return ForecastCashFlowResult(
        periods=[CashFlowPeriodOut(**period.__dict__) for period in forecast.periods]
    )


FORECAST_CASH_FLOW_TOOL = ToolSpec(
    name="forecast_cash_flow",
    description=(
        "Returns a week-by-week cash flow projection (opening balance, "
        "inflows, outflows, closing balance per week) for the next "
        "`weeks` weeks (1-26), starting from today's actual cash "
        "position. Built from get_expected_inflows and "
        "get_expected_outflows internally. Does NOT return today's "
        "current balance alone with no projection; use get_cash_position "
        "for that. Use this for 'what's our cash forecast?', 'will we "
        "have enough cash to cover the next N weeks?', or 'project our "
        "cash flow for the next month' (4 weeks)."
    ),
    parameters_model=ForecastCashFlowParams,
    result_model=ForecastCashFlowResult,
    handler=forecast_cash_flow_handler,
)
