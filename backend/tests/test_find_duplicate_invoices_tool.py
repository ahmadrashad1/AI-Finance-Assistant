from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.find_duplicate_invoices import (
    FIND_DUPLICATE_INVOICES_TOOL,
    FindDuplicateInvoicesParams,
    find_duplicate_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        FindDuplicateInvoicesParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_invoice_number_is_optional() -> None:
    assert FindDuplicateInvoicesParams().invoice_number is None
    assert FindDuplicateInvoicesParams(invoice_number="INV-1001").invoice_number == "INV-1001"


def test_tool_spec_wires_up_the_handler() -> None:
    assert FIND_DUPLICATE_INVOICES_TOOL.name == "find_duplicate_invoices"
    assert "duplicate" in FIND_DUPLICATE_INVOICES_TOOL.description.lower()
    assert FIND_DUPLICATE_INVOICES_TOOL.handler is find_duplicate_invoices_handler
    assert FIND_DUPLICATE_INVOICES_TOOL.parameters_model is FindDuplicateInvoicesParams
