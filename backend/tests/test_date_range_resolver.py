from __future__ import annotations

from datetime import date

import pytest

from ai_platform.date_range_resolver import resolve_date_range

TODAY = date(2024, 3, 15)  # a Friday, inside Q1 2024, in a leap year


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("today", (date(2024, 3, 15), date(2024, 3, 15))),
        ("Today", (date(2024, 3, 15), date(2024, 3, 15))),
        ("yesterday", (date(2024, 3, 14), date(2024, 3, 14))),
        ("this week", (date(2024, 3, 11), date(2024, 3, 17))),
        ("last week", (date(2024, 3, 4), date(2024, 3, 10))),
        ("next week", (date(2024, 3, 18), date(2024, 3, 24))),
        ("this month", (date(2024, 3, 1), date(2024, 3, 31))),
        ("last month", (date(2024, 2, 1), date(2024, 2, 29))),
        ("next month", (date(2024, 4, 1), date(2024, 4, 30))),
        ("this quarter", (date(2024, 1, 1), date(2024, 3, 31))),
        ("last quarter", (date(2023, 10, 1), date(2023, 12, 31))),
        ("next quarter", (date(2024, 4, 1), date(2024, 6, 30))),
        ("this year", (date(2024, 1, 1), date(2024, 12, 31))),
        ("last year", (date(2023, 1, 1), date(2023, 12, 31))),
        ("next year", (date(2025, 1, 1), date(2025, 12, 31))),
        ("ytd", (date(2024, 1, 1), date(2024, 3, 15))),
        ("year to date", (date(2024, 1, 1), date(2024, 3, 15))),
        ("last 30 days", (date(2024, 2, 15), date(2024, 3, 15))),
        ("next 30 days", (date(2024, 3, 15), date(2024, 4, 13))),
        ("last 2 weeks", (date(2024, 3, 2), date(2024, 3, 15))),
        ("next 2 weeks", (date(2024, 3, 15), date(2024, 3, 28))),
        ("last 2 months", (date(2024, 1, 15), date(2024, 3, 15))),
        ("next 2 months", (date(2024, 3, 15), date(2024, 5, 15))),
        ("Q2 2025", (date(2025, 4, 1), date(2025, 6, 30))),
        ("q4 2023", (date(2023, 10, 1), date(2023, 12, 31))),
    ],
)
def test_resolves_expected_range(expression: str, expected: tuple[date, date]) -> None:
    assert resolve_date_range(expression, today=TODAY) == expected


def test_january_last_month_crosses_year_boundary() -> None:
    result = resolve_date_range("last month", today=date(2024, 1, 15))
    assert result == (date(2023, 12, 1), date(2023, 12, 31))


def test_unrecognized_expression_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        resolve_date_range("banana", today=TODAY)


def test_last_zero_days_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not resolve date expression"):
        resolve_date_range("last 0 days", today=TODAY)
