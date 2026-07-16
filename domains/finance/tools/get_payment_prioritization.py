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


class GetPaymentPrioritizationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentPriorityItemOut(BaseModel):
    vendor_invoice_number: str
    vendor_name: str
    due_date: date
    balance: Decimal
    vendor_preferred: bool
    days_until_due: int


class GetPaymentPrioritizationResult(BaseModel):
    items: list[PaymentPriorityItemOut]
    available_cash: Decimal


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


async def get_payment_prioritization_handler(
    params: GetPaymentPrioritizationParams, context: ToolContext
) -> GetPaymentPrioritizationResult:
    prioritization = await _service(context).get_payment_prioritization()
    return GetPaymentPrioritizationResult(
        items=[PaymentPriorityItemOut(**item.__dict__) for item in prioritization.items],
        available_cash=prioritization.available_cash,
    )


GET_PAYMENT_PRIORITIZATION_TOOL = ToolSpec(
    name="get_payment_prioritization",
    description=(
        "Returns every outstanding vendor invoice ranked in the order "
        "they should be paid - preferred vendors first, then soonest due "
        "date, then largest balance as a tiebreaker - alongside "
        "available cash. Takes no parameters. This replaces manually "
        "combining get_vendor_invoices and get_cash_position when the "
        "user wants an actual pay-first ordering, not just the two raw "
        "lists. Use this for 'which invoices should I pay first?', "
        "'what should we pay now?', or 'prioritize our vendor "
        "payments'. The ranking is deterministic; explain the "
        "trade-offs (e.g. cash available vs. total due) yourself."
    ),
    parameters_model=GetPaymentPrioritizationParams,
    result_model=GetPaymentPrioritizationResult,
    handler=get_payment_prioritization_handler,
)
