from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_vendor_invoices import (
    GET_VENDOR_INVOICES_TOOL,
    GetVendorInvoicesParams,
    get_vendor_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetVendorInvoicesParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_defaults_are_none() -> None:
    params = GetVendorInvoicesParams()
    assert params.vendor_id is None


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_VENDOR_INVOICES_TOOL.name == "get_vendor_invoices"
    assert "vendor" in GET_VENDOR_INVOICES_TOOL.description.lower()
    assert GET_VENDOR_INVOICES_TOOL.handler is get_vendor_invoices_handler
    assert GET_VENDOR_INVOICES_TOOL.parameters_model is GetVendorInvoicesParams
