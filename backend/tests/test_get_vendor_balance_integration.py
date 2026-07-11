from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.purchase_order_repository import PurchaseOrderRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.tools.get_vendor_balance import (
    GetVendorBalanceParams,
    get_vendor_balance_handler,
)


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


@pytest.mark.asyncio
async def test_seeded_db_returns_correct_balance_for_named_vendor(
    clean_db: None, db_session: AsyncSession
) -> None:
    summit = await _make_vendor(db_session, "VEND-9601", "Summit Traders")
    other = await _make_vendor(db_session, "VEND-9602", "Cascade Logistics")
    po_repo = PurchaseOrderRepository(db_session)
    await po_repo.create(
        po_number="PO-9601", vendor_id=summit.id, order_date=date(2026, 3, 1),
        status="approved", total_amount=Decimal("4000.00"),
    )
    await po_repo.create(
        po_number="PO-9602", vendor_id=summit.id, order_date=date(2026, 1, 1),
        status="cancelled", total_amount=Decimal("9999.00"),
    )
    await po_repo.create(
        po_number="PO-9603", vendor_id=other.id, order_date=date(2026, 2, 1),
        status="approved", total_amount=Decimal("500.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_balance_handler(
        GetVendorBalanceParams(vendor_name="Summit Traders"), context
    )

    assert result.vendor_code == "VEND-9601"
    assert result.total_outstanding == Decimal("4000.00")
    assert result.open_purchase_order_count == 1
    assert result.oldest_order_date == date(2026, 3, 1)


@pytest.mark.asyncio
async def test_seeded_db_unknown_vendor_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Vendor not found"):
        await get_vendor_balance_handler(
            GetVendorBalanceParams(vendor_name="Does Not Exist Traders"), context
        )
