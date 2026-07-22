from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import BankAccountModel
from domains.finance.repositories.cash_repository import CashRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.purchase_requisition_repository import (
    PurchaseRequisitionRepository,
)
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.cash_flow_service import CashFlowService
from domains.finance.services.credit_service import CreditService
from domains.finance.simulation import simulation_today


def _service(db_session: AsyncSession) -> CashFlowService:
    credit_service = CreditService(
        CustomerRepository(db_session), InvoiceRepository(db_session), PaymentRepository(db_session)
    )
    return CashFlowService(
        CashRepository(db_session),
        CustomerRepository(db_session),
        InvoiceRepository(db_session),
        VendorRepository(db_session),
        VendorInvoiceRepository(db_session),
        PurchaseRequisitionRepository(db_session),
        PurchaseOrderRepository(db_session),
        credit_service,
    )


async def _make_bank_account(db_session: AsyncSession, opening_balance: Decimal) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating Account", opening_balance=opening_balance,
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.flush()


async def _make_customer(db_session: AsyncSession, code: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=f"{code} Corp", industry="manufacturing",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000"),
    )


async def _make_vendor(
    db_session: AsyncSession, code: str, payment_terms: str = "net_30", preferred: bool = False
) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=f"{code} Vendor", category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com",
        payment_terms=payment_terms, preferred=preferred,
    )


@pytest.mark.asyncio
async def test_expected_inflows_unadjusted_for_customer_with_no_history(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6001")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 15), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    inflows = await _service(db_session).get_expected_inflows(
        date_from=date(2026, 7, 10), date_to=date(2026, 7, 20)
    )
    assert len(inflows) == 1
    assert inflows[0].expected_receipt_date == date(2026, 7, 15)
    assert inflows[0].adjusted_for_payment_behavior is False


@pytest.mark.asyncio
async def test_expected_inflows_shifted_by_late_paying_customer_history(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6002")
    invoice_repo = InvoiceRepository(db_session)
    payment_repo = PaymentRepository(db_session)
    due_dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    for index, due in enumerate(due_dates):
        invoice = await invoice_repo.create(
            invoice_number=f"INV-61{index}", customer_id=customer.id, purchase_order_id=None,
            issue_date=due, due_date=due, status="sent",
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
        paid_date = due + timedelta(days=20)
        await payment_repo.record_payment(
            invoice_id=invoice.id, payment_date=paid_date, amount=Decimal("100"),
            payment_method="bank_transfer", today=paid_date,
        )
    unpaid_due = date(2026, 7, 1)
    await invoice_repo.create(
        invoice_number="INV-6120", customer_id=customer.id, purchase_order_id=None,
        issue_date=unpaid_due, due_date=unpaid_due, status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    inflows = await _service(db_session).get_expected_inflows(
        date_from=date(2026, 7, 15), date_to=date(2026, 7, 25)
    )
    assert len(inflows) == 1
    assert inflows[0].expected_receipt_date == date(2026, 7, 21)  # due + 20 days
    assert inflows[0].adjusted_for_payment_behavior is True


@pytest.mark.asyncio
async def test_expected_outflows_combines_all_three_sources(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-6001", payment_terms="net_15")
    vendor_invoice_repo = VendorInvoiceRepository(db_session)
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 10), status="sent",
        subtotal=Decimal("400"), tax=Decimal("0"), total=Decimal("400"),
    )
    purchase_order_repo = PurchaseOrderRepository(db_session)
    await purchase_order_repo.create(
        po_number="PO-6001", vendor_id=vendor.id, order_date=date(2026, 6, 26),
        status="approved", total_amount=Decimal("600"),
    )  # order_date + 15 days (net_15) = 2026-07-11
    await db_session.commit()

    outflows = await _service(db_session).get_expected_outflows(
        date_from=date(2026, 7, 1), date_to=date(2026, 7, 15)
    )
    sources = {outflow.source for outflow in outflows}
    assert "vendor_invoice" in sources
    assert "purchase_order" in sources
    total = sum((outflow.amount for outflow in outflows), Decimal("0"))
    assert total == Decimal("1000")


@pytest.mark.asyncio
async def test_forecast_cash_flow_chains_opening_to_prior_closing(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_bank_account(db_session, Decimal("10000"))
    await db_session.commit()

    forecast = await _service(db_session).forecast_cash_flow(weeks=3)
    assert len(forecast.periods) == 3
    assert forecast.periods[0].opening_balance == Decimal("10000")
    for earlier, later in zip(forecast.periods[:-1], forecast.periods[1:], strict=True):
        assert later.opening_balance == earlier.closing_balance


@pytest.mark.asyncio
async def test_forecast_cash_flow_rejects_out_of_range_weeks(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="weeks must be between 1 and 26"):
        await _service(db_session).forecast_cash_flow(weeks=27)
    with pytest.raises(ValueError, match="weeks must be between 1 and 26"):
        await _service(db_session).forecast_cash_flow(weeks=0)


@pytest.mark.asyncio
async def test_payment_prioritization_ranks_preferred_vendor_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    preferred = await _make_vendor(db_session, "VEND-6101", preferred=True)
    regular = await _make_vendor(db_session, "VEND-6102", preferred=False)
    vendor_invoice_repo = VendorInvoiceRepository(db_session)
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6101", vendor_id=regular.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 6, 15), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await vendor_invoice_repo.create(
        vendor_invoice_number="VINV-6102", vendor_id=preferred.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    prioritization = await _service(db_session).get_payment_prioritization()
    assert prioritization.items[0].vendor_invoice_number == "VINV-6102"
    assert prioritization.items[0].vendor_preferred is True


@pytest.mark.asyncio
async def test_expected_inflows_window_containing_today_includes_overdue_invoice(
    clean_db: None, db_session: AsyncSession
) -> None:
    """An already-overdue receivable (expected_receipt_date in the past) is
    rolled into the window that contains "today" - scenario 3."""
    today = simulation_today()
    customer = await _make_customer(db_session, "CUST-6201")
    invoice_repo = InvoiceRepository(db_session)
    overdue_due_date = today - timedelta(days=10)
    await invoice_repo.create(
        invoice_number="INV-6201", customer_id=customer.id, purchase_order_id=None,
        issue_date=overdue_due_date - timedelta(days=30), due_date=overdue_due_date,
        status="overdue", subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    await db_session.commit()

    inflows = await _service(db_session).get_expected_inflows(
        date_from=today, date_to=today + timedelta(days=6)
    )
    assert len(inflows) == 1
    # The true (past) expected_receipt_date is preserved on the record, even
    # though it was clamped to "today" only for the window-membership check.
    assert inflows[0].expected_receipt_date == overdue_due_date
    assert inflows[0].amount == Decimal("750")


@pytest.mark.asyncio
async def test_expected_inflows_future_window_excludes_overdue_invoice(
    clean_db: None, db_session: AsyncSession
) -> None:
    """A future window that does not contain "today" must NOT sweep in an
    overdue receivable - overdue AR is "expected now," not "expected next
    month" - scenario 2."""
    today = simulation_today()
    customer = await _make_customer(db_session, "CUST-6202")
    invoice_repo = InvoiceRepository(db_session)
    overdue_due_date = today - timedelta(days=10)
    await invoice_repo.create(
        invoice_number="INV-6202", customer_id=customer.id, purchase_order_id=None,
        issue_date=overdue_due_date - timedelta(days=30), due_date=overdue_due_date,
        status="overdue", subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    await db_session.commit()

    next_month_start = today.replace(day=1) + timedelta(days=32)
    next_month_start = next_month_start.replace(day=1)
    next_month_end = next_month_start + timedelta(days=27)
    inflows = await _service(db_session).get_expected_inflows(
        date_from=next_month_start, date_to=next_month_end
    )
    assert inflows == []


@pytest.mark.asyncio
async def test_forecast_cash_flow_places_overdue_invoice_in_current_week_only(
    clean_db: None, db_session: AsyncSession
) -> None:
    """scenario 1: forecast_cash_flow(weeks=4) with an overdue invoice must
    count it exactly once, in week 0, and never in weeks 1-3 - it must not
    be dropped entirely (the original bug) nor double-counted across weeks."""
    await _make_bank_account(db_session, Decimal("10000"))
    today = simulation_today()
    customer = await _make_customer(db_session, "CUST-6203")
    invoice_repo = InvoiceRepository(db_session)
    overdue_due_date = today - timedelta(days=10)
    await invoice_repo.create(
        invoice_number="INV-6203", customer_id=customer.id, purchase_order_id=None,
        issue_date=overdue_due_date - timedelta(days=30), due_date=overdue_due_date,
        status="overdue", subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    await db_session.commit()

    forecast = await _service(db_session).forecast_cash_flow(weeks=4)
    assert len(forecast.periods) == 4
    assert forecast.periods[0].inflows == Decimal("750")
    assert forecast.periods[1].inflows == Decimal("0")
    assert forecast.periods[2].inflows == Decimal("0")
    assert forecast.periods[3].inflows == Decimal("0")

