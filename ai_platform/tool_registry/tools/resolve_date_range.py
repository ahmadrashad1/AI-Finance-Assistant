from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ai_platform.date_range_resolver import resolve_date_range
from ai_platform.simulation_clock import simulation_today
from ai_platform.tool_registry.registry import ToolContext, ToolSpec


class ResolveDateRangeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str


class ResolveDateRangeResult(BaseModel):
    date_from: date
    date_to: date


async def resolve_date_range_handler(
    params: ResolveDateRangeParams, context: ToolContext
) -> ResolveDateRangeResult:
    date_from, date_to = resolve_date_range(params.expression, today=simulation_today())
    return ResolveDateRangeResult(date_from=date_from, date_to=date_to)


RESOLVE_DATE_RANGE_TOOL = ToolSpec(
    name="resolve_date_range",
    description=(
        "Converts a relative date expression (e.g. 'last month', 'next "
        "quarter', 'YTD', 'last 30 days', 'next 8 weeks', 'Q2 2025') into "
        "an explicit date_from/date_to range, computed against the "
        "simulation's current date - never guess these dates yourself. "
        "Call this FIRST whenever the user's request uses a relative "
        "time expression, then pass the returned date_from/date_to into "
        "whichever tool actually answers the question (e.g. "
        "get_expense_claims, get_expected_inflows). Does NOT retrieve "
        "any business data itself - it only does date arithmetic. If the "
        "expression can't be resolved, it fails with an error explaining "
        "which forms are supported; ask the user for an explicit range "
        "in that case."
    ),
    parameters_model=ResolveDateRangeParams,
    result_model=ResolveDateRangeResult,
    handler=resolve_date_range_handler,
)
