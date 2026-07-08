from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository


async def _make_vendor(db_session: AsyncSession, code: str = "VEND-0001") -> object:
    vendor_repo = VendorRepository(db_session)
    return await vendor_repo.create(
        vendor_code=code, company_name="Test Vendor", category="raw_materials",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )


@pytest.mark.asyncio
async def test_create_and_get_by_number(clean_db: None, db_session: AsyncSession) -> None:
    vendor = await _make_vendor(db_session)
    repo = PurchaseOrderRepository(db_session)
    po = await repo.create(
        po_number="PO-1001",
        vendor_id=vendor.id,
        order_date=date(2026, 1, 15),
        status="approved",
        total_amount=Decimal("5000.00"),
    )
    await db_session.commit()

    fetched = await repo.get_by_number("PO-1001")
    assert fetched is not None
    assert fetched.id == po.id
    assert fetched.approved_by is None


@pytest.mark.asyncio
async def test_list_by_vendor_orders_by_order_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor = await _make_vendor(db_session)
    repo = PurchaseOrderRepository(db_session)
    await repo.create(
        po_number="PO-1002", vendor_id=vendor.id, order_date=date(2026, 2, 1),
        status="received", total_amount=Decimal("1000.00"),
    )
    await repo.create(
        po_number="PO-1001", vendor_id=vendor.id, order_date=date(2026, 1, 1),
        status="received", total_amount=Decimal("2000.00"),
    )
    await db_session.commit()

    purchase_orders = await repo.list_by_vendor(vendor.id)
    assert [po.po_number for po in purchase_orders] == ["PO-1001", "PO-1002"]
