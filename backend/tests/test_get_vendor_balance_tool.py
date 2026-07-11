from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_vendor_balance import (
    GET_VENDOR_BALANCE_TOOL,
    GetVendorBalanceParams,
    get_vendor_balance_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetVendorBalanceParams(vendor_name="Summit", unexpected="value")  # type: ignore[call-arg]


def test_params_model_requires_vendor_name() -> None:
    with pytest.raises(ValidationError):
        GetVendorBalanceParams()  # type: ignore[call-arg]


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_VENDOR_BALANCE_TOOL.name == "get_vendor_balance"
    assert "vendor_name" in GET_VENDOR_BALANCE_TOOL.description.lower()
    assert GET_VENDOR_BALANCE_TOOL.handler is get_vendor_balance_handler
    assert GET_VENDOR_BALANCE_TOOL.parameters_model is GetVendorBalanceParams
