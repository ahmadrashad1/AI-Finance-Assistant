from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

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


class GetExpectedInflowsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date


class ExpectedInflowOut(BaseModel):
    invoice_number: str
    customer_code: str
    customer_name: str
    due_date: date
    expected_receipt_date: date
    amount: Decimal
    adjusted_for_payment_behavior: bool


class GetExpectedInflowsResult(BaseModel):
    inflows: list[ExpectedInflowOut]
    total_amount: Decimal


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


async def get_expected_inflows_handler(
    params: GetExpectedInflowsParams, context: ToolContext
) -> GetExpectedInflowsResult:
    inflows = await _service(context).get_expected_inflows(
        date_from=params.date_from, date_to=params.date_to
    )
    inflows_out = [ExpectedInflowOut(**inflow.__dict__) for inflow in inflows]
    total_amount = sum((inflow.amount for inflow in inflows_out), Decimal("0"))
    return GetExpectedInflowsResult(inflows=inflows_out, total_amount=total_amount)


GET_EXPECTED_INFLOWS_TOOL = ToolSpec(
    name="get_expected_inflows",
    description=(
        "Returns expected customer cash receipts between date_from and "
        "date_to (both required - call resolve_date_range first for a "
        "relative expression like 'next month'), based on unpaid "
        "invoices whose expected receipt date falls in that window. The "
        "expected receipt date shifts a late-paying customer's invoice "
        "due date later by their historical average days-to-pay - see "
        "get_customer_payment_behavior. Does NOT return the current, "
        "unadjusted unpaid-invoice list; use get_unpaid_invoices for "
        "that. Use this for 'what cash are we expecting next month?' or "
        "as half of a cash flow question alongside get_expected_outflows."
    ),
    parameters_model=GetExpectedInflowsParams,
    result_model=GetExpectedInflowsResult,
    handler=get_expected_inflows_handler,
)
