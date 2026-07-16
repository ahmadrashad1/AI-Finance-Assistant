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


class GetExpectedOutflowsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date


class ExpectedOutflowOut(BaseModel):
    source: str
    reference: str
    vendor_name: str | None
    expected_payment_date: date
    amount: Decimal


class GetExpectedOutflowsResult(BaseModel):
    outflows: list[ExpectedOutflowOut]
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


async def get_expected_outflows_handler(
    params: GetExpectedOutflowsParams, context: ToolContext
) -> GetExpectedOutflowsResult:
    outflows = await _service(context).get_expected_outflows(
        date_from=params.date_from, date_to=params.date_to
    )
    outflows_out = [ExpectedOutflowOut(**outflow.__dict__) for outflow in outflows]
    total_amount = sum((outflow.amount for outflow in outflows_out), Decimal("0"))
    return GetExpectedOutflowsResult(outflows=outflows_out, total_amount=total_amount)


GET_EXPECTED_OUTFLOWS_TOOL = ToolSpec(
    name="get_expected_outflows",
    description=(
        "Returns expected cash payments out between date_from and "
        "date_to (both required - call resolve_date_range first for a "
        "relative expression): vendor invoices due in the window, "
        "approved purchase requisitions not yet converted to a PO (by "
        "needed_by_date), and open purchase orders (by order date plus "
        "the vendor's payment terms, since a PO has no due date of its "
        "own). Each item's 'source' field says which of the three. Use "
        "this for 'what do we owe over the next N weeks?' or as half of "
        "a cash flow question alongside get_expected_inflows."
    ),
    parameters_model=GetExpectedOutflowsParams,
    result_model=GetExpectedOutflowsResult,
    handler=get_expected_outflows_handler,
)
