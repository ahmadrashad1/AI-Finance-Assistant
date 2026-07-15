from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class ListCustomersOverCreditLimitParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OverLimitCustomerOut(BaseModel):
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float


class ListCustomersOverCreditLimitResult(BaseModel):
    customers: list[OverLimitCustomerOut]


async def list_customers_over_credit_limit_handler(
    params: ListCustomersOverCreditLimitParams, context: ToolContext
) -> ListCustomersOverCreditLimitResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    exposures = await service.list_customers_over_credit_limit()
    return ListCustomersOverCreditLimitResult(
        customers=[
            OverLimitCustomerOut(
                customer_code=exposure.customer_code, customer_name=exposure.customer_name,
                outstanding_balance=exposure.outstanding_balance, credit_limit=exposure.credit_limit,
                utilization_percent=exposure.utilization_percent,
            )
            for exposure in exposures
        ]
    )


LIST_CUSTOMERS_OVER_CREDIT_LIMIT_TOOL = ToolSpec(
    name="list_customers_over_credit_limit",
    description=(
        "Returns only the customers whose current outstanding AR balance "
        "exceeds their approved credit limit, ranked by utilization "
        "percentage (worst first). Takes no parameters. Use this for "
        "'which customers are over their credit limit?' or 'who's "
        "exceeded their limit?' - a narrower, pre-filtered version of "
        "get_credit_exposure. Use get_credit_exposure instead when the "
        "user wants one specific customer's exposure, over limit or not."
    ),
    parameters_model=ListCustomersOverCreditLimitParams,
    result_model=ListCustomersOverCreditLimitResult,
    handler=list_customers_over_credit_limit_handler,
)
