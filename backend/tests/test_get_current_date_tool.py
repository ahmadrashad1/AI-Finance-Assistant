from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_platform.tool_registry.tools.get_current_date import (
    GET_CURRENT_DATE_TOOL,
    GetCurrentDateParams,
    get_current_date_handler,
)


@pytest.mark.asyncio
async def test_handler_returns_iso_date_and_day_of_week() -> None:
    result = await get_current_date_handler(GetCurrentDateParams())
    assert len(result.date) == 10
    assert result.date[4] == "-"
    assert result.date[7] == "-"
    assert result.day_of_week in {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCurrentDateParams(unexpected="value")


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_CURRENT_DATE_TOOL.name == "get_current_date"
    assert "date" in GET_CURRENT_DATE_TOOL.description.lower()
    assert GET_CURRENT_DATE_TOOL.handler is get_current_date_handler
    assert GET_CURRENT_DATE_TOOL.parameters_model is GetCurrentDateParams
