from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_cash_position import (
    GET_CASH_POSITION_TOOL,
    GetCashPositionParams,
    get_cash_position_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCashPositionParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_takes_no_fields() -> None:
    params = GetCashPositionParams()
    assert params.model_dump() == {}


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_CASH_POSITION_TOOL.name == "get_cash_position"
    assert "cash" in GET_CASH_POSITION_TOOL.description.lower()
    assert GET_CASH_POSITION_TOOL.handler is get_cash_position_handler
    assert GET_CASH_POSITION_TOOL.parameters_model is GetCashPositionParams
