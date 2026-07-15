from __future__ import annotations

import os
from datetime import date

# The single simulated "today" for the whole platform (PRD Ch.19, Simulation
# Date). Aging, overdue status, depreciation, close periods, and forecasts all
# derive from this date -- never from the machine's clock -- so that seeded
# data, tool output, and evaluation results stay stable over real time.
DEFAULT_SIMULATION_TODAY = date(2026, 7, 8)

_ENV_VAR = "SIMULATION_TODAY"


def simulation_today() -> date:
    """Return the configured simulation date (env ``SIMULATION_TODAY``, ISO format)."""
    raw = os.environ.get(_ENV_VAR)
    return date.fromisoformat(raw) if raw else DEFAULT_SIMULATION_TODAY


def full_months_between(start: date, end: date) -> int:
    """Whole calendar months elapsed from ``start`` to ``end``.

    The canonical month arithmetic for depreciation: the seeder and the
    consistency check must agree on what "fully depreciated" means.
    """
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)
