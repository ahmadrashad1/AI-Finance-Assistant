from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository


async def _make_invoice(
    db_session: AsyncSession, *, due_date: date, total: Decimal = Decimal("1000.00")
) -> object:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-0001", company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    return await invoice_repo.create(
        invoice_number="INV-7001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=due_date, status="sent",
        subtotal=total, tax=Decimal("0"), total=total,
    )


@pytest.mark.asyncio
async def test_full_payment_marks_invoice_paid(clean_db: None, db_session: AsyncSession) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("1000.00"),
        payment_method="bank_transfer", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.amount_paid == Decimal("1000.00")
    assert invoice.balance == Decimal("0.00")
    assert invoice.status == "paid"


@pytest.mark.asyncio
async def test_partial_payment_before_due_date_is_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.balance == Decimal("600.00")
    assert invoice.status == "partially_paid"


@pytest.mark.asyncio
async def test_partial_payment_after_due_date_is_overdue_not_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 1, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await db_session.commit()

    assert invoice.balance == Decimal("600.00")
    assert invoice.status == "overdue"


@pytest.mark.asyncio
async def test_list_by_invoice_returns_all_payments(
    clean_db: None, db_session: AsyncSession
) -> None:
    invoice = await _make_invoice(db_session, due_date=date(2026, 12, 1))
    repo = PaymentRepository(db_session)
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 1), amount=Decimal("400.00"),
        payment_method="check", today=date(2026, 7, 8),
    )
    await repo.record_payment(
        invoice_id=invoice.id, payment_date=date(2026, 6, 15), amount=Decimal("600.00"),
        payment_method="bank_transfer", today=date(2026, 7, 8),
    )
    await db_session.commit()

    payments = await repo.list_by_invoice(invoice.id)
    assert len(payments) == 2
    assert invoice.status == "paid"


@pytest.mark.asyncio
async def test_record_payment_raises_for_nonexistent_invoice(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = PaymentRepository(db_session)
    nonexistent_invoice_id = uuid.uuid4()

    with pytest.raises(ValueError, match=f"Invoice {nonexistent_invoice_id} does not exist"):
        await repo.record_payment(
            invoice_id=nonexistent_invoice_id,
            payment_date=date(2026, 6, 1),
            amount=Decimal("100.00"),
            payment_method="check",
            today=date(2026, 7, 8),
        )
