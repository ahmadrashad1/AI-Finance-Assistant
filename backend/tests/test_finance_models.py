from __future__ import annotations

from domains.finance.models import (
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
    VendorModel,
)


def test_customer_model_uses_finance_schema() -> None:
    assert CustomerModel.__table__.schema == "finance"


def test_customer_model_has_expected_columns() -> None:
    columns = {c.name for c in CustomerModel.__table__.columns}
    assert {
        "id", "customer_code", "company_name", "industry", "contact_name",
        "contact_email", "payment_terms", "credit_limit", "status",
        "created_at", "updated_at",
    } <= columns
    assert "balance" not in columns


def test_vendor_model_has_expected_columns() -> None:
    columns = {c.name for c in VendorModel.__table__.columns}
    assert {
        "id", "vendor_code", "company_name", "category", "contact_name",
        "contact_email", "payment_terms", "preferred", "status",
        "created_at", "updated_at",
    } <= columns


def test_product_model_has_expected_columns() -> None:
    columns = {c.name for c in ProductModel.__table__.columns}
    assert {"id", "sku", "name", "category", "unit_price", "is_active", "created_at"} <= columns


def test_department_model_has_expected_columns() -> None:
    columns = {c.name for c in DepartmentModel.__table__.columns}
    assert {"id", "name", "created_at"} <= columns


def test_employee_model_references_department() -> None:
    fk_targets = {fk.target_fullname for fk in EmployeeModel.__table__.foreign_keys}
    assert "finance.departments.id" in fk_targets


def test_purchase_order_model_references_vendor_and_employee() -> None:
    fk_targets = {fk.target_fullname for fk in PurchaseOrderModel.__table__.foreign_keys}
    assert "finance.vendors.id" in fk_targets
    assert "finance.employees.id" in fk_targets


def test_purchase_order_item_model_references_po_and_product() -> None:
    fk_targets = {fk.target_fullname for fk in PurchaseOrderItemModel.__table__.foreign_keys}
    assert "finance.purchase_orders.id" in fk_targets
    assert "finance.products.id" in fk_targets


def test_invoice_model_has_expected_columns() -> None:
    columns = {c.name for c in InvoiceModel.__table__.columns}
    assert {
        "id", "invoice_number", "customer_id", "purchase_order_id", "issue_date",
        "due_date", "status", "currency", "subtotal", "tax", "total",
        "amount_paid", "balance", "created_at", "updated_at",
    } <= columns


def test_invoice_model_purchase_order_is_nullable() -> None:
    column = InvoiceModel.__table__.columns["purchase_order_id"]
    assert column.nullable is True


def test_invoice_item_model_references_invoice_and_product() -> None:
    fk_targets = {fk.target_fullname for fk in InvoiceItemModel.__table__.foreign_keys}
    assert "finance.invoices.id" in fk_targets
    assert "finance.products.id" in fk_targets


def test_payment_model_references_invoice() -> None:
    fk_targets = {fk.target_fullname for fk in PaymentModel.__table__.foreign_keys}
    assert "finance.invoices.id" in fk_targets


def test_expense_claim_model_references_employee() -> None:
    fk_targets = {fk.target_fullname for fk in ExpenseClaimModel.__table__.foreign_keys}
    assert "finance.employees.id" in fk_targets
