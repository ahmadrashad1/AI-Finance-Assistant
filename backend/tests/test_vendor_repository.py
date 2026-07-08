from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.repositories.vendor_repository import VendorRepository


@pytest.mark.asyncio
async def test_create_and_get_by_id(clean_db: None, db_session: AsyncSession) -> None:
    repo = VendorRepository(db_session)
    vendor = await repo.create(
        vendor_code="VEND-0001",
        company_name="Summit Traders",
        category="raw_materials",
        contact_name="Amy Chen",
        contact_email="amy.chen@example.com",
        payment_terms="net_30",
    )
    await db_session.commit()

    fetched = await repo.get_by_id(vendor.id)
    assert fetched is not None
    assert fetched.vendor_code == "VEND-0001"
    assert fetched.preferred is False
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_get_by_code_returns_none_when_missing(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = VendorRepository(db_session)
    await repo.create(
        vendor_code="VEND-0002",
        company_name="Cascade Logistics",
        category="logistics",
        contact_name="Bo Kim",
        contact_email="bo.kim@example.com",
        payment_terms="net_15",
        preferred=True,
    )
    await db_session.commit()

    fetched = await repo.get_by_code("VEND-0002")
    assert fetched is not None
    assert fetched.preferred is True
    assert await repo.get_by_code("VEND-9999") is None


@pytest.mark.asyncio
async def test_list_all_orders_by_vendor_code(clean_db: None, db_session: AsyncSession) -> None:
    repo = VendorRepository(db_session)
    await repo.create(
        vendor_code="VEND-0002", company_name="B Vendor", category="software",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
    )
    await repo.create(
        vendor_code="VEND-0001", company_name="A Vendor", category="software",
        contact_name="B", contact_email="b@example.com", payment_terms="net_30",
    )
    await db_session.commit()

    vendors = await repo.list_all()
    assert [v.vendor_code for v in vendors] == ["VEND-0001", "VEND-0002"]
