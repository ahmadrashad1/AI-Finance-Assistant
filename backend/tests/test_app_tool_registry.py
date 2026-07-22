from __future__ import annotations

from app.core.tool_registry import get_tool_registry


def test_registry_includes_all_registered_tools() -> None:
    get_tool_registry.cache_clear()
    registry = get_tool_registry()
    names = {spec.name for spec in registry.list_specs()}
    assert names == {
        "get_current_date",
        "resolve_date_range",
        "get_unpaid_invoices",
        "search_invoices",
        "get_overdue_invoices",
        "get_customer_balance",
        "get_vendor_balance",
        "get_cash_position",
        "get_vendor_invoices",
        "get_customer",
        "get_aging_report",
        "find_duplicate_invoices",
        "search_customers",
        "get_expense_claims",
        "get_pending_expense_approvals",
        "get_expense_policy_violations",
        "get_expense_summary_by_department",
        "find_duplicate_expense_claims",
        "get_customer_payment_behavior",
        "get_credit_exposure",
        "list_customers_over_credit_limit",
        "assess_credit_risk",
        "get_expected_inflows",
        "get_expected_outflows",
        "forecast_cash_flow",
        "get_payment_prioritization",
    }
