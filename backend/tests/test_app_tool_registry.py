from __future__ import annotations

from app.core.tool_registry import get_tool_registry


def test_registry_includes_get_current_date_and_get_unpaid_invoices() -> None:
    get_tool_registry.cache_clear()
    registry = get_tool_registry()
    names = {spec.name for spec in registry.list_specs()}
    assert names == {"get_current_date", "get_unpaid_invoices"}
