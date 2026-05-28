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
    safety_fallback_decision,
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
        (10, 0, SunState.ABOVE, SubMode.SOLAR),  # mid-morning, sun up
        (15, 59, SunState.ABOVE, SubMode.SOLAR),  # just before dinner
        (16, 0, SunState.ABOVE, SubMode.DINNER),  # boundary: dinner starts
        (21, 59, SunState.ABOVE, SubMode.DINNER),  # just before night
        (22, 0, SunState.ABOVE, SubMode.NIGHT),  # boundary: night starts
        (23, 30, SunState.BELOW, SubMode.NIGHT),  # late night
        (5, 30, SunState.BELOW, SubMode.NIGHT),  # pre-dawn, sun still down
        (7, 0, SunState.ABOVE, SubMode.SOLAR),  # post-sunrise
        (14, 0, SunState.BELOW, SubMode.NIGHT),  # daytime but sun below (eclipse/weather)
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
    assert d.desired_amps == 14
    assert d.write_action is WriteAction.TURN_ON_AND_SET


def test_force_max_from_charging(base_snapshot: Snapshot) -> None:
    s = dataclasses.replace(base_snapshot, mode=Mode.FORCE_MAX, last_desired_amps=10)
    d = compute_decision(s)
    assert d.desired_amps == 14
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
    assert d.desired_amps == 14
    assert d.sub_mode is SubMode.NIGHT
    assert d.write_action is WriteAction.TURN_ON_AND_SET


def test_night_at_target_stops(base_snapshot: Snapshot) -> None:
    """At 23:00 with SOC at/above night target, stop."""
    s = dataclasses.replace(
        base_snapshot,
        now=datetime(2026, 5, 27, 23, 0, tzinfo=UTC),
        ev_soc=80.0,
        target_night_soc=80.0,
        last_desired_amps=14,
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


def test_solar_below_target_positive_leftover_uses_amps(base_snapshot: Snapshot) -> None:
    """Exporting 2300W and EV idle → leftover 2300W → 10A."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-2300.0,
        ev_consumption_w=0.0,
        ev_soc=60.0,
        target_day_soc=80.0,
        last_desired_amps=None,
    )
    d = compute_decision(s)
    assert d.desired_amps == 10  # 2300 / 230 = 10
    assert d.sub_mode is SubMode.SOLAR
    assert d.leftover_w == 2300.0


def test_solar_below_target_negative_leftover_floors_at_min(base_snapshot: Snapshot) -> None:
    """Importing → leftover negative → still charge at MIN below target."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=500.0,  # importing
        ev_consumption_w=0.0,
        ev_soc=60.0,
        target_day_soc=80.0,
        last_desired_amps=None,
    )
    d = compute_decision(s)
    assert d.desired_amps == 5  # MIN_AMPS
    assert d.sub_mode is SubMode.SOLAR


def test_solar_below_target_sub_min_leftover_floors_at_min(base_snapshot: Snapshot) -> None:
    """Leftover positive but < MIN_AMPS worth → floor at MIN."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-500.0,
        ev_consumption_w=0.0,
        ev_soc=60.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 5


def test_solar_at_target_positive_leftover(base_snapshot: Snapshot) -> None:
    """At target, follow leftover (no floor)."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-2300.0,
        ev_consumption_w=0.0,
        ev_soc=80.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 10


def test_solar_at_target_zero_leftover_stops(base_snapshot: Snapshot) -> None:
    """At target, no surplus → 0A (solar-only)."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=0.0,
        ev_consumption_w=0.0,
        ev_soc=80.0,
        target_day_soc=80.0,
        last_desired_amps=5,
    )
    d = compute_decision(s)
    assert d.desired_amps == 0
    assert d.write_action is WriteAction.TURN_OFF


def test_solar_at_target_sub_min_leftover_stops(base_snapshot: Snapshot) -> None:
    """At target, leftover < MIN worth → 0 (not MIN)."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-500.0,  # leftover ~ 500W → 2A
        ev_consumption_w=0.0,
        ev_soc=80.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 0


def test_solar_leftover_includes_current_ev_draw(base_snapshot: Snapshot) -> None:
    """leftover_w = -net_grid + ev_consumption. EV pulling 2300W, net_grid 0 → leftover 2300."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=0.0,
        ev_consumption_w=2300.0,
        ev_soc=60.0,
        target_day_soc=80.0,
        last_desired_amps=10,
    )
    d = compute_decision(s)
    assert d.leftover_w == 2300.0
    assert d.desired_amps == 10  # no change


def test_solar_clamps_to_max_amps(base_snapshot: Snapshot) -> None:
    """Huge solar surplus shouldn't push amps past MAX."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-8000.0,  # 8000W surplus → 35A unclamped
        ev_consumption_w=0.0,
        ev_soc=60.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 14


def test_solar_ceil_rounds_up_partial_amp(base_snapshot: Snapshot) -> None:
    """Partial-amp surplus must round UP (ceil), not nearest, so solar is fully absorbed.

    leftover = 1151 W → 5.004 A. round() would give 5; we want 6, even though it
    pulls ~229 W from grid on this tick. The trade-off: zero solar export, in
    exchange for at most ~VOLTAGE watts of grid import per tick.
    """
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-1151.0,
        ev_consumption_w=0.0,
        ev_soc=60.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    assert d.desired_amps == 6, "expected ceil(5.004) = 6, got round behavior"


def test_negative_ev_consumption_treated_as_zero(base_snapshot: Snapshot) -> None:
    """Negative EV consumption (bad sensor) should be ignored, not amplify leftover."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=-2300.0,
        ev_consumption_w=-500.0,  # nonsense
        ev_soc=60.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    # leftover should be -(-2300) + 0 = 2300 (NOT 2800)
    assert d.leftover_w == 2300.0
    assert d.desired_amps == 10


def test_implausible_ev_consumption_treated_as_zero(base_snapshot: Snapshot) -> None:
    """EV consumption > 20kW (sensor glitch) ignored."""
    s = dataclasses.replace(
        base_snapshot,
        net_grid_w=0.0,
        ev_consumption_w=50_000.0,  # impossible
        ev_soc=60.0,
        target_day_soc=80.0,
    )
    d = compute_decision(s)
    # Treated as 0 → leftover = -0 + 0 = 0 → MIN_AMPS below target
    assert d.leftover_w == 0.0
    assert d.desired_amps == 5


def test_safety_fallback_decision() -> None:
    d = safety_fallback_decision(reason="grid_export sensor stale 6 min", last_desired_amps=10)
    assert d.desired_amps == 6
    assert d.sub_mode is SubMode.SAFETY_FALLBACK
    assert d.write_action is WriteAction.SET_AMPS
    assert "stale" in d.reason


def test_safety_fallback_decision_no_change() -> None:
    d = safety_fallback_decision(reason="sensor", last_desired_amps=6)
    assert d.write_action is WriteAction.NONE


def test_safety_fallback_decision_from_off() -> None:
    d = safety_fallback_decision(reason="sensor", last_desired_amps=0)
    assert d.write_action is WriteAction.TURN_ON_AND_SET
