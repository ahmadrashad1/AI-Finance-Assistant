from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import (
    ApprovalThresholdPolicyModel,
    BankAccountModel,
    BankTransactionModel,
    BudgetModel,
    CashTransactionModel,
    ClosePeriodModel,
    CloseTaskModel,
    CustomerModel,
    DepartmentModel,
    EmployeeModel,
    ExpenseClaimModel,
    ExpenseLimitPolicyModel,
    ExpenseSubmissionPolicyModel,
    FixedAssetModel,
    InvoiceItemModel,
    InvoiceModel,
    PaymentModel,
    PayrollLineModel,
    PayrollRunModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    PurchaseRequisitionModel,
    RequisitionItemModel,
    TaxPeriodModel,
    TaxRateModel,
    VendorInvoiceModel,
    VendorModel,
    VendorPaymentModel,
)
from domains.finance.simulation import full_months_between
from domains.finance.simulator.constants import (
    PAYROLL_MONTHS,
    SALES_TAX_RATE,
    SIMULATION_TODAY,
)
from domains.finance.simulator.expectations import (
    DEFAULT_EXPECTATIONS_PATH,
    load_expectations,
)


async def run_consistency_check(
    db: AsyncSession, expectations: dict[str, Any] | None = None
) -> list[str]:
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
        if (
            po.approved_by_employee_id is not None
            and po.approved_by_employee_id not in employee_ids
        ):
            violations.append(
                f"Purchase order {po.po_number} references missing approver "
                f"{po.approved_by_employee_id}"
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

    await _check_v2(db, violations, expectations)
    return violations


_KNOWN_BANK_LINE_TYPES = ("bank_fee", "interest", "transfer", "tax_payment")


async def _check_v2(  # noqa: PLR0915
    db: AsyncSession, violations: list[str], expectations: dict[str, Any] | None
) -> None:
    """Simulator v2 invariants (PRD Ch.19). Planted anomalies must equal the
    expectations file exactly -- an anomaly that drifted from its recorded
    truth is itself a violation."""
    if expectations is None:
        try:
            expectations = load_expectations()
        except FileNotFoundError:
            violations.append(
                f"Expectations file missing at {DEFAULT_EXPECTATIONS_PATH}; reseed first"
            )
            expectations = {}

    employees = (await db.execute(select(EmployeeModel))).scalars().all()
    employees_by_id = {e.id: e for e in employees}
    employee_ids = set(employees_by_id)
    departments = (await db.execute(select(DepartmentModel))).scalars().all()
    department_ids = {d.id for d in departments}
    department_names = {d.id: d.name for d in departments}

    # -- employees ---------------------------------------------------------
    for employee in employees:
        if employee.grade is None or employee.salary is None or employee.hire_date is None:
            violations.append(
                f"Employee {employee.employee_code} is missing grade/salary/hire_date"
            )
        if employee.manager_id is not None and employee.manager_id not in employee_ids:
            violations.append(
                f"Employee {employee.employee_code} references missing manager"
            )
        if (employee.termination_date is not None) != (employee.status == "inactive"):
            violations.append(
                f"Employee {employee.employee_code} termination/status disagree"
            )

    # -- expense claims vs policy data --------------------------------------
    limits = {
        (p.category, p.grade): p.per_claim_limit
        for p in (await db.execute(select(ExpenseLimitPolicyModel))).scalars().all()
    }
    submission_policy = (
        await db.execute(select(ExpenseSubmissionPolicyModel))
    ).scalars().first()
    claims = (
        await db.execute(select(ExpenseClaimModel).order_by(ExpenseClaimModel.claim_number))
    ).scalars().all()
    self_approved_expected = set(
        expectations.get("self_approved_expense_claims", {}).get("claim_numbers", [])
    )
    over_limit: list[str] = []
    missing_receipt: list[str] = []
    late_submission: list[str] = []
    self_approved: list[str] = []
    for claim in claims:
        if claim.department_id is None or claim.department_id not in department_ids:
            violations.append(f"Expense claim {claim.claim_number} has no valid department")
            continue
        if claim.expense_date is None:
            violations.append(f"Expense claim {claim.claim_number} has no expense date")
            continue
        if claim.expense_date > claim.submitted_date:
            violations.append(
                f"Expense claim {claim.claim_number} submitted before the expense date"
            )
        claimant = employees_by_id.get(claim.employee_id)
        if claimant is None:
            continue  # already reported by the v1 checks
        if claim.status in ("approved", "reimbursed"):
            if claim.approver_id is None:
                violations.append(
                    f"Expense claim {claim.claim_number} is {claim.status} without an approver"
                )
            elif claim.approver_id == claim.employee_id:
                self_approved.append(claim.claim_number)

        recomputed: list[str] = []
        limit = limits.get((claim.category, claimant.grade or ""))
        if limit is not None and claim.amount > limit:
            recomputed.append("over_limit")
            over_limit.append(claim.claim_number)
        if (
            submission_policy is not None
            and claim.amount > submission_policy.receipt_required_above
            and not claim.receipt_attached
        ):
            recomputed.append("missing_receipt")
            missing_receipt.append(claim.claim_number)
        if submission_policy is not None and (
            claim.submitted_date - claim.expense_date
        ) > timedelta(days=submission_policy.submission_deadline_days):
            recomputed.append("late_submission")
            late_submission.append(claim.claim_number)
        if sorted(claim.policy_violations) != sorted(recomputed):
            violations.append(
                f"Expense claim {claim.claim_number} stores policy_violations "
                f"{claim.policy_violations} but recomputation gives {recomputed}"
            )

    if set(self_approved) != self_approved_expected:
        violations.append(
            f"Self-approved claims {sorted(self_approved)} != expectations "
            f"{sorted(self_approved_expected)}"
        )
    for label, computed in (
        ("over_limit_expense_claims", over_limit),
        ("missing_receipt_expense_claims", missing_receipt),
        ("late_submission_expense_claims", late_submission),
    ):
        expected = expectations.get(label, {}).get("claim_numbers", [])
        if sorted(computed) != sorted(expected):
            violations.append(
                f"{label}: recomputed {len(computed)} claims != expectations "
                f"{len(expected)}"
            )

    # -- bank transactions ---------------------------------------------------
    bank_lines = (
        await db.execute(select(BankTransactionModel))
    ).scalars().all()
    payments_all = (await db.execute(select(PaymentModel))).scalars().all()
    payment_ids = {p.id for p in payments_all}
    vendor_payments_all = (await db.execute(select(VendorPaymentModel))).scalars().all()
    vendor_payment_ids = {p.id for p in vendor_payments_all}
    payroll_runs = (
        await db.execute(select(PayrollRunModel).order_by(PayrollRunModel.period))
    ).scalars().all()
    payroll_run_ids = {r.id for r in payroll_runs}
    claim_ids = {c.id for c in claims}
    unmatched_refs: list[str] = []
    for line in bank_lines:
        matches = [
            line.matched_payment_id,
            line.matched_vendor_payment_id,
            line.matched_payroll_run_id,
            line.matched_expense_claim_id,
        ]
        match_count = sum(1 for m in matches if m is not None)
        if match_count > 1:
            violations.append(f"Bank transaction {line.id} matches multiple internal records")
        if line.match_status == "matched" and match_count != 1:
            violations.append(
                f"Bank transaction {line.id} is 'matched' but has {match_count} match links"
            )
        if line.match_status != "matched" and match_count > 0:
            violations.append(
                f"Bank transaction {line.id} is '{line.match_status}' but carries a match link"
            )
        if line.match_status == "internal" and line.transaction_type not in _KNOWN_BANK_LINE_TYPES:
            violations.append(
                f"Bank transaction {line.id} is 'internal' but typed {line.transaction_type!r}"
            )
        if line.match_status == "unmatched":
            if line.transaction_type != "unknown":
                violations.append(
                    f"Bank transaction {line.id} is 'unmatched' but typed "
                    f"{line.transaction_type!r}"
                )
            unmatched_refs.append(line.reference or str(line.id))
        if line.matched_payment_id is not None and line.matched_payment_id not in payment_ids:
            violations.append(f"Bank transaction {line.id} references missing payment")
        if (
            line.matched_vendor_payment_id is not None
            and line.matched_vendor_payment_id not in vendor_payment_ids
        ):
            violations.append(f"Bank transaction {line.id} references missing vendor payment")
        if (
            line.matched_payroll_run_id is not None
            and line.matched_payroll_run_id not in payroll_run_ids
        ):
            violations.append(f"Bank transaction {line.id} references missing payroll run")
        if (
            line.matched_expense_claim_id is not None
            and line.matched_expense_claim_id not in claim_ids
        ):
            violations.append(f"Bank transaction {line.id} references missing expense claim")

    expected_unmatched = expectations.get("unmatched_bank_transactions", {})
    if sorted(unmatched_refs) != sorted(expected_unmatched.get("references", [])):
        violations.append(
            f"Unmatched bank transactions {sorted(unmatched_refs)} != expectations "
            f"{sorted(expected_unmatched.get('references', []))}"
        )
    if bank_lines and expected_unmatched:
        proportion = round(len(unmatched_refs) / len(bank_lines), 4)
        if proportion != expected_unmatched.get("proportion"):
            violations.append(
                f"Unmatched proportion {proportion} != expectations "
                f"{expected_unmatched.get('proportion')}"
            )

    # Reconciliation work in the other direction: internal payments that the
    # bank statement never saw must be exactly the deliberate set.
    invoices_by_id = {
        inv.id: inv for inv in (await db.execute(select(InvoiceModel))).scalars().all()
    }
    vendor_invoices_by_id = {
        vi.id: vi
        for vi in (await db.execute(select(VendorInvoiceModel))).scalars().all()
    }
    mirrored_payment_ids = {
        line.matched_payment_id for line in bank_lines if line.matched_payment_id is not None
    }
    mirrored_vendor_payment_ids = {
        line.matched_vendor_payment_id
        for line in bank_lines
        if line.matched_vendor_payment_id is not None
    }
    unmirrored_invoice_numbers = sorted(
        invoices_by_id[p.invoice_id].invoice_number
        for p in payments_all
        if p.id not in mirrored_payment_ids and p.invoice_id in invoices_by_id
    )
    unmirrored_vendor_numbers = sorted(
        vendor_invoices_by_id[p.vendor_invoice_id].vendor_invoice_number
        for p in vendor_payments_all
        if p.id not in mirrored_vendor_payment_ids
        and p.vendor_invoice_id in vendor_invoices_by_id
    )
    expected_unmirrored = expectations.get("unmirrored_internal_payments", {})
    if unmirrored_invoice_numbers != sorted(expected_unmirrored.get("invoice_numbers", [])):
        violations.append(
            f"Payments without bank lines {unmirrored_invoice_numbers} != expectations "
            f"{sorted(expected_unmirrored.get('invoice_numbers', []))}"
        )
    if unmirrored_vendor_numbers != sorted(
        expected_unmirrored.get("vendor_invoice_numbers", [])
    ):
        violations.append(
            f"Vendor payments without bank lines {unmirrored_vendor_numbers} != "
            f"expectations {sorted(expected_unmirrored.get('vendor_invoice_numbers', []))}"
        )

    # -- payroll --------------------------------------------------------------
    if len(payroll_runs) != PAYROLL_MONTHS:
        violations.append(f"Expected {PAYROLL_MONTHS} payroll runs, found {len(payroll_runs)}")
    lines_by_run: dict[uuid.UUID, list[PayrollLineModel]] = {}
    for line_row in (await db.execute(select(PayrollLineModel))).scalars().all():
        lines_by_run.setdefault(line_row.payroll_run_id, []).append(line_row)
    bank_lines_by_id = {line.id: line for line in bank_lines}
    for i, run in enumerate(payroll_runs):
        if i > 0:
            previous = payroll_runs[i - 1].period
            expected_period = (
                previous.replace(year=previous.year + 1, month=1)
                if previous.month == 12
                else previous.replace(month=previous.month + 1)
            )
            if run.period != expected_period:
                violations.append(f"Payroll periods not contiguous at {run.period}")
        run_lines = lines_by_run.get(run.id, [])
        if not run_lines:
            violations.append(f"Payroll run {run.period} has no lines")
            continue
        gross = sum((line.base_salary + line.overtime + line.bonus for line in run_lines),
                    start=Decimal("0"))
        deductions = sum(
            (line.tax_withheld + line.other_deductions for line in run_lines),
            start=Decimal("0"),
        )
        net = sum((line.net_pay for line in run_lines), start=Decimal("0"))
        if (run.total_gross, run.total_deductions, run.total_net) != (gross, deductions, net):
            violations.append(f"Payroll run {run.period} totals disagree with its lines")
        period_end = run.period.replace(
            day=28
        ) + timedelta(days=4)  # safely into next month
        period_end = period_end.replace(day=1) - timedelta(days=1)
        active_ids = {
            e.id for e in employees
            if e.hire_date is not None and e.hire_date <= period_end
            and (e.termination_date is None or e.termination_date >= run.period)
        }
        line_employee_ids = {line.employee_id for line in run_lines}
        if line_employee_ids != active_ids:
            violations.append(
                f"Payroll run {run.period} covers {len(line_employee_ids)} employees, "
                f"expected {len(active_ids)} active"
            )
        if run.status == "completed":
            bank_line = (
                bank_lines_by_id.get(run.bank_transaction_id)
                if run.bank_transaction_id
                else None
            )
            if bank_line is None or bank_line.amount != -run.total_net:
                violations.append(
                    f"Payroll run {run.period} has no bank transaction of -{run.total_net}"
                )

    # -- budgets ---------------------------------------------------------------
    budgets = (await db.execute(select(BudgetModel))).scalars().all()
    purchase_orders_all = (
        await db.execute(select(PurchaseOrderModel))
    ).scalars().all()
    budget_by_dept: dict[uuid.UUID, Decimal] = {}
    budget_by_dept_category: dict[tuple[uuid.UUID, str], Decimal] = {}
    for budget in budgets:
        if budget.department_id not in department_ids:
            violations.append(f"Budget line {budget.id} references missing department")
            continue
        budget_by_dept[budget.department_id] = (
            budget_by_dept.get(budget.department_id, Decimal("0")) + budget.budgeted_amount
        )
        key = (budget.department_id, budget.category)
        budget_by_dept_category[key] = (
            budget_by_dept_category.get(key, Decimal("0")) + budget.budgeted_amount
        )

    actual_by_dept: dict[uuid.UUID, Decimal] = {}
    actual_by_dept_category: dict[tuple[uuid.UUID, str], Decimal] = {}

    def add_actual(department_id: uuid.UUID, category: str, amount: Decimal) -> None:
        actual_by_dept[department_id] = actual_by_dept.get(department_id, Decimal("0")) + amount
        key = (department_id, category)
        actual_by_dept_category[key] = (
            actual_by_dept_category.get(key, Decimal("0")) + amount
        )

    for claim in claims:
        if claim.status != "rejected" and claim.department_id is not None:
            add_actual(claim.department_id, claim.category, claim.amount)
    for run in payroll_runs:
        for line_row in lines_by_run.get(run.id, []):
            employee = employees_by_id.get(line_row.employee_id)
            if employee is not None:
                add_actual(
                    employee.department_id, "payroll",
                    line_row.base_salary + line_row.overtime + line_row.bonus,
                )
    for po in purchase_orders_all:
        if po.status in ("approved", "received") and po.created_by_employee_id is not None:
            employee = employees_by_id.get(po.created_by_employee_id)
            if employee is not None:
                add_actual(employee.department_id, "procurement", po.total_amount)

    over_departments = sorted(
        department_names[dept_id]
        for dept_id, actual in actual_by_dept.items()
        if actual > budget_by_dept.get(dept_id, Decimal("0"))
    )
    expected_over = expectations.get("over_budget_departments", {}).get(
        "department_names", []
    )
    if not set(expected_over) <= set(over_departments):
        violations.append(
            f"Expected over-budget departments {expected_over}, computed {over_departments}"
        )
    if len(over_departments) < 2:
        violations.append(
            f"Fewer than two departments over budget: {over_departments}"
        )
    under_expected = expectations.get("under_budget_department", {}).get("department_name")
    if under_expected:
        dept_id = next(
            (d for d, name in department_names.items() if name == under_expected), None
        )
        if dept_id is None:
            violations.append(f"Under-budget department {under_expected} does not exist")
        else:
            actual = actual_by_dept.get(dept_id, Decimal("0"))
            budget = budget_by_dept.get(dept_id, Decimal("0"))
            if budget == 0 or actual / budget > Decimal("0.7"):
                violations.append(
                    f"Department {under_expected} is not materially under budget "
                    f"(actual {actual}, budget {budget})"
                )
    overspend = expectations.get("category_overspend", {})
    if overspend:
        dept_id = next(
            (
                d for d, name in department_names.items()
                if name == overspend.get("department_name")
            ),
            None,
        )
        category = overspend.get("category")
        if dept_id is not None and category:
            actual = actual_by_dept_category.get((dept_id, category), Decimal("0"))
            budget = budget_by_dept_category.get((dept_id, category), Decimal("0"))
            if actual <= budget:
                violations.append(
                    f"Planted category overspend {overspend} not present "
                    f"(actual {actual}, budget {budget})"
                )

    # -- fixed assets ------------------------------------------------------------
    vendor_ids_all = {
        v.id for v in (await db.execute(select(VendorModel))).scalars().all()
    }
    assets = (await db.execute(select(FixedAssetModel))).scalars().all()
    fully_depreciated_in_use = []
    for asset in assets:
        if asset.purchase_date > SIMULATION_TODAY:
            violations.append(f"Asset {asset.asset_tag} purchased after the simulation date")
        if asset.useful_life_months <= 0:
            violations.append(f"Asset {asset.asset_tag} has non-positive useful life")
        if asset.salvage_value >= asset.purchase_cost:
            violations.append(f"Asset {asset.asset_tag} salvage >= cost")
        if asset.department_id not in department_ids:
            violations.append(f"Asset {asset.asset_tag} references missing department")
        if asset.vendor_id is not None and asset.vendor_id not in vendor_ids_all:
            violations.append(f"Asset {asset.asset_tag} references missing vendor")
        if (asset.status == "disposed") != (asset.disposal_date is not None):
            violations.append(f"Asset {asset.asset_tag} disposal fields disagree with status")
        if (
            asset.status == "in_use"
            and full_months_between(asset.purchase_date, SIMULATION_TODAY)
            >= asset.useful_life_months
        ):
            fully_depreciated_in_use.append(asset.asset_tag)
    expected_assets = expectations.get("fully_depreciated_assets_in_use", {}).get(
        "asset_tags", []
    )
    if sorted(fully_depreciated_in_use) != sorted(expected_assets):
        violations.append(
            f"Fully depreciated in-use assets {sorted(fully_depreciated_in_use)} != "
            f"expectations {sorted(expected_assets)}"
        )

    # -- requisitions and purchase orders ---------------------------------------
    requisitions = (
        await db.execute(select(PurchaseRequisitionModel))
    ).scalars().all()
    requisitions_by_id = {r.id: r for r in requisitions}
    product_ids_all = {
        p.id for p in (await db.execute(select(ProductModel))).scalars().all()
    }
    for requisition in requisitions:
        if requisition.requester_employee_id not in employee_ids:
            violations.append(
                f"Requisition {requisition.requisition_number} references missing requester"
            )
        if requisition.department_id not in department_ids:
            violations.append(
                f"Requisition {requisition.requisition_number} references missing department"
            )
        if (
            requisition.approver_id is not None
            and requisition.approver_id == requisition.requester_employee_id
        ):
            violations.append(
                f"Requisition {requisition.requisition_number} approved by its requester"
            )
        if requisition.status in ("approved", "converted"):
            if requisition.approver_id is None or requisition.approved_date is None:
                violations.append(
                    f"Requisition {requisition.requisition_number} is {requisition.status} "
                    "without approver/approved_date"
                )
            elif requisition.approved_date < requisition.requested_date:
                violations.append(
                    f"Requisition {requisition.requisition_number} approved before requested"
                )
    requisition_items = (
        await db.execute(select(RequisitionItemModel))
    ).scalars().all()
    for item in requisition_items:
        if item.requisition_id not in requisitions_by_id:
            violations.append(f"Requisition item {item.id} references missing requisition")
        if item.product_id not in product_ids_all:
            violations.append(f"Requisition item {item.id} references missing product")

    maverick_expected = set(
        expectations.get("maverick_purchase_orders", {}).get("po_numbers", [])
    )
    maverick_found = set()
    for po in purchase_orders_all:
        if po.status in ("draft", "cancelled"):
            continue
        if po.requisition_id is None:
            maverick_found.add(po.po_number)
        else:
            requisition = requisitions_by_id.get(po.requisition_id)
            if requisition is None:
                violations.append(f"PO {po.po_number} references missing requisition")
            elif requisition.status not in ("approved", "converted"):
                violations.append(
                    f"PO {po.po_number} traces to a requisition in status "
                    f"{requisition.status!r}"
                )
    if maverick_found != maverick_expected:
        violations.append(
            f"Maverick POs {sorted(maverick_found)} != expectations "
            f"{sorted(maverick_expected)}"
        )

    po_by_number = {po.po_number: po for po in purchase_orders_all}
    po_items = (await db.execute(select(PurchaseOrderItemModel))).scalars().all()
    items_by_po_id: dict[uuid.UUID, list[PurchaseOrderItemModel]] = {}
    for item in po_items:
        items_by_po_id.setdefault(item.purchase_order_id, []).append(item)
    for entry in expectations.get("price_variance_products", []):
        prices = []
        for purchase in entry.get("purchases", []):
            po = po_by_number.get(purchase["po_number"])
            if po is None:
                violations.append(
                    f"Price-variance PO {purchase['po_number']} does not exist"
                )
                continue
            for item in items_by_po_id.get(po.id, []):
                prices.append(item.unit_price)
        if len(prices) >= 2:
            low, high = min(prices), max(prices)
            if low == 0 or high / low < Decimal("1.25"):
                violations.append(
                    f"Price variance for {entry.get('sku')} below 25%: {low} vs {high}"
                )

    # -- transaction metadata (segregation of duties) -----------------------------
    for invoice in invoices_by_id.values():
        if invoice.created_by_employee_id is None:
            violations.append(f"Invoice {invoice.invoice_number} has no creator recorded")
        elif invoice.created_by_employee_id not in employee_ids:
            violations.append(f"Invoice {invoice.invoice_number} creator does not exist")
    for payment in payments_all:
        if payment.created_by_employee_id is None:
            violations.append(f"Payment {payment.id} has no creator recorded")
    threshold_policy = (
        await db.execute(
            select(ApprovalThresholdPolicyModel).where(
                ApprovalThresholdPolicyModel.subject == "payment"
            )
        )
    ).scalars().first()
    unapproved_expected = expectations.get("unapproved_payment_above_threshold", {})
    if threshold_policy is not None:
        unapproved_found = sorted(
            vendor_invoices_by_id[p.vendor_invoice_id].vendor_invoice_number
            for p in vendor_payments_all
            if p.amount > threshold_policy.threshold_amount
            and p.approved_by_employee_id is None
            and p.vendor_invoice_id in vendor_invoices_by_id
        )
        expected_number = unapproved_expected.get("vendor_invoice_number")
        expected_list = [expected_number] if expected_number else []
        if unapproved_found != expected_list:
            violations.append(
                f"Unapproved payments above threshold {unapproved_found} != "
                f"expectations {expected_list}"
            )

    # -- deteriorating customer ---------------------------------------------------
    deteriorating = expectations.get("deteriorating_customer", {})
    if deteriorating:
        code = deteriorating.get("customer_code")
        customer = (
            await db.execute(
                select(CustomerModel).where(CustomerModel.customer_code == code)
            )
        ).scalars().first()
        if customer is None:
            violations.append(f"Deteriorating customer {code} does not exist")
        else:
            customer_invoices = sorted(
                (
                    inv for inv in invoices_by_id.values()
                    if inv.customer_id == customer.id
                ),
                key=lambda inv: inv.due_date,
            )
            payments_by_invoice_id = {
                p.invoice_id: p for p in payments_all
            }
            lateness: list[int] = []
            unpaid: list[str] = []
            for inv in customer_invoices:
                payment = payments_by_invoice_id.get(inv.id)
                if payment is None:
                    unpaid.append(inv.invoice_number)
                else:
                    lateness.append((payment.payment_date - inv.due_date).days)
            if sorted(unpaid) != sorted(deteriorating.get("unpaid_invoice_numbers", [])):
                violations.append(
                    f"Deteriorating customer unpaid invoices {unpaid} != expectations"
                )
            if len(lateness) >= 6:
                early = sum(lateness[:3]) / 3
                late = sum(lateness[-3:]) / 3
                if late < early + 15:
                    violations.append(
                        f"Deteriorating customer lateness trend too weak: {lateness}"
                    )
            else:
                violations.append(
                    f"Deteriorating customer has too few payments for a trend: {lateness}"
                )

    # -- financial close ------------------------------------------------------------
    close_periods = (
        await db.execute(select(ClosePeriodModel).order_by(ClosePeriodModel.period))
    ).scalars().all()
    if len(close_periods) != PAYROLL_MONTHS:
        violations.append(
            f"Expected {PAYROLL_MONTHS} close periods, found {len(close_periods)}"
        )
    close_tasks = (await db.execute(select(CloseTaskModel))).scalars().all()
    tasks_by_period: dict[uuid.UUID, list[CloseTaskModel]] = {}
    for task in close_tasks:
        tasks_by_period.setdefault(task.close_period_id, []).append(task)
        if task.owner_employee_id not in employee_ids:
            violations.append(f"Close task {task.task_name} has a missing owner")
        if task.status == "blocked" and not task.blocking_reason:
            violations.append(f"Close task {task.task_name} blocked without a reason")
    for i, period in enumerate(close_periods):
        is_last = i == len(close_periods) - 1
        if is_last and period.status != "open":
            violations.append(f"Most recent close period {period.period} is not open")
        if not is_last and period.status != "closed":
            violations.append(f"Historic close period {period.period} is not closed")
        period_tasks = tasks_by_period.get(period.id, [])
        if not period_tasks:
            violations.append(f"Close period {period.period} has no tasks")
            continue
        if period.status == "closed":
            for task in period_tasks:
                if task.status != "completed":
                    violations.append(
                        f"Closed period {period.period} has task {task.task_name!r} "
                        f"in status {task.status!r}"
                    )
                elif (
                    period.closed_date is not None
                    and task.completed_date is not None
                    and task.completed_date > period.closed_date
                ):
                    violations.append(
                        f"Closed period {period.period} task {task.task_name!r} "
                        "completed after the close"
                    )
        else:
            statuses = {task.status for task in period_tasks}
            if not {"completed", "in_progress", "blocked"} <= statuses:
                violations.append(
                    f"Open close period {period.period} lacks a completed/in-progress/"
                    f"blocked mix: {sorted(statuses)}"
                )

    # -- tax --------------------------------------------------------------------------
    sales_rates = [
        r for r in (await db.execute(select(TaxRateModel))).scalars().all()
        if r.category == "sales"
    ]
    if not any(r.rate == SALES_TAX_RATE for r in sales_rates):
        violations.append(
            f"No sales tax rate of {SALES_TAX_RATE} found; invoice math would not be derivable"
        )
    for inv in invoices_by_id.values():
        expected_tax = (inv.subtotal * SALES_TAX_RATE).quantize(Decimal("0.01"))
        if inv.tax != expected_tax:
            violations.append(
                f"Invoice {inv.invoice_number} tax {inv.tax} != {expected_tax} "
                f"(subtotal x {SALES_TAX_RATE})"
            )
    tax_periods = (
        await db.execute(select(TaxPeriodModel).order_by(TaxPeriodModel.period))
    ).scalars().all()
    if len(tax_periods) != 6:
        violations.append(f"Expected 6 tax periods, found {len(tax_periods)}")
    for i, tax_period in enumerate(tax_periods):
        is_last = i == len(tax_periods) - 1
        if is_last and tax_period.status == "filed":
            violations.append(f"Most recent tax period {tax_period.period} already filed")
        if not is_last and tax_period.status != "filed":
            violations.append(f"Historic tax period {tax_period.period} is not filed")
        if tax_period.status == "filed":
            if tax_period.filed_date is None:
                violations.append(f"Tax period {tax_period.period} filed without a date")
            elif tax_period.filed_date > tax_period.filing_due_date:
                violations.append(f"Tax period {tax_period.period} filed after the due date")

    # -- reimbursements ------------------------------------------------------------
    reimbursed_claim_ids = {c.id for c in claims if c.status == "reimbursed"}
    mirrored_claim_ids = {
        line.matched_expense_claim_id
        for line in bank_lines
        if line.matched_expense_claim_id is not None
    }
    for claim in claims:
        if claim.id in reimbursed_claim_ids and claim.id not in mirrored_claim_ids:
            violations.append(
                f"Reimbursed claim {claim.claim_number} has no bank transaction"
            )


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
