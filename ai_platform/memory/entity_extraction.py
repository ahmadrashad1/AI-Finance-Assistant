from __future__ import annotations

from typing import Any

from ai_platform.orchestration.result_shaping import MAX_LIST_ITEMS_IN_PROMPT

# tool name -> (list field, name field, code field). Explicit and small on
# purpose: adding a new list-shaped tool means adding one entry here, never
# a generic "walk every string field" heuristic that would pull in noise
# (statuses, dates) as if they were entities.
_LIST_TOOL_ENTITY_FIELDS: dict[str, tuple[str, str, str]] = {
    "get_unpaid_invoices": ("invoices", "customer_name", "invoice_number"),
    "search_invoices": ("invoices", "customer_name", "invoice_number"),
    "get_overdue_invoices": ("invoices", "customer_name", "invoice_number"),
    "get_vendor_invoices": ("invoices", "vendor_name", "vendor_invoice_number"),
}

# tool name -> the one identifying name field on its flat result.
_FLAT_TOOL_ENTITY_FIELDS: dict[str, str] = {
    "get_customer_balance": "customer_name",
    "get_vendor_balance": "vendor_name",
    "get_customer": "customer_name",
}


def extract_entities(tool: str, result: dict[str, Any]) -> dict[str, list[str]]:
    """Pulls a small, explicit set of identifying business fields out of a
    tool's own result shape, for the next turn's compact memory summary.
    Never NLP, never keyword matching on the user's message - purely a
    lookup against each tool's already-known result shape.
    """
    if tool in _LIST_TOOL_ENTITY_FIELDS:
        list_field, name_field, code_field = _LIST_TOOL_ENTITY_FIELDS[tool]
        items = result.get(list_field) or []
        names = _dedupe_capped(item.get(name_field) for item in items)
        codes = _dedupe_capped(item.get(code_field) for item in items)
        entities: dict[str, list[str]] = {}
        if names:
            entities[name_field] = names
        if codes:
            entities[code_field] = codes
        return entities

    if tool in _FLAT_TOOL_ENTITY_FIELDS:
        field = _FLAT_TOOL_ENTITY_FIELDS[tool]
        value = result.get(field)
        return {field: [value]} if value else {}

    return {}


def _dedupe_capped(values: Any) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.append(value)
        if len(seen) >= MAX_LIST_ITEMS_IN_PROMPT:
            break
    return seen
