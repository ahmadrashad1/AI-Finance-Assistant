from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


class AssessCreditRiskParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str


class ExposureOut(BaseModel):
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


class PaymentBehaviorOut(BaseModel):
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


class AssessCreditRiskResult(BaseModel):
    customer_code: str
    customer_name: str
    exposure: ExposureOut
    payment_behavior: PaymentBehaviorOut
    total_invoice_count: int
    unpaid_invoice_count: int
    overdue_invoice_count: int


async def assess_credit_risk_handler(
    params: AssessCreditRiskParams, context: ToolContext
) -> AssessCreditRiskResult:
    service = CreditService(
        CustomerRepository(context.db), InvoiceRepository(context.db), PaymentRepository(context.db)
    )
    profile = await service.assess_credit_risk(customer_id=params.customer_id)
    return AssessCreditRiskResult(
        customer_code=profile.customer_code,
        customer_name=profile.customer_name,
        exposure=ExposureOut(
            outstanding_balance=profile.exposure.outstanding_balance,
            credit_limit=profile.exposure.credit_limit,
            utilization_percent=profile.exposure.utilization_percent,
            over_limit=profile.exposure.over_limit,
        ),
        payment_behavior=PaymentBehaviorOut(
            average_days_to_pay=profile.payment_behavior.average_days_to_pay,
            late_payment_count=profile.payment_behavior.late_payment_count,
            longest_delay_days=profile.payment_behavior.longest_delay_days,
            trend=profile.payment_behavior.trend,
            paid_invoice_count=profile.payment_behavior.paid_invoice_count,
        ),
        total_invoice_count=profile.total_invoice_count,
        unpaid_invoice_count=profile.unpaid_invoice_count,
        overdue_invoice_count=profile.overdue_invoice_count,
    )


ASSESS_CREDIT_RISK_TOOL = ToolSpec(
    name="assess_credit_risk",
    description=(
        "Returns a combined risk PROFILE for one customer (business code "
        "required): credit exposure (balance, limit, utilization), "
        "payment behavior (average days to pay, late count, trend), and "
        "invoice counts (total, unpaid, overdue). This tool returns "
        "EVIDENCE ONLY - it never recommends increasing, decreasing, or "
        "holding a credit limit. Reason over the returned evidence "
        "yourself to answer judgment questions like 'should we increase "
        "Customer X's credit limit?' or 'is Customer X a credit risk?' - "
        "do not expect this tool to state a recommendation. Use the "
        "narrower get_credit_exposure or get_customer_payment_behavior "
        "instead when the user only wants one fact, not a full profile."
    ),
    parameters_model=AssessCreditRiskParams,
    result_model=AssessCreditRiskResult,
    handler=assess_credit_risk_handler,
)
