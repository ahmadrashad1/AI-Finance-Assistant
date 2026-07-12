from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.vendor_invoice_repository import VendorInvoiceRepository
from domains.finance.repositories.vendor_repository import VendorRepository
from domains.finance.tools.get_vendor_invoices import (
    GetVendorInvoicesParams,
    get_vendor_invoices_handler,
)


async def _make_vendor(db_session: AsyncSession, code: str, name: str) -> object:
    repo = VendorRepository(db_session)
    return await repo.create(
        vendor_code=code, company_name=name, category="raw_materials",
        contact_name="A", contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
    )


@pytest.mark.asyncio
async def test_seeded_db_lists_outstanding_invoices_sorted_by_due_date(
    clean_db: None, db_session: AsyncSession
) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-9301", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-9302", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-9301", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 8, 1), status="sent",
        subtotal=Decimal("1000.00"), tax=Decimal("0"), total=Decimal("1000.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9302", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 6, 1), status="overdue",
        subtotal=Decimal("500.00"), tax=Decimal("0"), total=Decimal("500.00"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9303", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 6, 1), status="paid",
        subtotal=Decimal("999.00"), tax=Decimal("0"), total=Decimal("999.00"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_invoices_handler(GetVendorInvoicesParams(), context)

    assert [i.vendor_invoice_number for i in result.invoices] == ["VINV-9302", "VINV-9301"]
    assert result.summary.count == 2
    assert result.summary.total_outstanding == Decimal("1500.00")


@pytest.mark.asyncio
async def test_seeded_db_filters_by_vendor_id(clean_db: None, db_session: AsyncSession) -> None:
    vendor_a = await _make_vendor(db_session, "VEND-9401", "Summit Traders")
    vendor_b = await _make_vendor(db_session, "VEND-9402", "Cascade Logistics")
    invoice_repo = VendorInvoiceRepository(db_session)
    await invoice_repo.create(
        vendor_invoice_number="VINV-9401", vendor_id=vendor_a.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await invoice_repo.create(
        vendor_invoice_number="VINV-9402", vendor_id=vendor_b.id, purchase_order_id=None,
        issue_date=date(2026, 5, 1), due_date=date(2026, 7, 1), status="sent",
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_vendor_invoices_handler(
        GetVendorInvoicesParams(vendor_id="VEND-9401"), context
    )
    assert [i.vendor_invoice_number for i in result.invoices] == ["VINV-9401"]


@pytest.mark.asyncio
async def test_seeded_db_unknown_vendor_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Vendor not found"):
        await get_vendor_invoices_handler(
            GetVendorInvoicesParams(vendor_id="VEND-DOES-NOT-EXIST"), context
        )
