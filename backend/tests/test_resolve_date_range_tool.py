from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.tool_registry.registry import ToolContext
from ai_platform.tool_registry.tools.resolve_date_range import (
    ResolveDateRangeParams,
    resolve_date_range_handler,
)


@pytest.mark.asyncio
async def test_resolves_this_month_against_simulation_today(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    result = await resolve_date_range_handler(
        ResolveDateRangeParams(expression="this month"), context
    )
    assert result.date_from.day == 1
    assert result.date_to >= result.date_from


@pytest.mark.asyncio
async def test_unrecognized_expression_raises_value_error(
    clean_db: None, db_session: AsyncSession
) -> None:
    context = ToolContext(db=db_session)
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        await resolve_date_range_handler(ResolveDateRangeParams(expression="banana"), context)
