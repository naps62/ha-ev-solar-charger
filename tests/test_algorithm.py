"""Tests for the pure decision algorithm."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, time

import pytest

from custom_components.ev_solar_charger.algorithm import (
    Decision,
    Mode,
    Snapshot,
    SubMode,
    SunState,
    WriteAction,
    compute_decision,
    pick_submode,
)


def test_snapshot_is_frozen_dataclass(base_snapshot: Snapshot) -> None:
    """Snapshot should be immutable so the algorithm can't accidentally mutate inputs."""
    assert dataclasses.is_dataclass(base_snapshot)
    assert base_snapshot.__dataclass_params__.frozen is True


def test_decision_has_required_fields() -> None:
    decision = Decision(
        desired_amps=10,
        write_action=WriteAction.SET_AMPS,
        sub_mode=SubMode.SOLAR,
        reason="test",
        leftover_w=2300.0,
    )
    assert decision.desired_amps == 10
    assert decision.write_action is WriteAction.SET_AMPS
    assert decision.sub_mode is SubMode.SOLAR


def test_mode_enum_values() -> None:
    assert Mode.AUTO.value == "auto"
    assert Mode.FORCE_MIN.value == "force-min"
    assert Mode.FORCE_MAX.value == "force-max"
    assert Mode.OFF.value == "off"


def test_sub_mode_enum_values() -> None:
    assert SubMode.SOLAR.value == "solar"
    assert SubMode.DINNER.value == "dinner"
    assert SubMode.NIGHT.value == "night"
    assert SubMode.SAFETY_FALLBACK.value == "safety-fallback"
    assert SubMode.DISABLED.value == "disabled"
    assert SubMode.FORCE_MIN.value == "force-min"
    assert SubMode.FORCE_MAX.value == "force-max"


def test_write_action_enum_values() -> None:
    assert {a.value for a in WriteAction} == {"none", "turn_off", "turn_on_and_set", "set_amps"}


def test_sun_state_enum_values() -> None:
    assert SunState.ABOVE.value == "above_horizon"
    assert SunState.BELOW.value == "below_horizon"


@pytest.mark.parametrize(
    ("hour", "minute", "sun", "expected"),
    [
        (10, 0, SunState.ABOVE, SubMode.SOLAR),     # mid-morning, sun up
        (15, 59, SunState.ABOVE, SubMode.SOLAR),    # just before dinner
        (16, 0, SunState.ABOVE, SubMode.DINNER),    # boundary: dinner starts
        (21, 59, SunState.ABOVE, SubMode.DINNER),   # just before night
        (22, 0, SunState.ABOVE, SubMode.NIGHT),     # boundary: night starts
        (23, 30, SunState.BELOW, SubMode.NIGHT),    # late night
        (5, 30, SunState.BELOW, SubMode.NIGHT),     # pre-dawn, sun still down
        (7, 0, SunState.ABOVE, SubMode.SOLAR),      # post-sunrise
        (14, 0, SunState.BELOW, SubMode.NIGHT),     # daytime but sun below (eclipse/weather)
    ],
)
def test_pick_submode(hour: int, minute: int, sun: SunState, expected: SubMode) -> None:
    now = datetime(2026, 5, 27, hour, minute, tzinfo=UTC)
    result = pick_submode(
        now=now,
        sun_state=sun,
        dinner_start=time(16, 0),
        night_start=time(22, 0),
    )
    assert result is expected


def test_disabled_returns_no_op(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, enabled=False)
    d = compute_decision(s)
    assert d.write_action is WriteAction.NONE
    assert d.sub_mode is SubMode.DISABLED
    assert d.desired_amps is None


def test_cable_off_returns_no_op(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, cable_connected=False)
    d = compute_decision(s)
    assert d.write_action is WriteAction.NONE
    assert d.sub_mode is SubMode.DISABLED


def test_not_at_home_returns_no_op(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, at_home=False)
    d = compute_decision(s)
    assert d.write_action is WriteAction.NONE
    assert d.sub_mode is SubMode.DISABLED


def test_mode_off_turns_off(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.OFF, last_desired_amps=10)
    d = compute_decision(s)
    assert d.desired_amps == 0
    assert d.write_action is WriteAction.TURN_OFF


def test_mode_off_no_write_if_already_off(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.OFF, last_desired_amps=0)
    d = compute_decision(s)
    assert d.desired_amps == 0
    assert d.write_action is WriteAction.NONE


def test_force_min(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.FORCE_MIN, last_desired_amps=None)
    d = compute_decision(s)
    assert d.desired_amps == 5
    assert d.sub_mode is SubMode.FORCE_MIN
    assert d.write_action is WriteAction.TURN_ON_AND_SET  # last was None == off


def test_force_max_from_off(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.FORCE_MAX, last_desired_amps=0)
    d = compute_decision(s)
    assert d.desired_amps == 16
    assert d.write_action is WriteAction.TURN_ON_AND_SET


def test_force_max_from_charging(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.FORCE_MAX, last_desired_amps=10)
    d = compute_decision(s)
    assert d.desired_amps == 16
    assert d.write_action is WriteAction.SET_AMPS


def test_dinner_caps_at_6a(base_snapshot: Snapshot) -> None:
    """At 17:00, dinner sub-mode applies the 6A cap."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 17, 0, tzinfo=UTC),
        last_desired_amps=None,
    )
    d = compute_decision(s)
    assert d.desired_amps == 6
    assert d.sub_mode is SubMode.DINNER
    assert d.write_action is WriteAction.TURN_ON_AND_SET


def test_dinner_ignores_solar_surplus(base_snapshot: Snapshot) -> None:
    """Dinner mode caps at 6A even with massive solar export."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 18, 0, tzinfo=UTC),
        net_grid_w=-4000.0,  # huge export
        last_desired_amps=10,
    )
    d = compute_decision(s)
    assert d.desired_amps == 6
    assert d.sub_mode is SubMode.DINNER


def test_dinner_ignores_soc(base_snapshot: Snapshot) -> None:
    """Dinner mode caps at 6A regardless of SOC vs target."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 19, 0, tzinfo=UTC),
        ev_soc=95.0,
        target_day_soc=50.0,
        last_desired_amps=6,
    )
    d = compute_decision(s)
    assert d.desired_amps == 6
    assert d.write_action is WriteAction.NONE  # no change


def test_night_below_target_charges_at_max(base_snapshot: Snapshot) -> None:
    """At 23:00 with SOC below night target, charge at MAX."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 23, 0, tzinfo=UTC),
        ev_soc=60.0,
        target_night_soc=80.0,
        last_desired_amps=None,
    )
    d = compute_decision(s)
    assert d.desired_amps == 16
    assert d.sub_mode is SubMode.NIGHT
    assert d.write_action is WriteAction.TURN_ON_AND_SET


def test_night_at_target_stops(base_snapshot: Snapshot) -> None:
    """At 23:00 with SOC at/above night target, stop."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 23, 0, tzinfo=UTC),
        ev_soc=80.0,
        target_night_soc=80.0,
        last_desired_amps=16,
    )
    d = compute_decision(s)
    assert d.desired_amps == 0
    assert d.sub_mode is SubMode.NIGHT
    assert d.write_action is WriteAction.TURN_OFF


def test_night_above_target_stays_off(base_snapshot: Snapshot) -> None:
    """Already at 0, SOC above target → no write."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 2, 0, tzinfo=UTC),
        sun_state=SunState.BELOW,
        ev_soc=90.0,
        target_night_soc=80.0,
        last_desired_amps=0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 0
    assert d.write_action is WriteAction.NONE
