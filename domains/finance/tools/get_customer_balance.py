from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.services.invoice_service import InvoiceService


class GetCustomerBalanceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str


class GetCustomerBalanceResult(BaseModel):
    customer_code: str
    customer_name: str
    total_outstanding: Decimal
    unpaid_invoice_count: int
    oldest_due_date: date | None


async def get_customer_balance_handler(
    params: GetCustomerBalanceParams, context: ToolContext
) -> GetCustomerBalanceResult:
    service = InvoiceService(InvoiceRepository(context.db), CustomerRepository(context.db))
    balance = await service.get_customer_balance(customer_name=params.customer_name)
    return GetCustomerBalanceResult(
        customer_code=balance.customer_code,
        customer_name=balance.customer_name,
        total_outstanding=balance.total_outstanding,
        unpaid_invoice_count=balance.unpaid_invoice_count,
        oldest_due_date=balance.oldest_due_date,
    )


GET_CUSTOMER_BALANCE_TOOL = ToolSpec(
    name="get_customer_balance",
    description=(
        "Returns how much a single customer currently owes: total "
        "outstanding balance across all their unpaid invoices (status "
        "'sent', 'partially_paid', or 'overdue'), how many such invoices "
        "they have, and the due date of the oldest one. Requires "
        "customer_name (the customer's company name as the user says it, "
        "e.g. 'Northwind Manufacturing Ltd.' - not a business code). Use "
        "this whenever the user asks how much a specific customer owes, "
        "however phrased - e.g. 'How much does Northwind Manufacturing "
        "owe us?' or \"What's Acme Corp's balance?\""
    ),
    parameters_model=GetCustomerBalanceParams,
    result_model=GetCustomerBalanceResult,
    handler=get_customer_balance_handler,
)
