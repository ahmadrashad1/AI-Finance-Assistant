from __future__ import annotations

from datetime import date

import pytest

from domains.finance.simulation import DEFAULT_SIMULATION_TODAY, simulation_today


def test_default_simulation_date_is_fixed_anchor() -> None:
    assert date(2026, 7, 8) == DEFAULT_SIMULATION_TODAY
    assert simulation_today() == date(2026, 7, 8)


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATION_TODAY", "2027-01-15")
    assert simulation_today() == date(2027, 1, 15)


def test_invalid_env_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATION_TODAY", "not-a-date")
    with pytest.raises(ValueError):
        simulation_today()


def test_simulator_constants_anchor_matches_simulation_module() -> None:
    from domains.finance.simulator.constants import SIMULATION_TODAY

    assert SIMULATION_TODAY == DEFAULT_SIMULATION_TODAY
