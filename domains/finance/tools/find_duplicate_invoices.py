from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class FindDuplicateInvoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None = None


class DuplicateInvoiceOut(BaseModel):
    invoice_number: str
    customer_name: str
    issue_date: date
    total: Decimal = Field(ge=0)


class FindDuplicateInvoicesSummary(BaseModel):
    group_count: int = Field(ge=0)
    invoice_count: int = Field(ge=0)


class FindDuplicateInvoicesResult(BaseModel):
    duplicate_groups: list[list[DuplicateInvoiceOut]]
    summary: FindDuplicateInvoicesSummary


async def find_duplicate_invoices_handler(
    params: FindDuplicateInvoicesParams, context: ToolContext
) -> FindDuplicateInvoicesResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    groups = await service.find_duplicate_invoices(invoice_number=params.invoice_number)

    groups_out = [
        [
            DuplicateInvoiceOut(
                invoice_number=record.invoice_number, customer_name=record.customer_name,
                issue_date=record.issue_date, total=record.total,
            )
            for record in group.invoices
        ]
        for group in groups
    ]
    invoice_count = sum(len(group) for group in groups_out)
    summary = FindDuplicateInvoicesSummary(
        group_count=len(groups_out), invoice_count=invoice_count
    )
    return FindDuplicateInvoicesResult(duplicate_groups=groups_out, summary=summary)


FIND_DUPLICATE_INVOICES_TOOL = ToolSpec(
    name="find_duplicate_invoices",
    description=(
        "Finds potential duplicate customer invoices - invoices for the "
        "same customer, the same total amount, issued within 7 days of "
        "each other. Optional invoice_number checks only that one "
        "invoice's own potential duplicates; omit it to scan every "
        "invoice for duplicate groups. An empty result means no "
        "duplicates were found - that is a valid, complete answer, not a "
        "failure. Use this for 'Find duplicate invoices', 'Check whether "
        "invoice INV-2201 already exists', or similar."
    ),
    parameters_model=FindDuplicateInvoicesParams,
    result_model=FindDuplicateInvoicesResult,
    handler=find_duplicate_invoices_handler,
)
