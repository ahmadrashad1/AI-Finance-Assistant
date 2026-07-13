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
from domains.finance.repositories.payment_repository import PaymentRepository


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


@pytest.mark.asyncio
async def test_search_filters_by_invoice_number(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7401")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7401", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7402", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.search(invoice_number="INV-7401")
    assert [i.invoice_number for i in results] == ["INV-7401"]


@pytest.mark.asyncio
async def test_search_filters_by_status(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7501")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7501", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7502", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.search(status="paid")
    assert [i.invoice_number for i in results] == ["INV-7501"]


@pytest.mark.asyncio
async def test_search_filters_by_amount_range(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7601")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7601", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await repo.create(
        invoice_number="INV-7602", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await repo.create(
        invoice_number="INV-7603", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("5000"), tax=Decimal("0"), total=Decimal("5000"),
    )
    await db_session.commit()

    results = await repo.search(minimum_amount=Decimal("100"), maximum_amount=Decimal("1000"))
    assert [i.invoice_number for i in results] == ["INV-7602"]


@pytest.mark.asyncio
async def test_search_amount_filters_on_total_not_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Regression test: verify amount filters use total, not balance.

    Creates an invoice with a partial payment so that total != balance,
    then searches by amount range. The search must filter on the invoice's
    face amount (total), not its outstanding balance. If someone accidentally
    swapped the filter to use balance instead of total, this test would fail.
    """
    customer = await _make_customer(db_session, "CUST-7701")
    invoice_repo = InvoiceRepository(db_session)
    payment_repo = PaymentRepository(db_session)

    # Create invoice with total=1000, initially balance=1000 (no payments)
    inv_with_payment = await invoice_repo.create(
        invoice_number="INV-7701", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("909.09"), tax=Decimal("90.91"), total=Decimal("1000.00"),
    )
    # Record a payment of 500, leaving balance=500 but total still=1000
    await payment_repo.record_payment(
        invoice_id=inv_with_payment.id, payment_date=date(2026, 1, 15),
        amount=Decimal("500.00"), payment_method="check",
    )

    # Create another invoice with total=700 (unchanged, balance=700)
    await invoice_repo.create(
        invoice_number="INV-7702", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("636.36"), tax=Decimal("63.64"), total=Decimal("700.00"),
    )
    await db_session.commit()

    # Refresh to see updated state
    inv_with_payment = await invoice_repo.get_by_id(inv_with_payment.id)
    assert inv_with_payment is not None
    assert inv_with_payment.total == Decimal("1000.00")
    assert inv_with_payment.balance == Decimal("500.00")

    # Search for invoices in range [700, 1000] on total (not balance)
    # Should return INV-7701 (total=1000 is in range, even though balance=500 is not)
    # and INV-7702 (total=700 is in range)
    results = await invoice_repo.search(
        minimum_amount=Decimal("700"), maximum_amount=Decimal("1000")
    )
    result_numbers = [i.invoice_number for i in results]
    assert set(result_numbers) == {"INV-7701", "INV-7702"}

    # Verify INV-7701 is in results (it must filter on total, not balance)
    inv_7701_result = next(i for i in results if i.invoice_number == "INV-7701")
    assert inv_7701_result.total == Decimal("1000.00")
    assert inv_7701_result.balance == Decimal("500.00")


@pytest.mark.asyncio
async def test_search_filters_by_due_date_range(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7701")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7701", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 1, 10), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        invoice_number="INV-7702", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 3, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.search(due_after=date(2026, 2, 1), due_before=date(2026, 4, 1))
    assert [i.invoice_number for i in results] == ["INV-7702"]


@pytest.mark.asyncio
async def test_search_with_no_filters_returns_everything(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7801")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7801", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="draft",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.search()
    assert [i.invoice_number for i in results] == ["INV-7801"]


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


@pytest.mark.asyncio
async def test_finds_a_duplicate_pair_same_customer_amount_and_close_dates(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7001")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("2000"), tax=Decimal("0"), total=Decimal("2000"),
    )
    await repo.create(
        invoice_number="INV-7002", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 2), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("2000"), tax=Decimal("0"), total=Decimal("2000"),
    )
    await db_session.commit()

    groups = await repo.find_potential_duplicate_groups()

    assert len(groups) == 1
    assert {invoice.invoice_number for invoice in groups[0]} == {"INV-7001", "INV-7002"}


@pytest.mark.asyncio
async def test_does_not_group_different_customers_or_amounts(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_a = await _make_customer(db_session, "CUST-7101")
    customer_b = await _make_customer(db_session, "CUST-7102")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7101", customer_id=customer_a.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await repo.create(
        invoice_number="INV-7102", customer_id=customer_b.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await repo.create(
        invoice_number="INV-7103", customer_id=customer_a.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("999"), tax=Decimal("0"), total=Decimal("999"),
    )
    await db_session.commit()

    groups = await repo.find_potential_duplicate_groups()

    assert groups == []


@pytest.mark.asyncio
async def test_does_not_group_dates_more_than_seven_days_apart(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7201")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7201", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    await repo.create(
        invoice_number="INV-7202", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 15), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("750"), tax=Decimal("0"), total=Decimal("750"),
    )
    await db_session.commit()

    groups = await repo.find_potential_duplicate_groups()

    assert groups == []


@pytest.mark.asyncio
async def test_excludes_cancelled_invoices(clean_db: None, db_session: AsyncSession) -> None:
    customer = await _make_customer(db_session, "CUST-7301")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7301", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("300"), tax=Decimal("0"), total=Decimal("300"),
    )
    await repo.create(
        invoice_number="INV-7302", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="cancelled",
        subtotal=Decimal("300"), tax=Decimal("0"), total=Decimal("300"),
    )
    await db_session.commit()

    groups = await repo.find_potential_duplicate_groups()

    assert groups == []


@pytest.mark.asyncio
async def test_invoice_number_filter_checks_only_that_invoices_own_group(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer = await _make_customer(db_session, "CUST-7401")
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number="INV-7401", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("1200"), tax=Decimal("0"), total=Decimal("1200"),
    )
    await repo.create(
        invoice_number="INV-7402", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 3, 2), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("1200"), tax=Decimal("0"), total=Decimal("1200"),
    )
    await repo.create(
        invoice_number="INV-7403", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 6, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await db_session.commit()

    groups = await repo.find_potential_duplicate_groups(invoice_number="INV-7401")
    assert len(groups) == 1
    assert {invoice.invoice_number for invoice in groups[0]} == {"INV-7401", "INV-7402"}

    no_dupes = await repo.find_potential_duplicate_groups(invoice_number="INV-7403")
    assert no_dupes == []

    unknown = await repo.find_potential_duplicate_groups(invoice_number="INV-9999")
    assert unknown == []
