from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class GetAgingReportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgingBucketOut(BaseModel):
    label: str
    invoice_count: int = Field(ge=0)
    total_balance: Decimal = Field(ge=0)


class GetAgingReportResult(BaseModel):
    buckets: list[AgingBucketOut]
    grand_total: Decimal = Field(ge=0)


async def get_aging_report_handler(
    params: GetAgingReportParams, context: ToolContext
) -> GetAgingReportResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    report = await service.get_aging_report()
    buckets_out = [
        AgingBucketOut(
            label=bucket.label, invoice_count=bucket.invoice_count,
            total_balance=bucket.total_balance,
        )
        for bucket in report.buckets
    ]
    return GetAgingReportResult(buckets=buckets_out, grand_total=report.grand_total)


GET_AGING_REPORT_TOOL = ToolSpec(
    name="get_aging_report",
    description=(
        "Summarizes all unpaid customer invoices into five aging buckets "
        "(current/not-yet-due, 0-30, 31-60, 61-90, and 90+ days overdue), "
        "each with an invoice count and total outstanding balance, plus a "
        "grand total. Takes no parameters. Use this for any request about "
        "receivables aging, however phrased - e.g. 'Generate an aging "
        "report', 'How much is overdue by bucket?', or 'Break down what "
        "customers owe us by how late they are.'"
    ),
    parameters_model=GetAgingReportParams,
    result_model=GetAgingReportResult,
    handler=get_aging_report_handler,
)
