from __future__ import annotations

from typing import Any, Final

MAX_LIST_ITEMS_IN_PROMPT: Final[int] = 10


def cap_result_for_prompt(
    result: dict[str, Any] | None, *, max_items: int = MAX_LIST_ITEMS_IN_PROMPT
) -> dict[str, Any] | None:
    """Truncates list-valued fields before a tool result is embedded in the
    Phase-2 prompt, so a large result set (e.g. 87 unpaid invoices) can't
    exceed the LLM provider's request-size limit. This only shapes what the
    Phase-2 model sees - the full, uncapped result is still what the tool
    returns and what tool_executions persists.
    """
    if result is None:
        return None
    capped: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, list) and len(value) > max_items:
            capped[key] = value[:max_items]
            capped["_truncated"] = True
            capped[f"_{key}_omitted_count"] = len(value) - max_items
        else:
            capped[key] = value
    return capped
