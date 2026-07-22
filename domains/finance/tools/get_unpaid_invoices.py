from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class GetUnpaidInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    minimum_amount: Decimal | None = Field(default=None, ge=0)


class UnpaidInvoiceOut(BaseModel):
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date
    total: Decimal
    balance: Decimal
    days_outstanding: int
    status: str


class UnpaidInvoicesSummary(BaseModel):
    count: int
    total_outstanding: Decimal


class GetUnpaidInvoicesResult(BaseModel):
    invoices: list[UnpaidInvoiceOut]
    summary: UnpaidInvoicesSummary


async def get_unpaid_invoices_handler(
    params: GetUnpaidInvoicesParams, context: ToolContext
) -> GetUnpaidInvoicesResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    unpaid = await service.get_unpaid_invoices(
        customer_id=params.customer_id, minimum_amount=params.minimum_amount
    )
    invoices_out = [
        UnpaidInvoiceOut(
            invoice_number=invoice.invoice_number,
            customer_name=invoice.customer_name,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            total=invoice.total,
            balance=invoice.balance,
            days_outstanding=invoice.days_outstanding,
            status=invoice.status,
        )
        for invoice in unpaid
    ]
    total_outstanding = sum((invoice.balance for invoice in invoices_out), Decimal("0"))
    return GetUnpaidInvoicesResult(
        invoices=invoices_out,
        summary=UnpaidInvoicesSummary(count=len(invoices_out), total_outstanding=total_outstanding),
    )


GET_UNPAID_INVOICES_TOOL = ToolSpec(
    name="get_unpaid_invoices",
    description=(
        "Returns every still-unpaid customer invoice - status 'sent', "
        "'partially_paid', or 'overdue' (never 'draft'/'cancelled') - "
        "with amount owed (balance), days outstanding, and status. Use "
        "whenever the user asks who owes money or wants unpaid/"
        "outstanding invoices, however phrased - e.g. 'Show unpaid "
        "invoices', 'Which invoices haven't been paid?', 'Outstanding "
        "invoices?', 'Who still owes us money?', 'Customers with "
        "overdue invoices'. Optional filters: customer_id (e.g. "
        "'CUST-0007') and/or minimum_amount outstanding."
    ),
    parameters_model=GetUnpaidInvoicesParams,
    result_model=GetUnpaidInvoicesResult,
    handler=get_unpaid_invoices_handler,
)
