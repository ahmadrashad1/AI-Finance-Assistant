from __future__ import annotations

from app.core.tool_registry import get_tool_registry


def test_registry_includes_all_registered_tools() -> None:
    get_tool_registry.cache_clear()
    registry = get_tool_registry()
    names = {spec.name for spec in registry.list_specs()}
    assert names == {
        "get_current_date",
        "get_unpaid_invoices",
        "search_invoices",
        "get_overdue_invoices",
        "get_customer_balance",
        "get_vendor_balance",
        "get_cash_position",
        "get_vendor_invoices",
        "get_customer",
    }
