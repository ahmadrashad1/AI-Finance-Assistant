from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_overdue_invoices import (
    GET_OVERDUE_INVOICES_TOOL,
    GetOverdueInvoicesParams,
    get_overdue_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetOverdueInvoicesParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_rejects_negative_minimum_days() -> None:
    with pytest.raises(ValidationError):
        GetOverdueInvoicesParams(minimum_days=-1)


def test_params_model_defaults_are_none() -> None:
    params = GetOverdueInvoicesParams()
    assert params.customer_id is None
    assert params.minimum_days is None


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_OVERDUE_INVOICES_TOOL.name == "get_overdue_invoices"
    assert "overdue" in GET_OVERDUE_INVOICES_TOOL.description.lower()
    assert GET_OVERDUE_INVOICES_TOOL.handler is get_overdue_invoices_handler
    assert GET_OVERDUE_INVOICES_TOOL.parameters_model is GetOverdueInvoicesParams
