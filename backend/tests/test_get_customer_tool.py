from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL, GetCustomerParams


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCustomerParams(unexpected="value")  # type: ignore[call-arg]


def test_params_model_requires_customer_name() -> None:
    with pytest.raises(ValidationError):
        GetCustomerParams()  # type: ignore[call-arg]


def test_tool_spec_wires_up_the_handler() -> None:
    from domains.finance.tools.get_customer import get_customer_handler

    assert GET_CUSTOMER_TOOL.name == "get_customer"
    assert "not a code" in GET_CUSTOMER_TOOL.description.lower()
    assert GET_CUSTOMER_TOOL.handler is get_customer_handler
    assert GET_CUSTOMER_TOOL.parameters_model is GetCustomerParams
