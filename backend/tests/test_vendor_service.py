from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorBalance, VendorService


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


def _service(db_session: AsyncSession) -> VendorService:
    return VendorService(VendorInvoiceRepository(db_session), VendorRepository(db_session))


@pytest.mark.asyncio
async def test_get_vendor_balance_sums_outstanding_vendor_invoices(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-2001", "Summit Traders")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-3001", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("1000.00"), tax=Decimal("0"), total=Decimal("1000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3002", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("2000.00"), tax=Decimal("0"), total=Decimal("2000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-3003", vendor_id=vendor.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="paid",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")

    assert isinstance(balance, VendorBalance)
    assert balance.vendor_code == "VEND-2001"
    assert balance.total_outstanding == Decimal("3000.00")
    assert balance.open_invoice_count == 2
    assert balance.oldest_due_date == date(2026, 2, 1)


@pytest.mark.asyncio
async def test_get_vendor_balance_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2101", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="summit traders")
    assert balance.vendor_code == "VEND-2101"


@pytest.mark.asyncio
async def test_get_vendor_balance_with_no_outstanding_invoices_returns_zero(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2201", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")
    assert balance.total_outstanding == Decimal("0")
    assert balance.open_invoice_count == 0
    assert balance.oldest_due_date is None


@pytest.mark.asyncio
async def test_get_vendor_balance_unknown_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).get_vendor_balance(vendor_name="Does Not Exist Traders")
