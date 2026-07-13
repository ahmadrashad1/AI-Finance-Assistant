from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_aging_report import GetAgingReportParams, get_aging_report_handler


@pytest.mark.asyncio
async def test_seeded_db_produces_a_five_bucket_report(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9601", company_name="Aging Report Co", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-9601", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2025, 1, 1), due_date=date(2025, 2, 1), status="overdue",
        subtotal=Decimal("5000"), tax=Decimal("0"), total=Decimal("5000"),
    )
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await get_aging_report_handler(GetAgingReportParams(), context)

    assert [b.label for b in result.buckets] == ["current", "0-30", "31-60", "61-90", "90+"]
    assert result.grand_total >= Decimal("5000")
    ninety_plus = next(b for b in result.buckets if b.label == "90+")
    assert ninety_plus.invoice_count >= 1
