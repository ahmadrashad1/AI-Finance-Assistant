from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import (
    InvoiceRepository,
    compute_invoice_status,
)


async def _make_customer(db_session: AsyncSession, code: str = "CUST-0001") -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name="Test Customer", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("10000.00"),
    )


@pytest.mark.asyncio
async def test_create_sets_balance_to_total(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    invoice = await repo.create(
        invoice_number="INV-7001",
        customer_id=customer.id,
        purchase_order_id=None,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        status="sent",
        subtotal=Decimal("900.00"),
        tax=Decimal("100.00"),
        total=Decimal("1000.00"),
    )
    await db_session.commit()

    assert invoice.amount_paid == Decimal("0")
    assert invoice.balance == Decimal("1000.00")
    assert invoice.currency == "USD"


@pytest.mark.asyncio
async def test_list_by_customer_orders_by_issue_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7002", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    invoices = await repo.list_by_customer(customer.id)
    assert [i.invoice_number for i in invoices] == ["INV-7001", "INV-7002"]


@pytest.mark.asyncio
async def test_list_overdue_filters_by_status_and_due_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7003", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2025, 12, 1), due_date=date(2026, 1, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7004", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    overdue = await repo.list_overdue(as_of=date(2026, 7, 8))
    assert [i.invoice_number for i in overdue] == ["INV-7003"]


@pytest.mark.asyncio
async def test_list_overdue_and_semantics_due_date_future(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Verify that list_overdue uses AND logic: status=overdue AND due_date < as_of.

    This test proves that status=overdue with a future due_date is excluded from results,
    demonstrating the query requires BOTH conditions to be true, not just status.
    """
    customer = await _make_customer(db_session)
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7005", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 6, 1), due_date=date(2026, 8, 15), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    # Query as_of 2026-07-08, which is BEFORE the due_date of 2026-08-15
    # Even though status is "overdue", it should NOT be in the result
    overdue = await repo.list_overdue(as_of=date(2026, 7, 8))
    assert [i.invoice_number for i in overdue] == []


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_status_set(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7101")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7101", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7102", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent", "overdue"))
    assert [i.invoice_number for i in results] == ["INV-7101"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_customer_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-7201")
    globex = await _make_customer(db_session, "CUST-7202")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7201", customer_id=acme.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7202", customer_id=globex.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), customer_id=acme.id)
    assert [i.invoice_number for i in results] == ["INV-7201"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_minimum_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7301")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7301", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await repo.create(
        invoice_number="INV-7302", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), minimum_balance=Decimal("100"))
    assert [i.invoice_number for i in results] == ["INV-7302"]


def test_compute_invoice_status_priority_rule() -> None:
    common = {"total": Decimal("100"), "due_date": date(2026, 1, 1), "as_of": date(2026, 7, 8)}
    assert (
        compute_invoice_status(amount_paid=Decimal("0"), current_status="cancelled", **common)
        == "cancelled"
    )
    assert (
        compute_invoice_status(amount_paid=Decimal("0"), current_status="draft", **common)
        == "draft"
    )
    assert (
        compute_invoice_status(amount_paid=Decimal("100"), current_status="sent", **common)
        == "paid"
    )
    assert (
        compute_invoice_status(amount_paid=Decimal("40"), current_status="sent", **common)
        == "overdue"
    )
    not_yet_due = {
        "total": Decimal("100"), "due_date": date(2026, 12, 1), "as_of": date(2026, 7, 8)
    }
    assert (
        compute_invoice_status(amount_paid=Decimal("40"), current_status="sent", **not_yet_due)
        == "partially_paid"
    )
    assert (
        compute_invoice_status(amount_paid=Decimal("0"), current_status="sent", **not_yet_due)
        == "sent"
    )
    # Boundary: due_date == as_of is NOT yet overdue (strict less-than rule)
    equal_date = {
        "total": Decimal("100"), "due_date": date(2026, 7, 8), "as_of": date(2026, 7, 8)
    }
    assert (
        compute_invoice_status(amount_paid=Decimal("40"), current_status="sent", **equal_date)
        == "partially_paid"
    )
