from __future__ import annotations

from functools import lru_cache

from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_customer_balance import GET_CUSTOMER_BALANCE_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL
from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL


@lru_cache
def get_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    registry.register(SEARCH_INVOICES_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    registry.register(GET_CUSTOMER_BALANCE_TOOL)
    return registry
