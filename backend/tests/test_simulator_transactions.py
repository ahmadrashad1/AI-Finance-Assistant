from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    ExpenseClaimModel,
    InvoiceModel,
    PaymentModel,
    PurchaseOrderModel,
)
from domains.finance.simulator.constants import (
    NUM_DUPLICATE_INVOICES,
    NUM_INVOICES,
    NUM_PURCHASE_ORDERS,
)
from domains.finance.simulator.generator import SimulatorSeeder


@pytest.mark.asyncio
async def test_seed_produces_expected_scale(clean_db: None, db_session: AsyncSession) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    po_count = (
        await db_session.execute(select(func.count()).select_from(PurchaseOrderModel))
    ).scalar_one()
    invoice_count = (
        await db_session.execute(select(func.count()).select_from(InvoiceModel))
    ).scalar_one()
    payment_count = (
        await db_session.execute(select(func.count()).select_from(PaymentModel))
    ).scalar_one()
    expense_count = (
        await db_session.execute(select(func.count()).select_from(ExpenseClaimModel))
    ).scalar_one()

    assert po_count == NUM_PURCHASE_ORDERS
    assert invoice_count == NUM_INVOICES + NUM_DUPLICATE_INVOICES
    assert payment_count > 0
    assert expense_count > 0


@pytest.mark.asyncio
async def test_seed_invoices_all_reference_real_customers(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    invoices = (await db_session.execute(select(InvoiceModel))).scalars().all()
    for invoice in invoices:
        assert invoice.total == invoice.subtotal + invoice.tax
        assert invoice.balance == invoice.total - invoice.amount_paid


@pytest.mark.asyncio
async def test_seed_creates_duplicate_invoices_sharing_customer_and_po(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder = SimulatorSeeder(db_session, seed=42)
    await seeder.seed()
    await db_session.commit()

    duplicates = (
        await db_session.execute(
            select(InvoiceModel).where(InvoiceModel.invoice_number.like("INV-9%"))
        )
    ).scalars().all()
    assert len(duplicates) == NUM_DUPLICATE_INVOICES
    for duplicate in duplicates:
        assert duplicate.purchase_order_id is not None
