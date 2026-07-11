from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from domains.finance.tools.search_invoices import SEARCH_INVOICES_TOOL, SearchInvoicesParams


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        SearchInvoicesParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SearchInvoicesParams(status="not-a-real-status")  # type: ignore[arg-type]


def test_params_model_rejects_negative_minimum_amount() -> None:
    with pytest.raises(ValidationError):
        SearchInvoicesParams(minimum_amount=Decimal("-1"))


def test_params_model_defaults_are_all_none() -> None:
    params = SearchInvoicesParams()
    assert params.invoice_number is None
    assert params.customer_id is None
    assert params.status is None
    assert params.minimum_amount is None
    assert params.maximum_amount is None
    assert params.due_before is None
    assert params.due_after is None


def test_tool_spec_wires_up_the_handler() -> None:
    from domains.finance.tools.search_invoices import search_invoices_handler

    assert SEARCH_INVOICES_TOOL.name == "search_invoices"
    assert "invoice_number" in SEARCH_INVOICES_TOOL.description.lower()
    assert SEARCH_INVOICES_TOOL.handler is search_invoices_handler
    assert SEARCH_INVOICES_TOOL.parameters_model is SearchInvoicesParams
