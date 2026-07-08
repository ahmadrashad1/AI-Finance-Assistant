from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import (
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorModel,
)
from domains.finance.simulator.constants import SIMULATION_TODAY


async def run_consistency_check(db: AsyncSession) -> list[str]:
    violations: list[str] = []

    customer_ids = set((await db.execute(select(CustomerModel.id))).scalars().all())
    vendor_ids = set((await db.execute(select(VendorModel.id))).scalars().all())
    product_ids = set((await db.execute(select(ProductModel.id))).scalars().all())
    department_ids = set((await db.execute(select(DepartmentModel.id))).scalars().all())
    all_purchase_orders = (await db.execute(select(PurchaseOrderModel))).scalars().all()
    purchase_orders = {po.id: po for po in all_purchase_orders}
    invoices = list((await db.execute(select(InvoiceModel))).scalars().all())
    invoice_ids = {invoice.id for invoice in invoices}

    for invoice in invoices:
        if invoice.customer_id not in customer_ids:
            violations.append(
                f"Invoice {invoice.invoice_number} references missing customer "
                f"{invoice.customer_id}"
            )
        if (
            invoice.purchase_order_id is not None
            and invoice.purchase_order_id not in purchase_orders
        ):
            violations.append(
                f"Invoice {invoice.invoice_number} references missing purchase order "
                f"{invoice.purchase_order_id}"
            )

    for po in purchase_orders.values():
        if po.vendor_id not in vendor_ids:
            violations.append(
                f"Purchase order {po.po_number} references missing vendor {po.vendor_id}"
            )

    invoice_items = (await db.execute(select(InvoiceItemModel))).scalars().all()
    for item in invoice_items:
        if item.invoice_id not in invoice_ids:
            violations.append(
                f"Invoice item {item.id} references missing invoice {item.invoice_id}"
            )
        if item.product_id not in product_ids:
            violations.append(
                f"Invoice item {item.id} references missing product {item.product_id}"
            )

    po_items = (await db.execute(select(PurchaseOrderItemModel))).scalars().all()
    for po_item in po_items:
        if po_item.purchase_order_id not in purchase_orders:
            violations.append(
                f"Purchase order item {po_item.id} references missing purchase order "
                f"{po_item.purchase_order_id}"
            )
        if po_item.product_id not in product_ids:
            violations.append(
                f"Purchase order item {po_item.id} references missing product {po_item.product_id}"
            )

    employees = (await db.execute(select(EmployeeModel))).scalars().all()
    for employee in employees:
        if employee.department_id not in department_ids:
            violations.append(
                f"Employee {employee.employee_code} references missing department "
                f"{employee.department_id}"
            )

    payments = (await db.execute(select(PaymentModel))).scalars().all()
    payments_by_invoice: dict[uuid.UUID, Decimal] = {}
    for payment in payments:
        if payment.invoice_id not in invoice_ids:
            violations.append(
                f"Payment {payment.id} references missing invoice {payment.invoice_id}"
            )
            continue
        payments_by_invoice[payment.invoice_id] = (
            payments_by_invoice.get(payment.invoice_id, Decimal("0")) + payment.amount
        )

    for invoice in invoices:
        paid_total = payments_by_invoice.get(invoice.id, Decimal("0"))
        expected_balance = invoice.total - paid_total
        if invoice.balance != expected_balance:
            violations.append(
                f"Invoice {invoice.invoice_number} balance {invoice.balance} != total "
                f"{invoice.total} - payments {paid_total} = {expected_balance}"
            )

        if invoice.status == "cancelled":
            continue
        is_past_due_unpaid = invoice.due_date < SIMULATION_TODAY and invoice.balance > 0
        if invoice.status != "draft" and is_past_due_unpaid and invoice.status != "overdue":
            violations.append(
                f"Invoice {invoice.invoice_number} is past due with balance {invoice.balance} "
                f"but status is {invoice.status!r}, expected 'overdue'"
            )
        if invoice.status == "overdue" and not is_past_due_unpaid:
            violations.append(
                f"Invoice {invoice.invoice_number} has status 'overdue' but its due date/balance "
                "don't justify it"
            )

    return violations


async def _main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        violations = await run_consistency_check(session)
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        print(f"\n{len(violations)} consistency violation(s) found.", file=sys.stderr)
        sys.exit(1)
    print("Consistency check passed: 0 violations.")


if __name__ == "__main__":
    asyncio.run(_main())
