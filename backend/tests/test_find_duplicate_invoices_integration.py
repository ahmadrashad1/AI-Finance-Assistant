from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.find_duplicate_invoices import (
    FindDuplicateInvoicesParams,
    find_duplicate_invoices_handler,
)


@pytest.mark.asyncio
async def test_seeded_db_finds_a_real_duplicate_pair(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9701", company_name="Duplicate Integration Co", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-9701", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 1), status="sent",
        subtotal=Decimal("4400"), tax=Decimal("0"), total=Decimal("4400"),
    )
    await invoice_repo.create(
        invoice_number="INV-9702", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 2, 2), due_date=date(2026, 3, 1), status="sent",
        subtotal=Decimal("4400"), tax=Decimal("0"), total=Decimal("4400"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await find_duplicate_invoices_handler(FindDuplicateInvoicesParams(), context)

    assert result.summary.group_count == 1
    assert result.summary.invoice_count == 2
    numbers = {invoice.invoice_number for invoice in result.duplicate_groups[0]}
    assert numbers == {"INV-9701", "INV-9702"}


@pytest.mark.asyncio
async def test_seeded_db_reports_no_duplicates_honestly(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await find_duplicate_invoices_handler(FindDuplicateInvoicesParams(), context)

    assert result.duplicate_groups == []
    assert result.summary.group_count == 0
    assert result.summary.invoice_count == 0
