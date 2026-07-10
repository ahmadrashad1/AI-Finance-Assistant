from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.tools.get_unpaid_invoices import (
    GET_UNPAID_INVOICES_TOOL,
    GetUnpaidInvoicesParams,
    get_unpaid_invoices_handler,
)


def test_params_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        GetUnpaidInvoicesParams(unexpected="value")


def test_params_model_rejects_negative_minimum_amount() -> None:
    with pytest.raises(ValidationError):
        GetUnpaidInvoicesParams(minimum_amount=Decimal("-1"))


def test_params_model_defaults_are_none() -> None:
    params = GetUnpaidInvoicesParams()
    assert params.customer_id is None
    assert params.minimum_amount is None


def test_tool_spec_wires_up_the_handler() -> None:
    assert GET_UNPAID_INVOICES_TOOL.name == "get_unpaid_invoices"
    assert GET_UNPAID_INVOICES_TOOL.handler is get_unpaid_invoices_handler
    assert GET_UNPAID_INVOICES_TOOL.parameters_model is GetUnpaidInvoicesParams
    description = GET_UNPAID_INVOICES_TOOL.description.lower()
    for phrase in [
        "who still owes us money",
        "which invoices haven't been paid",
        "outstanding invoices",
        "customers with overdue invoices",
        "show unpaid invoices",
    ]:
        assert phrase in description


@pytest.mark.asyncio
async def test_handler_returns_empty_result_against_empty_db(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await get_unpaid_invoices_handler(GetUnpaidInvoicesParams(), context)
    assert result.invoices == []
    assert result.summary.count == 0
    assert result.summary.total_outstanding == Decimal("0")
