from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.search_customers import (
    SEARCH_CUSTOMERS_TOOL,
    SearchCustomersParams,
    search_customers_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        SearchCustomersParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_requires_name_query() -> None:
    with pytest.raises(ValidationError):
        SearchCustomersParams()  # type: ignore[call-arg]


def test_tool_spec_wires_up_the_handler() -> None:
    assert SEARCH_CUSTOMERS_TOOL.name == "search_customers"
    assert "fragment" in SEARCH_CUSTOMERS_TOOL.description.lower() \
        or "partial" in SEARCH_CUSTOMERS_TOOL.description.lower()
    assert SEARCH_CUSTOMERS_TOOL.handler is search_customers_handler
    assert SEARCH_CUSTOMERS_TOOL.parameters_model is SearchCustomersParams
