from __future__ import annotations

import pytest
from pydantic import BaseModel

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from ai_platform.tool_registry.result_validator import ResultValidationError, validate_result


class _Params(BaseModel):
    pass


class _Result(BaseModel):
    value: int


async def _handler(params: _Params, context: ToolContext) -> _Result:
    return _Result(value=1)


_SPEC = ToolSpec(
    name="dummy",
    description="dummy tool",
    parameters_model=_Params,
    result_model=_Result,
    handler=_handler,
)


def test_validate_result_accepts_matching_payload() -> None:
    validated = validate_result(_SPEC, {"value": 42})
    assert validated == {"value": 42}


def test_validate_result_rejects_mismatched_payload() -> None:
    with pytest.raises(ResultValidationError):
        validate_result(_SPEC, {"wrong_field": "oops"})
