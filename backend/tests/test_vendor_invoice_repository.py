from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import (
    VendorInvoiceRepository,
    compute_vendor_invoice_status,
)
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


def test_compute_vendor_invoice_status_cancelled_and_draft_are_preserved() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="cancelled",
    ) == "cancelled"
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="draft",
    ) == "draft"


def test_compute_vendor_invoice_status_paid_beats_overdue() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("100"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "paid"


def test_compute_vendor_invoice_status_overdue_beats_partially_paid() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("40"), due_date=date(2026, 1, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "overdue"


def test_compute_vendor_invoice_status_partially_paid_when_not_yet_due() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("40"), due_date=date(2026, 12, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "partially_paid"


def test_compute_vendor_invoice_status_sent_when_unpaid_and_not_due() -> None:
    assert compute_vendor_invoice_status(
        total=Decimal("100"), amount_paid=Decimal("0"), due_date=date(2026, 12, 1),
        as_of=date(2026, 6, 1), current_status="sent",
    ) == "sent"


@pytest.mark.asyncio
async def test_create_and_get_by_number(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    repo = VendorInvoiceRepository(db_session)
    invoice = await repo.create(
        vendor_invoice_number="VINV-0001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 1, 31), status="sent",
        subtotal=Decimal("1000"), tax=Decimal("0"), total=Decimal("1000"),
    )
    await db_session.commit()

    fetched = await repo.get_by_number("VINV-0001")
    assert fetched is not None
    assert fetched.id == invoice.id
    assert fetched.balance == Decimal("1000")
    assert fetched.amount_paid == Decimal("0")


@pytest.mark.asyncio
async def test_list_by_vendor_orders_by_issue_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-1101")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1102", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1101", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_vendor(vendor.id)
    assert [r.vendor_invoice_number for r in results] == ["VINV-1101", "VINV-1102"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_status_and_vendor(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-1201")
    vendor_b = await _make_vendor(db_session, "VEND-1202")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1201", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1202", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1203", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("overdue",), vendor_id=vendor_a.id)
    assert [r.vendor_invoice_number for r in results] == ["VINV-1201"]


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_minimum_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-1301")
    repo = VendorInvoiceRepository(db_session)
    await repo.create(
        vendor_invoice_number="VINV-1301", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    await repo.create(
        vendor_invoice_number="VINV-1302", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    results = await repo.list_by_statuses(statuses=("sent",), minimum_balance=Decimal("100"))
    assert [r.vendor_invoice_number for r in results] == ["VINV-1302"]


@pytest.mark.asyncio
async def test_create_and_get_by_id(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    repo = VendorInvoiceRepository(db_session)
    invoice = await repo.create(
        vendor_invoice_number="VINV-0002", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 1, 31), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    fetched = await repo.get_by_id(invoice.id)
    assert fetched is not None
    assert fetched.id == invoice.id
    assert fetched.vendor_invoice_number == "VINV-0002"
    assert fetched.balance == Decimal("500")
    assert fetched.amount_paid == Decimal("0")


@pytest.mark.asyncio
async def test_list_by_statuses_filters_by_vendor_and_minimum_balance(
    clean_db: None, db_session: AsyncSession
) -> None:
    """Verify that vendor_id and minimum_balance genuinely AND together.

    This test proves that list_by_statuses requires BOTH filters to be satisfied,
    not just either one independently.
    """
    vendor_a = await _make_vendor(db_session, "VEND-1401")
    vendor_b = await _make_vendor(db_session, "VEND-1402")
    repo = VendorInvoiceRepository(db_session)

    # vendor_a: high balance, sent status
    await repo.create(
        vendor_invoice_number="VINV-1401", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    # vendor_a: low balance, sent status (fails minimum_balance)
    await repo.create(
        vendor_invoice_number="VINV-1402", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 1, 2), due_date=date(2026, 2, 2), status="sent",
        subtotal=Decimal("50"), tax=Decimal("0"), total=Decimal("50"),
    )
    # vendor_b: high balance, sent status (fails vendor_id)
    await repo.create(
        vendor_invoice_number="VINV-1403", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 1, 3), due_date=date(2026, 2, 3), status="sent",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    # Only VINV-1401 should match: vendor_a AND balance >= 100
    results = await repo.list_by_statuses(
        statuses=("sent",), vendor_id=vendor_a.id, minimum_balance=Decimal("100")
    )
    assert [r.vendor_invoice_number for r in results] == ["VINV-1401"]
