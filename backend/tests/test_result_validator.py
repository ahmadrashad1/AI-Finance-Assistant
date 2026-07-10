from __future__ import annotations

import json
from decimal import Decimal

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


class _DecimalResult(BaseModel):
    amount: Decimal


async def _decimal_handler(params: _Params, context: ToolContext) -> _DecimalResult:
    return _DecimalResult(amount=Decimal("1234.50"))


_DECIMAL_SPEC = ToolSpec(
    name="decimal_dummy",
    description="dummy tool returning Decimal",
    parameters_model=_Params,
    result_model=_DecimalResult,
    handler=_decimal_handler,
)


def test_validate_result_serializes_decimal_as_json_safe_string() -> None:
    validated = validate_result(_DECIMAL_SPEC, {"amount": Decimal("1234.50")})
    assert validated == {"amount": "1234.50"}
    # Must be usable by json.dumps directly - this is the actual bug this
    # test guards against (tool_executions.result JSONB storage and
    # ChatWorkflow's Phase-2 prompt both call json.dumps on this dict).
    json.dumps(validated)
