from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from domains.finance.models import BankAccountModel
from domains.finance.tools.forecast_cash_flow import (
    ForecastCashFlowParams,
    forecast_cash_flow_handler,
)
from domains.finance.tools.get_payment_prioritization import (
    GetPaymentPrioritizationParams,
    get_payment_prioritization_handler,
)


@pytest.mark.asyncio
async def test_forecast_cash_flow_tool_returns_requested_period_count(
    clean_db: None, db_session: AsyncSession
) -> None:
    account = BankAccountModel(
        id=uuid.uuid4(), account_name="Operating", opening_balance=Decimal("5000"),
        opening_date=date(2025, 1, 1),
    )
    db_session.add(account)
    await db_session.commit()

    context = ToolContext(db=db_session)
    result = await forecast_cash_flow_handler(ForecastCashFlowParams(weeks=4), context)
    assert len(result.periods) == 4


@pytest.mark.asyncio
async def test_get_payment_prioritization_tool_empty_db_returns_no_items(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await get_payment_prioritization_handler(GetPaymentPrioritizationParams(), context)
    assert result.items == []
