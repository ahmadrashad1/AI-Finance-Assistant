from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean
from typing import Final

from domains.finance.models import CustomerModel, InvoiceModel, PaymentModel
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository

UNPAID_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
TREND_THRESHOLD_DAYS: Final[int] = 5
MINIMUM_INVOICES_FOR_TREND: Final[int] = 4


@dataclass(frozen=True)
class PaymentBehavior:
    customer_code: str
    customer_name: str
    average_days_to_pay: float | None
    late_payment_count: int
    longest_delay_days: int
    trend: str
    paid_invoice_count: int


@dataclass(frozen=True)
class CreditExposure:
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal
    utilization_percent: float
    over_limit: bool


@dataclass(frozen=True)
class CreditRiskProfile:
    customer_code: str
    customer_name: str
    exposure: CreditExposure
    payment_behavior: PaymentBehavior
    total_invoice_count: int
    unpaid_invoice_count: int
    overdue_invoice_count: int


class CreditService:
    """Business logic for credit management: payment-behavior trend
    detection and credit exposure/utilization. `assess_credit_risk`
    returns evidence and deterministic indicators only - never a
    recommendation; that judgment belongs to Phase 2 reasoning over this
    evidence (PRD Ch.21 Domain 2 - an architectural boundary, not a
    style choice).
    """

    def __init__(
        self,
        customer_repository: CustomerRepository,
        invoice_repository: InvoiceRepository,
        payment_repository: PaymentRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._invoice_repository = invoice_repository
        self._payment_repository = payment_repository

    async def _resolve_customer(self, customer_id: str) -> CustomerModel:
        customer = await self._customer_repository.get_by_code(customer_id)
        if customer is None:
            raise ValueError(f"Customer not found: {customer_id}")
        return customer

    def _days_late(self, invoice: InvoiceModel, payments: list[PaymentModel]) -> int | None:
        if invoice.status != "paid" or not payments:
            return None
        last_payment_date = max(payment.payment_date for payment in payments)
        return (last_payment_date - invoice.due_date).days

    async def get_customer_payment_behavior(self, *, customer_id: str) -> PaymentBehavior:
        customer = await self._resolve_customer(customer_id)
        invoices = await self._invoice_repository.list_by_customer(customer.id)
        payments = await self._payment_repository.list_by_customer(customer.id)
        payments_by_invoice: dict[uuid.UUID, list[PaymentModel]] = {}
        for payment in payments:
            payments_by_invoice.setdefault(payment.invoice_id, []).append(payment)

        paid_invoices = sorted(
            (invoice for invoice in invoices if invoice.status == "paid"),
            key=lambda invoice: invoice.due_date,
        )
        lateness: list[int] = []
        for invoice in paid_invoices:
            days_late = self._days_late(invoice, payments_by_invoice.get(invoice.id, []))
            if days_late is not None:
                lateness.append(days_late)

        average_days_to_pay = mean(lateness) if lateness else None
        late_payment_count = sum(1 for days in lateness if days > 0)
        longest_delay_days = max((days for days in lateness if days > 0), default=0)

        if len(lateness) < MINIMUM_INVOICES_FOR_TREND:
            trend = "insufficient_data"
        else:
            midpoint = len(lateness) // 2
            first_half_avg = mean(lateness[:midpoint])
            second_half_avg = mean(lateness[midpoint:])
            if second_half_avg - first_half_avg > TREND_THRESHOLD_DAYS:
                trend = "deteriorating"
            elif first_half_avg - second_half_avg > TREND_THRESHOLD_DAYS:
                trend = "improving"
            else:
                trend = "stable"

        return PaymentBehavior(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            average_days_to_pay=average_days_to_pay,
            late_payment_count=late_payment_count,
            longest_delay_days=longest_delay_days,
            trend=trend,
            paid_invoice_count=len(paid_invoices),
        )

    async def _exposure_for(self, customer: CustomerModel) -> CreditExposure:
        unpaid = await self._invoice_repository.list_by_statuses(
            statuses=UNPAID_STATUSES, customer_id=customer.id
        )
        outstanding = sum((invoice.balance for invoice in unpaid), Decimal("0"))
        utilization = (
            float(outstanding / customer.credit_limit * 100) if customer.credit_limit > 0 else 0.0
        )
        return CreditExposure(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            outstanding_balance=outstanding,
            credit_limit=customer.credit_limit,
            utilization_percent=utilization,
            over_limit=outstanding > customer.credit_limit,
        )

    async def get_credit_exposure(self, *, customer_id: str | None = None) -> list[CreditExposure]:
        if customer_id is not None:
            customer = await self._resolve_customer(customer_id)
            return [await self._exposure_for(customer)]
        customers = await self._customer_repository.list_all()
        return [await self._exposure_for(customer) for customer in customers]

    async def list_customers_over_credit_limit(self) -> list[CreditExposure]:
        exposures = await self.get_credit_exposure()
        over_limit = [exposure for exposure in exposures if exposure.over_limit]
        over_limit.sort(key=lambda exposure: exposure.utilization_percent, reverse=True)
        return over_limit

    async def assess_credit_risk(self, *, customer_id: str) -> CreditRiskProfile:
        customer = await self._resolve_customer(customer_id)
        exposure = await self._exposure_for(customer)
        payment_behavior = await self.get_customer_payment_behavior(customer_id=customer_id)
        invoices = await self._invoice_repository.list_by_customer(customer.id)
        unpaid_count = sum(1 for invoice in invoices if invoice.status in UNPAID_STATUSES)
        overdue_count = sum(1 for invoice in invoices if invoice.status == "overdue")
        return CreditRiskProfile(
            customer_code=customer.customer_code,
            customer_name=customer.company_name,
            exposure=exposure,
            payment_behavior=payment_behavior,
            total_invoice_count=len(invoices),
            unpaid_invoice_count=unpaid_count,
            overdue_invoice_count=overdue_count,
        )
