from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec


class GetCurrentDateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCurrentDateResult(BaseModel):
    date: str
    day_of_week: str


async def get_current_date_handler(
    params: GetCurrentDateParams, context: ToolContext
) -> GetCurrentDateResult:
    now = datetime.now(UTC)
    return GetCurrentDateResult(date=now.date().isoformat(), day_of_week=now.strftime("%A"))


GET_CURRENT_DATE_TOOL = ToolSpec(
    name="get_current_date",
    description=(
        "Returns today's current date (ISO 8601, e.g. '2026-07-07') and day "
        "of week. Use this whenever the user asks what today's date is."
    ),
    parameters_model=GetCurrentDateParams,
    result_model=GetCurrentDateResult,
    handler=get_current_date_handler,
)
