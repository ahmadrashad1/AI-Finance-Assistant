from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_overdue_invoices import (
    GetOverdueInvoicesParams,
    get_overdue_invoices_handler,
)

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
        issue_date=TODAY - timedelta(days=90),
        due_date=TODAY + timedelta(days=due_offset_days),
        status=status,
        subtotal=total,
        tax=Decimal("0"),
        total=total,
    )


@pytest.mark.asyncio
async def test_seeded_db_returns_only_overdue_sorted_by_urgency(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-9301", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-9301", customer_id=acme.id, status="overdue",
        total=Decimal("500.00"), due_offset_days=-5,
    )
    await _make_invoice(
        db_session, number="INV-9302", customer_id=acme.id, status="overdue",
        total=Decimal("100.00"), due_offset_days=-40,
    )
    await _make_invoice(
        db_session, number="INV-9303", customer_id=acme.id, status="sent",
        total=Decimal("900.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_overdue_invoices_handler(GetOverdueInvoicesParams(), context)

    assert [i.invoice_number for i in result.invoices] == ["INV-9302", "INV-9301"]
    assert result.summary.count == 2
    assert result.summary.total_outstanding == Decimal("600.00")


@pytest.mark.asyncio
async def test_seeded_db_minimum_days_filters_correctly(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-9401", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-9401", customer_id=acme.id, status="overdue",
        total=Decimal("500.00"), due_offset_days=-5,
    )
    await _make_invoice(
        db_session, number="INV-9402", customer_id=acme.id, status="overdue",
        total=Decimal("100.00"), due_offset_days=-40,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_overdue_invoices_handler(
        GetOverdueInvoicesParams(minimum_days=30), context
    )

    assert [i.invoice_number for i in result.invoices] == ["INV-9402"]


@pytest.mark.asyncio
async def test_seeded_db_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_overdue_invoices_handler(
            GetOverdueInvoicesParams(customer_id="CUST-DOES-NOT-EXIST"), context
        )
