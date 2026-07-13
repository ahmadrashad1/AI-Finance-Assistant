from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_aging_report import (
    GET_AGING_REPORT_TOOL,
    GetAgingReportParams,
    get_aging_report_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetAgingReportParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_takes_no_fields() -> None:
    assert GetAgingReportParams().model_dump() == {}


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_AGING_REPORT_TOOL.name == "get_aging_report"
    assert "aging" in GET_AGING_REPORT_TOOL.description.lower()
    assert GET_AGING_REPORT_TOOL.handler is get_aging_report_handler
    assert GET_AGING_REPORT_TOOL.parameters_model is GetAgingReportParams
