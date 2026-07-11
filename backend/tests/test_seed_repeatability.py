from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.finance.models import (
    CustomerModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
from domains.finance.simulator.generator import SimulatorSeeder

FINANCE_TABLES = (
    "finance.vendor_payments", "finance.vendor_invoices",
    "finance.payments", "finance.invoice_items", "finance.invoices",
    "finance.purchase_order_items", "finance.purchase_orders", "finance.expense_claims",
    "finance.employees", "finance.departments", "finance.products",
    "finance.customers", "finance.vendors",
)


async def _snapshot(db_session: AsyncSession) -> dict[str, object]:
    counts = {}
    for model in (
        CustomerModel, VendorModel, ProductModel, EmployeeModel,
        PurchaseOrderModel, InvoiceModel, PaymentModel, ExpenseClaimModel,
        VendorInvoiceModel, VendorPaymentModel,
    ):
        counts[model.__tablename__] = (
            await db_session.execute(select(func.count()).select_from(model))
        ).scalar_one()

    invoiced_by_customer: dict[str, Decimal] = {}
    rows = (
        await db_session.execute(
            select(CustomerModel.customer_code, InvoiceModel.total)
            .join(InvoiceModel, InvoiceModel.customer_id == CustomerModel.id)
        )
    ).all()
    for customer_code, total in rows:
        current = invoiced_by_customer.get(customer_code, Decimal("0"))
        invoiced_by_customer[customer_code] = current + total

    return {"counts": counts, "invoiced_by_customer": invoiced_by_customer}


@pytest.mark.asyncio
async def test_same_seed_produces_identical_data(
    clean_db: None, db_session: AsyncSession
) -> None:
    seeder_a = SimulatorSeeder(db_session, seed=42)
    await seeder_a.seed()
    await db_session.commit()
    snapshot_a = await _snapshot(db_session)

    await db_session.execute(text(f"TRUNCATE TABLE {', '.join(FINANCE_TABLES)} CASCADE"))
    await db_session.commit()

    seeder_b = SimulatorSeeder(db_session, seed=42)
    await seeder_b.seed()
    await db_session.commit()
    snapshot_b = await _snapshot(db_session)

    assert snapshot_a == snapshot_b
