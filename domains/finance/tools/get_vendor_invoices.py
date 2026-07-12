from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorService


class GetVendorInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: str | None = None


class VendorInvoiceOut(BaseModel):
    vendor_invoice_number: str
    vendor_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_until_due: int
    status: str


class VendorInvoicesSummary(BaseModel):
    count: int
    total_outstanding: Decimal


class GetVendorInvoicesResult(BaseModel):
    invoices: list[VendorInvoiceOut]
    summary: VendorInvoicesSummary


async def get_vendor_invoices_handler(
    params: GetVendorInvoicesParams, context: ToolContext
) -> GetVendorInvoicesResult:
    service = VendorService(
        VendorInvoiceRepository(context.db),
        VendorRepository(context.db),
        CashRepository(context.db),
    )
    records = await service.list_outstanding_vendor_invoices(vendor_id=params.vendor_id)
    invoices_out = [
        VendorInvoiceOut(
            vendor_invoice_number=record.vendor_invoice_number,
            vendor_name=record.vendor_name,
            issue_date=record.issue_date,
            due_date=record.due_date,
            total=record.total,
            balance=record.balance,
            days_until_due=record.days_until_due,
            status=record.status,
        )
        for record in records
    ]
    total_outstanding = sum((invoice.balance for invoice in invoices_out), Decimal("0"))
    return GetVendorInvoicesResult(
        invoices=invoices_out,
        summary=VendorInvoicesSummary(
            count=len(invoices_out), total_outstanding=total_outstanding
        ),
    )


GET_VENDOR_INVOICES_TOOL = ToolSpec(
    name="get_vendor_invoices",
    description=(
        "Returns the company's outstanding vendor invoices (status "
        "'sent', 'partially_paid', or 'overdue' - bills not yet fully "
        "paid), sorted by due date, soonest first. Optionally filter to "
        "one vendor via vendor_id (business code, e.g. 'VEND-0007'). Use "
        "this for 'what vendor invoices are outstanding' style questions, "
        "and as one of several tools when reasoning about which bills to "
        "pay first (combine with get_cash_position for that) - e.g. "
        "'Which invoices should I pay first?' or 'What vendor bills are "
        "outstanding?'"
    ),
    parameters_model=GetVendorInvoicesParams,
    result_model=GetVendorInvoicesResult,
    handler=get_vendor_invoices_handler,
)
