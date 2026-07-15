from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.simulation import simulation_today
from domains.finance.tools.get_unpaid_invoices import (
    GetUnpaidInvoicesParams,
    get_unpaid_invoices_handler,
)

TODAY = simulation_today()


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
async def test_seeded_db_returns_only_unpaid_invoices_with_correct_totals(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8001", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-8002", "Globex Inc")

    await _make_invoice(
        db_session, number="INV-8001", customer_id=acme.id, status="overdue",
        total=Decimal("500.00"), due_offset_days=-10,
    )
    await _make_invoice(
        db_session, number="INV-8002", customer_id=acme.id, status="sent",
        total=Decimal("600.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8003", customer_id=globex.id, status="paid",
        total=Decimal("2000.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8004", customer_id=globex.id, status="draft",
        total=Decimal("300.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8005", customer_id=globex.id, status="cancelled",
        total=Decimal("300.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(GetUnpaidInvoicesParams(), context)

    numbers = {invoice.invoice_number for invoice in result.invoices}
    assert numbers == {"INV-8001", "INV-8002"}
    assert result.summary.count == 2
    assert result.summary.total_outstanding == Decimal("500.00") + Decimal("600.00")
    # Materiality sort: larger outstanding balance (INV-8002, 600) first.
    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8002", "INV-8001"]

    overdue_invoice = next(i for i in result.invoices if i.invoice_number == "INV-8001")
    assert overdue_invoice.days_outstanding == 10
    not_yet_due_invoice = next(i for i in result.invoices if i.invoice_number == "INV-8002")
    assert not_yet_due_invoice.days_outstanding == 0
    assert overdue_invoice.customer_name == "Acme Corp"


@pytest.mark.asyncio
async def test_customer_id_filters_to_one_customer(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8101", "Acme Corp")
    globex = await _make_customer(db_session, "CUST-8102", "Globex Inc")
    await _make_invoice(
        db_session, number="INV-8101", customer_id=acme.id, status="sent",
        total=Decimal("100.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8102", customer_id=globex.id, status="sent",
        total=Decimal("200.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(
        GetUnpaidInvoicesParams(customer_id="CUST-8101"), context
    )

    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8101"]


@pytest.mark.asyncio
async def test_minimum_amount_filters_out_small_balances(
    clean_db: None, db_session: AsyncSession
) -> None:
    acme = await _make_customer(db_session, "CUST-8201", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-8201", customer_id=acme.id, status="sent",
        total=Decimal("50.00"), due_offset_days=15,
    )
    await _make_invoice(
        db_session, number="INV-8202", customer_id=acme.id, status="sent",
        total=Decimal("5000.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(
        GetUnpaidInvoicesParams(minimum_amount=Decimal("1000.00")), context
    )

    assert [invoice.invoice_number for invoice in result.invoices] == ["INV-8202"]


@pytest.mark.asyncio
async def test_unknown_customer_id_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_unpaid_invoices_handler(
            GetUnpaidInvoicesParams(customer_id="CUST-DOES-NOT-EXIST"), context
        )
