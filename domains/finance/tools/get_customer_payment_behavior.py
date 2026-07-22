from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class GetCustomerPaymentBehaviorParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str


class GetCustomerPaymentBehaviorResult(BaseModel):
    customer_code: str
    customer_name: str
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


async def get_customer_payment_behavior_handler(
    params: GetCustomerPaymentBehaviorParams, context: ToolContext
) -> GetCustomerPaymentBehaviorResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    behavior = await service.get_customer_payment_behavior(customer_id=params.customer_id)
    return GetCustomerPaymentBehaviorResult(**behavior.__dict__)


GET_CUSTOMER_PAYMENT_BEHAVIOR_TOOL = ToolSpec(
    name="get_customer_payment_behavior",
    description=(
        "Returns one customer's payment pattern: average days to pay "
        "(positive = late, negative = early; null if no fully paid "
        "invoices yet), late-payment count, longest delay, trend "
        "('improving'/'deteriorating'/'stable'/'insufficient_data' if "
        "fewer than 4 paid invoices), and sample size. Requires "
        "customer_id (e.g. 'CUST-0007' - use get_customer first if only "
        "a company name is given). Does NOT return balance or credit "
        "limit (use get_credit_exposure). Use for 'is Customer X paying "
        "slower than before?' or 'what's Customer X's payment history?'."
    ),
    parameters_model=GetCustomerPaymentBehaviorParams,
    result_model=GetCustomerPaymentBehaviorResult,
    handler=get_customer_payment_behavior_handler,
)
