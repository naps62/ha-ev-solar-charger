"""Pytest fixtures shared across tests."""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest

from custom_components.ev_solar_charger.algorithm import (
    Mode,
    Snapshot,
    SunState,
)


@pytest.fixture
def base_snapshot() -> Snapshot:
    """Return a baseline snapshot used as the starting point for tests.

    Defaults: 12:00 noon, sun up, no grid import/export, EV at home plugged in,
    auto mode, day target 80, night target 80, dinner 16:00, night 22:00,
    EV SOC 50%, last_desired_amps=None.
    """
    return Snapshot(
        now=datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC),
        sun_state=SunState.ABOVE,
        net_grid_w=0.0,
        ev_consumption_w=0.0,
        ev_soc=50.0,
        cable_connected=True,
        at_home=True,
        enabled=True,
        mode=Mode.AUTO,
        target_day_soc=80.0,
        target_night_soc=80.0,
        dinner_start=time(16, 0),
        night_start=time(22, 0),
        last_desired_amps=None,
    )
