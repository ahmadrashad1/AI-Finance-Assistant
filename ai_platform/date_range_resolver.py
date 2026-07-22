from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_QUARTER_PATTERN = re.compile(r"^q([1-4])\s+(\d{4})$")
_RELATIVE_N_PATTERN = re.compile(r"^(last|next)\s+(\d+)\s+(day|days|week|weeks|month|months)$")


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = 3 * (quarter - 1) + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return start, end


def _quarter_of(month: int) -> int:
    return (month - 1) // 3 + 1


def _week_bounds(today: date, offset_weeks: int) -> tuple[date, date]:
    this_week_start = today - timedelta(days=today.weekday())
    start = this_week_start + timedelta(days=7 * offset_weeks)
    return start, start + timedelta(days=6)


def _month_bounds_offset(today: date, offset_months: int) -> tuple[date, date]:
    target = _add_months(today.replace(day=1), offset_months)
    return _month_bounds(target.year, target.month)


def _quarter_bounds_offset(today: date, offset_quarters: int) -> tuple[date, date]:
    zero_based_quarter = _quarter_of(today.month) - 1
    total = today.year * 4 + zero_based_quarter + offset_quarters
    year, quarter_zero_based = divmod(total, 4)
    return _quarter_bounds(year, quarter_zero_based + 1)


def _year_bounds_offset(today: date, offset_years: int) -> tuple[date, date]:
    year = today.year + offset_years
    return date(year, 1, 1), date(year, 12, 31)


def resolve_date_range(expression: str, *, today: date) -> tuple[date, date]:
    """Resolves a relative date expression into an explicit (date_from,
    date_to) range, computed deterministically against `today` (the
    simulation date, never the model). This is the only place relative-
    date arithmetic happens - the planning prompt requires the LLM to
    call the resolve_date_range tool for any relative expression rather
    than compute dates itself (PRD Ch.24, Deterministic Date Resolution).

    Supported expressions (case-insensitive, whitespace-normalized):
    today, yesterday, this/last/next week, this/last/next month,
    this/last/next quarter, this/last/next year, ytd / year to date,
    last/next N days, last/next N weeks, last/next N months, and an
    explicit "QN YYYY" (e.g. "Q2 2025").
    """
    normalized = " ".join(expression.strip().lower().split())

    if normalized == "today":
        return today, today
    if normalized == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if normalized == "this week":
        return _week_bounds(today, 0)
    if normalized == "last week":
        return _week_bounds(today, -1)
    if normalized == "next week":
        return _week_bounds(today, 1)
    if normalized == "this month":
        return _month_bounds_offset(today, 0)
    if normalized == "last month":
        return _month_bounds_offset(today, -1)
    if normalized == "next month":
        return _month_bounds_offset(today, 1)
    if normalized == "this quarter":
        return _quarter_bounds_offset(today, 0)
    if normalized == "last quarter":
        return _quarter_bounds_offset(today, -1)
    if normalized == "next quarter":
        return _quarter_bounds_offset(today, 1)
    if normalized == "this year":
        return _year_bounds_offset(today, 0)
    if normalized == "last year":
        return _year_bounds_offset(today, -1)
    if normalized == "next year":
        return _year_bounds_offset(today, 1)
    if normalized in ("ytd", "year to date"):
        return date(today.year, 1, 1), today

    match = _RELATIVE_N_PATTERN.match(normalized)
    if match:
        direction, n_str, unit = match.groups()
        n = int(n_str)
        if n < 1:
            raise _unresolved(expression)
        forward = direction == "next"
        if unit.startswith("day"):
            span = timedelta(days=n - 1)
            return (today, today + span) if forward else (today - span, today)
        if unit.startswith("week"):
            span = timedelta(days=n * 7 - 1)
            return (today, today + span) if forward else (today - span, today)
        return (today, _add_months(today, n)) if forward else (_add_months(today, -n), today)

    match = _QUARTER_PATTERN.match(normalized)
    if match:
        quarter = int(match.group(1))
        year = int(match.group(2))
        return _quarter_bounds(year, quarter)

    raise _unresolved(expression)


def _unresolved(expression: str) -> ValueError:
    return ValueError(
        f"Could not resolve date expression: '{expression}'. Try things like "
        "'last month', 'next quarter', 'YTD', 'last 30 days', 'next 8 weeks', "
        "or 'Q2 2025'."
    )
