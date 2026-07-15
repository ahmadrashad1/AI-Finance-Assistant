from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.credit_service import CreditService


def _service(db_session: AsyncSession) -> CreditService:
    return CreditService(
        CustomerRepository(db_session), InvoiceRepository(db_session), PaymentRepository(db_session)
    )


async def _make_customer(
    db_session: AsyncSession, code: str, credit_limit: Decimal = Decimal("50000")
) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=f"{code} Corp", industry="manufacturing",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=credit_limit,
    )


async def _paid_invoice(
    db_session: AsyncSession, customer: object, number: str, due_date: date, payment_date: date
) -> None:
    invoice_repo = InvoiceRepository(db_session)
    invoice = await invoice_repo.create(
        invoice_number=number, customer_id=customer.id, purchase_order_id=None,
        issue_date=due_date, due_date=due_date, status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    payment_repo = PaymentRepository(db_session)
    await payment_repo.record_payment(
        invoice_id=invoice.id, payment_date=payment_date, amount=Decimal("1000"),
        payment_method="bank_transfer", today=payment_date,
    )


@pytest.mark.asyncio
async def test_payment_behavior_detects_deteriorating_trend(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7001")
    due_dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    lateness = [0, 2, 20, 40]
    for index, (due, delay) in enumerate(zip(due_dates, lateness, strict=True)):
        payment_date = due + timedelta(days=delay)
        await _paid_invoice(db_session, customer, f"INV-70{index}", due, payment_date)
    await db_session.commit()

    behavior = await _service(db_session).get_customer_payment_behavior(customer_id="CUST-7001")
    assert behavior.trend == "deteriorating"
    assert behavior.paid_invoice_count == 4
    assert behavior.late_payment_count == 3
    assert behavior.longest_delay_days == 40


@pytest.mark.asyncio
async def test_payment_behavior_insufficient_data_below_four_paid_invoices(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7002")
    await _paid_invoice(db_session, customer, "INV-7100", date(2026, 1, 1), date(2026, 1, 1))
    await db_session.commit()

    behavior = await _service(db_session).get_customer_payment_behavior(customer_id="CUST-7002")
    assert behavior.trend == "insufficient_data"


@pytest.mark.asyncio
async def test_payment_behavior_unknown_customer_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Customer not found"):
        await _service(db_session).get_customer_payment_behavior(customer_id="CUST-DOES-NOT-EXIST")


@pytest.mark.asyncio
async def test_credit_exposure_flags_over_limit(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7003", credit_limit=Decimal("500"))
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7200", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    [exposure] = await _service(db_session).get_credit_exposure(customer_id="CUST-7003")
    assert exposure.outstanding_balance == Decimal("1000")
    assert exposure.over_limit is True
    assert exposure.utilization_percent == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_list_customers_over_credit_limit_filters_and_sorts(
    clean_db: None, db_session: AsyncSession
) -> None:
    over = await _make_customer(db_session, "CUST-7004", credit_limit=Decimal("100"))
    under = await _make_customer(db_session, "CUST-7005", credit_limit=Decimal("100000"))
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7300", customer_id=over.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await invoice_repo.create(
        invoice_number="INV-7301", customer_id=under.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    over_limit = await _service(db_session).list_customers_over_credit_limit()
    assert [e.customer_code for e in over_limit] == ["CUST-7004"]


@pytest.mark.asyncio
async def test_assess_credit_risk_combines_exposure_and_behavior(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7006")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7400", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("300"), tax=Decimal("0"), total=Decimal("300"),
    )
    await db_session.commit()

    profile = await _service(db_session).assess_credit_risk(customer_id="CUST-7006")
    assert profile.exposure.outstanding_balance == Decimal("300")
    assert profile.total_invoice_count == 1
    assert profile.overdue_invoice_count == 1
    assert not hasattr(profile, "recommendation")
