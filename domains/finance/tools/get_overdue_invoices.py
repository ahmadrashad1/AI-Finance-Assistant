from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class GetOverdueInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    minimum_days: int | None = Field(default=None, ge=0)


class OverdueInvoiceOut(BaseModel):
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class OverdueInvoicesSummary(BaseModel):
    count: int
    total_outstanding: Decimal


class GetOverdueInvoicesResult(BaseModel):
    invoices: list[OverdueInvoiceOut]
    summary: OverdueInvoicesSummary


async def get_overdue_invoices_handler(
    params: GetOverdueInvoicesParams, context: ToolContext
) -> GetOverdueInvoicesResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    records = await service.get_overdue_invoices(
        customer_id=params.customer_id, minimum_days=params.minimum_days
    )
    invoices_out = [
        OverdueInvoiceOut(
            invoice_number=record.invoice_number,
            customer_name=record.customer_name,
            issue_date=record.issue_date,
            due_date=record.due_date,
            total=record.total,
            balance=record.balance,
            days_outstanding=record.days_outstanding,
            status=record.status,
        )
        for record in records
    ]
    total_outstanding = sum((invoice.balance for invoice in invoices_out), Decimal("0"))
    return GetOverdueInvoicesResult(
        invoices=invoices_out,
        summary=OverdueInvoicesSummary(
            count=len(invoices_out), total_outstanding=total_outstanding
        ),
    )


GET_OVERDUE_INVOICES_TOOL = ToolSpec(
    name="get_overdue_invoices",
    description=(
        "Returns customer invoices that are past their due date (status "
        "'overdue' specifically - not merely unpaid), sorted by days "
        "overdue, most urgent first. Optionally filter to one customer via "
        "customer_id (business code, e.g. 'CUST-0007') and/or to invoices "
        "overdue by at least minimum_days. Use this whenever the user "
        "gives a specific overdue-day threshold (e.g. 'overdue by more "
        "than 30 days') or explicitly asks about past-due/late invoices "
        "rather than just unpaid ones - e.g. 'Show invoices overdue by 30 "
        "days', 'Which invoices are past due?', or \"Show ABC's overdue "
        "invoices\". For a general 'who owes us money' with no day "
        "threshold, use get_unpaid_invoices instead - it covers every "
        "unpaid status, not just 'overdue'."
    ),
    parameters_model=GetOverdueInvoicesParams,
    result_model=GetOverdueInvoicesResult,
    handler=get_overdue_invoices_handler,
)
