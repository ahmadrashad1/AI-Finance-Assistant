from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
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
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-9601", vendor_id=summit.id, purchase_order_id=None,
        issue_date=date(2026, 3, 1), due_date=date(2026, 4, 1), status="sent",
        subtotal=Decimal("4000.00"), tax=Decimal("0"), total=Decimal("4000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9602", vendor_id=summit.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="paid",
        subtotal=Decimal("9999.00"), tax=Decimal("0"), total=Decimal("9999.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9603", vendor_id=other.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="overdue",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_balance_handler(
        GetVendorBalanceParams(vendor_name="Summit Traders"), context
    )

    assert result.vendor_code == "VEND-9601"
    assert result.total_outstanding == Decimal("4000.00")
    assert result.open_invoice_count == 1
    assert result.oldest_due_date == date(2026, 4, 1)


@pytest.mark.asyncio
async def test_seeded_db_unknown_vendor_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Vendor not found"):
        await get_vendor_balance_handler(
            GetVendorBalanceParams(vendor_name="Does Not Exist Traders"), context
        )
