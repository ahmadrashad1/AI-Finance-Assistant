from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.credit_service import CreditService
from domains.finance.simulation import simulation_today

UNPAID_AR_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
UNPAID_AP_STATUSES: Final[tuple[str, ...]] = ("sent", "partially_paid", "overdue")
PAYMENT_TERM_DAYS: Final[dict[str, int]] = {
    "net_15": 15, "net_30": 30, "net_45": 45, "net_60": 60,
}
DEFAULT_TERM_DAYS: Final[int] = 30
MAX_FORECAST_WEEKS: Final[int] = 26


@dataclass(frozen=True)
class ExpectedInflow:
    invoice_number: str
    customer_code: str
    customer_name: str
    due_date: date
    expected_receipt_date: date
    amount: Decimal
    adjusted_for_payment_behavior: bool


@dataclass(frozen=True)
class ExpectedOutflow:
    source: str
    reference: str
    vendor_name: str | None
    expected_payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class CashFlowPeriod:
    period_start: date
    period_end: date
    opening_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class CashFlowForecast:
    periods: list[CashFlowPeriod]


@dataclass(frozen=True)
class PaymentPriorityItem:
    vendor_invoice_number: str
    vendor_name: str
    due_date: date
    balance: Decimal
    vendor_preferred: bool
    days_until_due: int


@dataclass(frozen=True)
class PaymentPrioritization:
    items: list[PaymentPriorityItem]
    available_cash: Decimal


class CashFlowService:
    """Business logic for cash flow forecasting. Expected inflows adjust
    each unpaid invoice's due date by that customer's historical average
    lateness (CreditService.get_customer_payment_behavior) - a positive
    average shifts the expected receipt later; a customer with no paid
    history is assumed to pay on time. Expected outflows combine vendor
    invoices already due, approved requisitions not yet converted to a
    PO (by needed_by_date), and open purchase orders (by order_date plus
    the vendor's payment-terms days, since a PO itself carries no due
    date). Both adjustment rules are deterministic, per PRD Ch.21
    Domain 3.
    """

    def __init__(
        self,
        cash_repository: CashRepository,
        customer_repository: CustomerRepository,
        invoice_repository: InvoiceRepository,
        vendor_repository: VendorRepository,
        vendor_invoice_repository: VendorInvoiceRepository,
        purchase_requisition_repository: PurchaseRequisitionRepository,
        purchase_order_repository: PurchaseOrderRepository,
        credit_service: CreditService,
    ) -> None:
        self._cash_repository = cash_repository
        self._customer_repository = customer_repository
        self._invoice_repository = invoice_repository
        self._vendor_repository = vendor_repository
        self._vendor_invoice_repository = vendor_invoice_repository
        self._purchase_requisition_repository = purchase_requisition_repository
        self._purchase_order_repository = purchase_order_repository
        self._credit_service = credit_service

    async def get_expected_inflows(self, *, date_from: date, date_to: date) -> list[ExpectedInflow]:
        today = simulation_today()
        invoices = await self._invoice_repository.list_by_statuses(statuses=UNPAID_AR_STATUSES)
        customers = await self._customer_repository.list_all()
        customers_by_id = {customer.id: customer for customer in customers}

        behavior_cache: dict[uuid.UUID, float | None] = {}
        results: list[ExpectedInflow] = []
        for invoice in invoices:
            customer = customers_by_id.get(invoice.customer_id)
            if customer is None:
                continue
            if customer.id not in behavior_cache:
                behavior = await self._credit_service.get_customer_payment_behavior(
                    customer_id=customer.customer_code
                )
                behavior_cache[customer.id] = behavior.average_days_to_pay
            average_days_to_pay = behavior_cache[customer.id]
            adjustment_days = max(0, round(average_days_to_pay)) if average_days_to_pay else 0
            expected_receipt_date = invoice.due_date + timedelta(days=adjustment_days)
            # Already-overdue receipts (expected_receipt_date before today) are
            # rolled into whichever window contains "today" - clamping against
            # the fixed simulation_today() reference, never against this call's
            # own date_from, so an overdue invoice is counted in exactly one
            # week's window instead of matching every window it's asked about.
            effective_receipt_date = (
                expected_receipt_date if expected_receipt_date >= today else today
            )
            if date_from <= effective_receipt_date <= date_to:
                results.append(
                    ExpectedInflow(
                        invoice_number=invoice.invoice_number,
                        customer_code=customer.customer_code,
                        customer_name=customer.company_name,
                        due_date=invoice.due_date,
                        expected_receipt_date=expected_receipt_date,
                        amount=invoice.balance,
                        adjusted_for_payment_behavior=adjustment_days > 0,
                    )
                )
        results.sort(key=lambda inflow: inflow.expected_receipt_date)
        return results

    async def get_expected_outflows(
        self, *, date_from: date, date_to: date
    ) -> list[ExpectedOutflow]:
        vendors = await self._vendor_repository.list_all()
        vendors_by_id = {vendor.id: vendor for vendor in vendors}
        results: list[ExpectedOutflow] = []

        vendor_invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=UNPAID_AP_STATUSES
        )
        for invoice in vendor_invoices:
            if date_from <= invoice.due_date <= date_to:
                vendor = vendors_by_id.get(invoice.vendor_id)
                results.append(
                    ExpectedOutflow(
                        source="vendor_invoice",
                        reference=invoice.vendor_invoice_number,
                        vendor_name=vendor.company_name if vendor else None,
                        expected_payment_date=invoice.due_date,
                        amount=invoice.balance,
                    )
                )

        requisitions = await self._purchase_requisition_repository.list_requisitions(
            status="approved"
        )
        for requisition in requisitions:
            if requisition.needed_by_date is None:
                continue
            if date_from <= requisition.needed_by_date <= date_to:
                results.append(
                    ExpectedOutflow(
                        source="purchase_requisition",
                        reference=requisition.requisition_number,
                        vendor_name=None,
                        expected_payment_date=requisition.needed_by_date,
                        amount=requisition.estimated_amount,
                    )
                )

        purchase_orders = await self._purchase_order_repository.list_by_statuses(
            statuses=("approved",)
        )
        for order in purchase_orders:
            vendor = vendors_by_id.get(order.vendor_id)
            term_days = (
                PAYMENT_TERM_DAYS.get(vendor.payment_terms, DEFAULT_TERM_DAYS)
                if vendor
                else DEFAULT_TERM_DAYS
            )
            expected_date = order.order_date + timedelta(days=term_days)
            if date_from <= expected_date <= date_to:
                results.append(
                    ExpectedOutflow(
                        source="purchase_order",
                        reference=order.po_number,
                        vendor_name=vendor.company_name if vendor else None,
                        expected_payment_date=expected_date,
                        amount=order.total_amount,
                    )
                )

        results.sort(key=lambda outflow: outflow.expected_payment_date)
        return results

    async def forecast_cash_flow(self, *, weeks: int) -> CashFlowForecast:
        if weeks < 1 or weeks > MAX_FORECAST_WEEKS:
            raise ValueError(f"weeks must be between 1 and {MAX_FORECAST_WEEKS}, got {weeks}")

        today = simulation_today()
        opening_balance = await self._cash_repository.get_balance_as_of(today)
        periods: list[CashFlowPeriod] = []
        for week_index in range(weeks):
            period_start = today + timedelta(days=7 * week_index)
            period_end = period_start + timedelta(days=6)
            inflows = await self.get_expected_inflows(date_from=period_start, date_to=period_end)
            outflows = await self.get_expected_outflows(date_from=period_start, date_to=period_end)
            inflow_total = sum((inflow.amount for inflow in inflows), Decimal("0"))
            outflow_total = sum((outflow.amount for outflow in outflows), Decimal("0"))
            closing_balance = opening_balance + inflow_total - outflow_total
            periods.append(
                CashFlowPeriod(
                    period_start=period_start, period_end=period_end,
                    opening_balance=opening_balance, inflows=inflow_total,
                    outflows=outflow_total, closing_balance=closing_balance,
                )
            )
            opening_balance = closing_balance
        return CashFlowForecast(periods=periods)

    async def get_payment_prioritization(self) -> PaymentPrioritization:
        today = simulation_today()
        available_cash = await self._cash_repository.get_balance_as_of(today)
        vendors = await self._vendor_repository.list_all()
        vendors_by_id = {vendor.id: vendor for vendor in vendors}
        vendor_invoices = await self._vendor_invoice_repository.list_by_statuses(
            statuses=UNPAID_AP_STATUSES
        )

        items: list[PaymentPriorityItem] = []
        for invoice in vendor_invoices:
            vendor = vendors_by_id.get(invoice.vendor_id)
            items.append(
                PaymentPriorityItem(
                    vendor_invoice_number=invoice.vendor_invoice_number,
                    vendor_name=vendor.company_name if vendor else "Unknown vendor",
                    due_date=invoice.due_date,
                    balance=invoice.balance,
                    vendor_preferred=vendor.preferred if vendor else False,
                    days_until_due=(invoice.due_date - today).days,
                )
            )
        items.sort(key=lambda item: (not item.vendor_preferred, item.due_date, -item.balance))
        return PaymentPrioritization(items=items, available_cash=available_cash)
