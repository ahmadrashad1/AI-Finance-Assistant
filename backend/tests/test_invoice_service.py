from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.repositories.payment_repository import PaymentRepository
from domains.finance.services.invoice_service import InvoiceService

AS_OF = date(2026, 7, 8)


async def _make_customer(db_session: AsyncSession, code: str, name: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=name, industry="Retail", contact_name="A",
        contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )


def _service(db_session: AsyncSession) -> InvoiceService:
    return InvoiceService(InvoiceRepository(db_session), CustomerRepository(db_session))


@pytest.mark.asyncio
async def test_unpaid_excludes_paid_draft_and_cancelled(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6001", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    for number, status in [("INV-6002", "paid"), ("INV-6003", "draft"), ("INV-6004", "cancelled")]:
        await invoice_repo.create(
            invoice_number=number, customer_id=customer.id, purchase_order_id=None,
            issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status=status,
            subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert [r.invoice_number for r in results] == ["INV-6001"]


@pytest.mark.asyncio
async def test_partially_paid_and_overdue_are_included(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6101", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    payment_repo = PaymentRepository(db_session)

    partially_paid = await invoice_repo.create(
        invoice_number="INV-6101", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await payment_repo.record_payment(
        invoice_id=partially_paid.id, payment_date=date(2026, 6, 1),
        amount=Decimal("400"), payment_method="check", today=AS_OF,
    )
    await invoice_repo.create(
        invoice_number="INV-6102", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert {r.invoice_number for r in results} == {"INV-6101", "INV-6102"}


@pytest.mark.asyncio
async def test_days_outstanding_is_zero_before_due_date_and_positive_after(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6201", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6201", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        invoice_number="INV-6202", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 6, 20), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)
    by_number = {r.invoice_number: r for r in results}

    assert by_number["INV-6201"].days_outstanding == 0
    assert by_number["INV-6202"].days_outstanding == (AS_OF - date(2026, 6, 20)).days


@pytest.mark.asyncio
async def test_sorts_by_materiality_largest_balance_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6301", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6301", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await invoice_repo.create(
        invoice_number="INV-6302", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(as_of=AS_OF)

    assert [r.invoice_number for r in results] == ["INV-6302", "INV-6301"]


@pytest.mark.asyncio
async def test_minimum_amount_filters_by_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-6401", "Acme Corp")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6401", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await invoice_repo.create(
        invoice_number="INV-6402", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(
        minimum_amount=Decimal("100"), as_of=AS_OF
    )

    assert [r.invoice_number for r in results] == ["INV-6402"]


@pytest.mark.asyncio
async def test_customer_id_resolves_business_code_to_internal_customer(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-6501", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-6502", "Globex Inc")
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-6501", customer_id=acme.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        invoice_number="INV-6502", customer_id=globex.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 12, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await _service(db_session).get_unpaid_invoices(
        customer_id="CUST-6501", as_of=AS_OF
    )

    assert [r.invoice_number for r in results] == ["INV-6501"]
    assert results[0].customer_name == "Acme Corp"


@pytest.mark.asyncio
async def test_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Customer not found"):
        await _service(db_session).get_unpaid_invoices(customer_id="CUST-DOES-NOT-EXIST")
