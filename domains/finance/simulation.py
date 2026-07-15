from __future__ import annotations

# Domain-side alias for the platform simulation clock, so finance services and
# the simulator never touch the system clock directly (PRD Ch.19). The clock
# itself lives in ai_platform because platform-level tools (get_current_date)
# must agree with the domain on what "today" is, and ai_platform cannot import
# domains.
from ai_platform.simulation_clock import (
    DEFAULT_SIMULATION_TODAY,
    full_months_between,
    simulation_today,
)

__all__ = ["DEFAULT_SIMULATION_TODAY", "full_months_between", "simulation_today"]
