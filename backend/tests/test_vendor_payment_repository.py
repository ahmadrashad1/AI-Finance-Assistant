from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_payment_repository import VendorPaymentRepository
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


async def _make_vendor_invoice(
    db_session: AsyncSession, vendor_id: object, number: str = "VINV-0001",
    total: Decimal = Decimal("1000"), due_date: date = date(2026, 6, 1),
) -> object:
    repo = VendorInvoiceRepository(db_session)
    return await repo.create(
        vendor_invoice_number=number, vendor_id=vendor_id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=due_date, status="sent",
        subtotal=total, tax=Decimal("0"), total=total,
    )


@pytest.mark.asyncio
async def test_full_payment_marks_invoice_paid(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    invoice = await _make_vendor_invoice(db_session, vendor.id)
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("1000"), payment_method="bank_transfer", today=date(2026, 5, 20),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.balance == Decimal("0")
    assert updated.status == "paid"


@pytest.mark.asyncio
async def test_partial_payment_before_due_date_is_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0002")
    invoice = await _make_vendor_invoice(db_session, vendor.id, "VINV-0002")
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("400"), payment_method="check", today=date(2026, 5, 20),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.balance == Decimal("600")
    assert updated.status == "partially_paid"


@pytest.mark.asyncio
async def test_partial_payment_after_due_date_is_overdue_not_partially_paid(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0003")
    invoice = await _make_vendor_invoice(
        db_session, vendor.id, "VINV-0003", due_date=date(2026, 1, 1)
    )
    repo = VendorPaymentRepository(db_session)

    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 6, 1),
        amount=Decimal("400"), payment_method="check", today=date(2026, 6, 1),
    )
    await db_session.commit()

    invoice_repo = VendorInvoiceRepository(db_session)
    updated = await invoice_repo.get_by_id(invoice.id)
    assert updated is not None
    assert updated.status == "overdue"


@pytest.mark.asyncio
async def test_list_by_vendor_invoice_returns_all_payments(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-0004")
    invoice = await _make_vendor_invoice(db_session, vendor.id, "VINV-0004")
    repo = VendorPaymentRepository(db_session)
    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 10),
        amount=Decimal("300"), payment_method="check", today=date(2026, 5, 10),
    )
    await repo.record_payment(
        vendor_invoice_id=invoice.id, payment_date=date(2026, 5, 20),
        amount=Decimal("700"), payment_method="bank_transfer", today=date(2026, 5, 20),
    )
    await db_session.commit()

    payments = await repo.list_by_vendor_invoice(invoice.id)
    assert len(payments) == 2
    assert sorted(p.amount for p in payments) == [Decimal("300"), Decimal("700")]


@pytest.mark.asyncio
async def test_record_payment_raises_for_nonexistent_vendor_invoice(
    clean_db: None, db_session: AsyncSession
) -> None:
    import uuid

    repo = VendorPaymentRepository(db_session)
    with pytest.raises(ValueError, match="does not exist"):
        await repo.record_payment(
            vendor_invoice_id=uuid.uuid4(), payment_date=date(2026, 5, 20),
            amount=Decimal("100"), payment_method="check",
        )
