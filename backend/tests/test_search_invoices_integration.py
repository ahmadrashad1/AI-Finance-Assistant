from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.search_invoices import SearchInvoicesParams, search_invoices_handler

TODAY = date.today()


async def _make_customer(db_session: AsyncSession, code: str, name: str) -> object:
    repo = CustomerRepository(db_session)
    return await repo.create(
        customer_code=code, company_name=name, industry="Retail", contact_name="A",
        contact_email=f"{code.lower()}@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )


async def _make_invoice(
    db_session: AsyncSession,
    *,
    number: str,
    customer_id: object,
    status: str,
    total: Decimal,
    due_offset_days: int,
) -> None:
    repo = InvoiceRepository(db_session)
    await repo.create(
        invoice_number=number,
        customer_id=customer_id,
        purchase_order_id=None,
        issue_date=TODAY - timedelta(days=60),
        due_date=TODAY + timedelta(days=due_offset_days),
        status=status,
        subtotal=total,
        tax=Decimal("0"),
        total=total,
    )


@pytest.mark.asyncio
async def test_seeded_db_search_by_invoice_number(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-9101", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-9101", customer_id=acme.id, status="sent",
        total=Decimal("500.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-9102", customer_id=acme.id, status="sent",
        total=Decimal("600.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await search_invoices_handler(
        SearchInvoicesParams(invoice_number="INV-9101"), context
    )

    assert [i.invoice_number for i in result.invoices] == ["INV-9101"]
    assert result.summary.count == 1
    assert result.summary.total_amount == Decimal("500.00")


@pytest.mark.asyncio
async def test_seeded_db_search_by_status_and_amount_range(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-9201", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-9201", customer_id=acme.id, status="paid",
        total=Decimal("5000.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-9202", customer_id=acme.id, status="sent",
        total=Decimal("5000.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-9203", customer_id=acme.id, status="paid",
        total=Decimal("50.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await search_invoices_handler(
        SearchInvoicesParams(status="paid", minimum_amount=Decimal("1000.00")), context
    )

    assert [i.invoice_number for i in result.invoices] == ["INV-9201"]


@pytest.mark.asyncio
async def test_seeded_db_search_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await search_invoices_handler(
            SearchInvoicesParams(customer_id="CUST-DOES-NOT-EXIST"), context
        )
