from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ai_platform.tool_registry.registry import ToolSpec


class ResultValidationError(Exception):
    """Raised when a tool handler's return value doesn't match its declared result schema."""


def validate_result(spec: ToolSpec, raw_result: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = spec.result_model.model_validate(raw_result)
    except PydanticValidationError as exc:
        raise ResultValidationError(
            f"Tool '{spec.name}' returned a result that doesn't match its declared schema: {exc}"
        ) from exc
    return validated.model_dump()
