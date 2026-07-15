from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class GetCreditExposureParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None


class CreditExposureOut(BaseModel):
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


class GetCreditExposureResult(BaseModel):
    exposures: list[CreditExposureOut]


async def get_credit_exposure_handler(
    params: GetCreditExposureParams, context: ToolContext
) -> GetCreditExposureResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    exposures = await service.get_credit_exposure(customer_id=params.customer_id)
    return GetCreditExposureResult(
        exposures=[CreditExposureOut(**exposure.__dict__) for exposure in exposures]
    )


GET_CREDIT_EXPOSURE_TOOL = ToolSpec(
    name="get_credit_exposure",
    description=(
        "Returns outstanding AR balance versus approved credit limit and "
        "utilization percentage, for one customer (pass customer_id, the "
        "business code) or every customer (omit customer_id). Does NOT "
        "return payment history or trend; use "
        "get_customer_payment_behavior for that. Does NOT filter to only "
        "customers over their limit; use list_customers_over_credit_limit "
        "for that narrower question. Use this for 'what's Customer X's "
        "credit exposure?' or 'how much of their credit limit are they "
        "using?'."
    ),
    parameters_model=GetCreditExposureParams,
    result_model=GetCreditExposureResult,
    handler=get_credit_exposure_handler,
)
