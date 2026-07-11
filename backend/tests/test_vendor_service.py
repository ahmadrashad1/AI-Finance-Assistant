from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.services.vendor_service import VendorBalance, VendorService


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


def _service(db_session: AsyncSession) -> VendorService:
    return VendorService(PurchaseOrderRepository(db_session), VendorRepository(db_session))


@pytest.mark.asyncio
async def test_get_vendor_balance_sums_approved_and_received_purchase_orders(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session, "VEND-2001", "Summit Traders")
    po_repo = PurchaseOrderRepository(db_session)
    await po_repo.create(
        po_number="PO-3001", vendor_id=vendor.id, order_date=date(2026, 3, 1),
        status="approved", total_amount=Decimal("1000.00"),
    )
    await po_repo.create(
        po_number="PO-3002", vendor_id=vendor.id, order_date=date(2026, 1, 1),
        status="received", total_amount=Decimal("2000.00"),
    )
    await po_repo.create(
        po_number="PO-3003", vendor_id=vendor.id, order_date=date(2026, 2, 1),
        status="draft", total_amount=Decimal("500.00"),
    )
    await po_repo.create(
        po_number="PO-3004", vendor_id=vendor.id, order_date=date(2026, 2, 1),
        status="cancelled", total_amount=Decimal("9999.00"),
    )
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")

    assert isinstance(balance, VendorBalance)
    assert balance.vendor_code == "VEND-2001"
    assert balance.total_outstanding == Decimal("3000.00")
    assert balance.open_purchase_order_count == 2
    assert balance.oldest_order_date == date(2026, 1, 1)


@pytest.mark.asyncio
async def test_get_vendor_balance_is_case_insensitive(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2101", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="summit traders")

    assert balance.vendor_code == "VEND-2101"


@pytest.mark.asyncio
async def test_get_vendor_balance_with_no_open_purchase_orders_returns_zero(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_vendor(db_session, "VEND-2201", "Summit Traders")
    await db_session.commit()

    balance = await _service(db_session).get_vendor_balance(vendor_name="Summit Traders")

    assert balance.total_outstanding == Decimal("0")
    assert balance.open_purchase_order_count == 0
    assert balance.oldest_order_date is None


@pytest.mark.asyncio
async def test_get_vendor_balance_unknown_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    with pytest.raises(ValueError, match="Vendor not found"):
        await _service(db_session).get_vendor_balance(vendor_name="Does Not Exist Traders")
