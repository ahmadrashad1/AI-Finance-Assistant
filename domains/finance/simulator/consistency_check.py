from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import (
    BankAccountModel,
    CashTransactionModel,
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
from domains.finance.simulator.constants import SIMULATION_TODAY


async def run_consistency_check(db: AsyncSession) -> list[str]:
    violations: list[str] = []

    customer_ids = set((await db.execute(select(CustomerModel.id))).scalars().all())
    vendor_ids = set((await db.execute(select(VendorModel.id))).scalars().all())
    product_ids = set((await db.execute(select(ProductModel.id))).scalars().all())
    department_ids = set((await db.execute(select(DepartmentModel.id))).scalars().all())
    employee_ids = set((await db.execute(select(EmployeeModel.id))).scalars().all())
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
        if po.approved_by is not None and po.approved_by not in employee_ids:
            violations.append(
                f"Purchase order {po.po_number} references missing approver {po.approved_by}"
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

    expense_claims = (await db.execute(select(ExpenseClaimModel))).scalars().all()
    for claim in expense_claims:
        if claim.employee_id not in employee_ids:
            violations.append(
                f"Expense claim {claim.claim_number} references missing employee "
                f"{claim.employee_id}"
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

    all_vendor_invoices = (await db.execute(select(VendorInvoiceModel))).scalars().all()
    vendor_invoices_by_id = {vi.id: vi for vi in all_vendor_invoices}

    for vendor_invoice in all_vendor_invoices:
        if vendor_invoice.vendor_id not in vendor_ids:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} references missing "
                f"vendor {vendor_invoice.vendor_id}"
            )
        if (
            vendor_invoice.purchase_order_id is not None
            and vendor_invoice.purchase_order_id not in purchase_orders
        ):
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} references missing "
                f"purchase order {vendor_invoice.purchase_order_id}"
            )

    vendor_payments = (await db.execute(select(VendorPaymentModel))).scalars().all()
    vendor_payments_by_invoice: dict[uuid.UUID, Decimal] = {}
    for vendor_payment in vendor_payments:
        if vendor_payment.vendor_invoice_id not in vendor_invoices_by_id:
            violations.append(
                f"Vendor payment {vendor_payment.id} references missing vendor invoice "
                f"{vendor_payment.vendor_invoice_id}"
            )
            continue
        vendor_payments_by_invoice[vendor_payment.vendor_invoice_id] = (
            vendor_payments_by_invoice.get(vendor_payment.vendor_invoice_id, Decimal("0"))
            + vendor_payment.amount
        )

    for vendor_invoice in all_vendor_invoices:
        paid_total = vendor_payments_by_invoice.get(vendor_invoice.id, Decimal("0"))
        expected_balance = vendor_invoice.total - paid_total
        if vendor_invoice.balance != expected_balance:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} balance "
                f"{vendor_invoice.balance} != total {vendor_invoice.total} - payments "
                f"{paid_total} = {expected_balance}"
            )

        if vendor_invoice.status == "cancelled":
            continue
        is_past_due_unpaid = (
            vendor_invoice.due_date < SIMULATION_TODAY and vendor_invoice.balance > 0
        )
        if (
            vendor_invoice.status != "draft"
            and is_past_due_unpaid
            and vendor_invoice.status != "overdue"
        ):
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} is past due with "
                f"balance {vendor_invoice.balance} but status is "
                f"{vendor_invoice.status!r}, expected 'overdue'"
            )
        if vendor_invoice.status == "overdue" and not is_past_due_unpaid:
            violations.append(
                f"Vendor invoice {vendor_invoice.vendor_invoice_number} has status 'overdue' "
                "but its due date/balance don't justify it"
            )

    bank_account_ids = set(
        (await db.execute(select(BankAccountModel.id))).scalars().all()
    )
    payment_ids = {payment.id for payment in payments}
    vendor_payment_ids = {vp.id for vp in vendor_payments}
    cash_transactions = (await db.execute(select(CashTransactionModel))).scalars().all()
    transactions_by_payment_id = {
        ct.payment_id for ct in cash_transactions if ct.payment_id is not None
    }
    transactions_by_vendor_payment_id = {
        ct.vendor_payment_id for ct in cash_transactions if ct.vendor_payment_id is not None
    }

    for transaction in cash_transactions:
        if transaction.bank_account_id not in bank_account_ids:
            violations.append(
                f"Cash transaction {transaction.id} references missing bank account "
                f"{transaction.bank_account_id}"
            )
        if transaction.payment_id is not None and transaction.payment_id not in payment_ids:
            violations.append(
                f"Cash transaction {transaction.id} references missing payment "
                f"{transaction.payment_id}"
            )
        if (
            transaction.vendor_payment_id is not None
            and transaction.vendor_payment_id not in vendor_payment_ids
        ):
            violations.append(
                f"Cash transaction {transaction.id} references missing vendor payment "
                f"{transaction.vendor_payment_id}"
            )

    for payment in payments:
        if payment.id not in transactions_by_payment_id:
            violations.append(f"Payment {payment.id} has no corresponding cash transaction")

    for vendor_payment in vendor_payments:
        if vendor_payment.id not in transactions_by_vendor_payment_id:
            violations.append(
                f"Vendor payment {vendor_payment.id} has no corresponding cash transaction"
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
