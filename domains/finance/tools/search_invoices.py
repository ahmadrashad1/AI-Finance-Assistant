from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService

InvoiceStatus = Literal["draft", "sent", "paid", "partially_paid", "overdue", "cancelled"]


class SearchInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None = None
    customer_id: str | None = None
    status: InvoiceStatus | None = None
    minimum_amount: Decimal | None = Field(default=None, ge=0)
    maximum_amount: Decimal | None = Field(default=None, ge=0)
    due_before: date | None = None
    due_after: date | None = None


class InvoiceOut(BaseModel):
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class SearchInvoicesSummary(BaseModel):
    count: int
    total_amount: Decimal


class SearchInvoicesResult(BaseModel):
    invoices: list[InvoiceOut]
    summary: SearchInvoicesSummary


async def search_invoices_handler(
    params: SearchInvoicesParams, context: ToolContext
) -> SearchInvoicesResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    records = await service.search_invoices(
        invoice_number=params.invoice_number,
        customer_id=params.customer_id,
        status=params.status,
        minimum_amount=params.minimum_amount,
        maximum_amount=params.maximum_amount,
        due_before=params.due_before,
        due_after=params.due_after,
    )
    invoices_out = [
        InvoiceOut(
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
    total_amount = sum((invoice.total for invoice in invoices_out), Decimal("0"))
    return SearchInvoicesResult(
        invoices=invoices_out,
        summary=SearchInvoicesSummary(count=len(invoices_out), total_amount=total_amount),
    )


SEARCH_INVOICES_TOOL = ToolSpec(
    name="search_invoices",
    description=(
        "Searches customer invoices by any combination of filters: exact "
        "invoice_number, customer_id (business code, e.g. 'CUST-0007'), "
        "status ('draft', 'sent', 'paid', 'partially_paid', 'overdue', or "
        "'cancelled'), an amount range (minimum_amount/maximum_amount, "
        "against the invoice total), and a due-date range "
        "(due_after/due_before). All filters are optional and combine with "
        "AND - omit a filter to not restrict on it. Use this for flexible "
        "invoice lookups that get_unpaid_invoices/get_overdue_invoices "
        "don't cover, e.g. 'Find invoice INV-1045', 'Show invoice "
        "INV-1045', 'Show paid invoices over 5000 for CUST-0003', or "
        "'Invoices due before end of month'."
    ),
    parameters_model=SearchInvoicesParams,
    result_model=SearchInvoicesResult,
    handler=search_invoices_handler,
)
