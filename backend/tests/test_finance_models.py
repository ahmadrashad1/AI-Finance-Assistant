from __future__ import annotations

from domains.finance.models import CustomerModel, ProductModel, VendorModel


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
