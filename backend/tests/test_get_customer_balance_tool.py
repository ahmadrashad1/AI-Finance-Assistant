from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.finance.tools.get_customer_balance import (
    GET_CUSTOMER_BALANCE_TOOL,
    GetCustomerBalanceParams,
    get_customer_balance_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetCustomerBalanceParams(customer_name="Acme", unexpected="value")  # type: ignore[call-arg]


def test_params_model_requires_customer_name() -> None:
    with pytest.raises(ValidationError):
        GetCustomerBalanceParams()  # type: ignore[call-arg]


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_CUSTOMER_BALANCE_TOOL.name == "get_customer_balance"
    assert "customer_name" in GET_CUSTOMER_BALANCE_TOOL.description.lower()
    assert GET_CUSTOMER_BALANCE_TOOL.handler is get_customer_balance_handler
    assert GET_CUSTOMER_BALANCE_TOOL.parameters_model is GetCustomerBalanceParams
