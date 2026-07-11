from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_customer_balance import (
    GetCustomerBalanceParams,
    get_customer_balance_handler,
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
        issue_date=TODAY - timedelta(days=60),
        due_date=TODAY + timedelta(days=due_offset_days),
        status=status,
        subtotal=total,
        tax=Decimal("0"),
        total=total,
    )


@pytest.mark.asyncio
async def test_seeded_db_returns_correct_balance_for_named_customer(
    clean_db: None, db_session: AsyncSession
) -> None:
    await _make_customer(db_session, "CUST-9501", "Northwind Manufacturing Ltd.")
    other = await _make_customer(db_session, "CUST-9502", "Globex Inc")
    acme = await _make_customer(db_session, "CUST-9503", "Acme Corp")
    await _make_invoice(
        db_session, number="INV-9501", customer_id=acme.id, status="overdue",
        total=Decimal("700.00"), due_offset_days=-10,
    )
    await _make_invoice(
        db_session, number="INV-9502", customer_id=other.id, status="sent",
        total=Decimal("999.00"), due_offset_days=15,
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_customer_balance_handler(
        GetCustomerBalanceParams(customer_name="Acme Corp"), context
    )

    assert result.customer_code == "CUST-9503"
    assert result.total_outstanding == Decimal("700.00")
    assert result.unpaid_invoice_count == 1


@pytest.mark.asyncio
async def test_seeded_db_unknown_customer_name_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Customer not found"):
        await get_customer_balance_handler(
            GetCustomerBalanceParams(customer_name="Does Not Exist Inc."), context
        )
