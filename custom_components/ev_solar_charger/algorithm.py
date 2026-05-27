"""Pure decision algorithm for the EV Solar Charger integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum


class Mode(Enum):
    """User-selected top-level mode."""

    AUTO = "auto"
    FORCE_MIN = "force-min"
    FORCE_MAX = "force-max"
    OFF = "off"


class SubMode(Enum):
    """Resolved sub-mode for diagnostics and dashboard display."""

    SOLAR = "solar"
    DINNER = "dinner"
    NIGHT = "night"
    SAFETY_FALLBACK = "safety-fallback"
    DISABLED = "disabled"
    FORCE_MIN = "force-min"
    FORCE_MAX = "force-max"


class WriteAction(Enum):
    """What the coordinator should do this tick."""

    NONE = "none"
    TURN_OFF = "turn_off"
    TURN_ON_AND_SET = "turn_on_and_set"
    SET_AMPS = "set_amps"


class SunState(Enum):
    """Simplified sun state (above/below horizon)."""

    ABOVE = "above_horizon"
    BELOW = "below_horizon"


@dataclass(frozen=True)
class Snapshot:
    """All inputs the algorithm needs for one decision."""

    now: datetime
    sun_state: SunState
    net_grid_w: float
    ev_consumption_w: float
    ev_soc: float
    cable_connected: bool
    at_home: bool
    enabled: bool
    mode: Mode
    target_day_soc: float
    target_night_soc: float
    dinner_start: time
    night_start: time
    last_desired_amps: int | None


@dataclass(frozen=True)
class Decision:
    """The algorithm's output for one tick."""

    desired_amps: int | None
    write_action: WriteAction
    sub_mode: SubMode
    reason: str
    leftover_w: float | None


def pick_submode(
    now: datetime,
    sun_state: SunState,
    dinner_start: time,
    night_start: time,
) -> SubMode:
    """Resolve the current sub-mode from time-of-day and sun state.

    Rules:
    - dinner window (always wins when active)
    - else: solar if sun above, else night
    """
    h = now.time()
    if dinner_start <= h < night_start:
        return SubMode.DINNER
    if sun_state is SunState.ABOVE and h < dinner_start:
        return SubMode.SOLAR
    return SubMode.NIGHT


# Defaults used internally; the coordinator passes config-driven values via Snapshot
# extensions in a later task. For v0.1 these are constants.
MIN_AMPS = 5
MAX_AMPS = 16
VOLTAGE = 230
DINNER_AMPS = 6
MAX_PLAUSIBLE_EV_W = 20_000  # anything above this is sensor glitch


def _write_action_for(desired: int, last: int | None) -> WriteAction:
    """Decide which service call to make based on the change."""
    if last == desired:
        return WriteAction.NONE
    if desired == 0:
        return WriteAction.TURN_OFF
    if last in (0, None):
        return WriteAction.TURN_ON_AND_SET
    return WriteAction.SET_AMPS


def compute_decision(s: Snapshot) -> Decision:
    """Pure decision function: Snapshot -> Decision."""
    # Gate: if we shouldn't be doing anything, return no-op.
    if not s.enabled or not s.cable_connected or not s.at_home:
        reason_bits = []
        if not s.enabled:
            reason_bits.append("disabled")
        if not s.cable_connected:
            reason_bits.append("cable off")
        if not s.at_home:
            reason_bits.append("not home")
        return Decision(
            desired_amps=None,
            write_action=WriteAction.NONE,
            sub_mode=SubMode.DISABLED,
            reason=", ".join(reason_bits),
            leftover_w=None,
        )

    # User force-mode overrides
    if s.mode is Mode.OFF:
        return Decision(
            desired_amps=0,
            write_action=_write_action_for(0, s.last_desired_amps),
            sub_mode=SubMode.DISABLED,
            reason="mode=off",
            leftover_w=None,
        )
    if s.mode is Mode.FORCE_MIN:
        return Decision(
            desired_amps=MIN_AMPS,
            write_action=_write_action_for(MIN_AMPS, s.last_desired_amps),
            sub_mode=SubMode.FORCE_MIN,
            reason=f"force-min: {MIN_AMPS}A",
            leftover_w=None,
        )
    if s.mode is Mode.FORCE_MAX:
        return Decision(
            desired_amps=MAX_AMPS,
            write_action=_write_action_for(MAX_AMPS, s.last_desired_amps),
            sub_mode=SubMode.FORCE_MAX,
            reason=f"force-max: {MAX_AMPS}A",
            leftover_w=None,
        )

    # Auto mode → time-of-day sub-mode
    sub = pick_submode(s.now, s.sun_state, s.dinner_start, s.night_start)

    if sub is SubMode.DINNER:
        return Decision(
            desired_amps=DINNER_AMPS,
            write_action=_write_action_for(DINNER_AMPS, s.last_desired_amps),
            sub_mode=SubMode.DINNER,
            reason=f"dinner cap: {DINNER_AMPS}A",
            leftover_w=None,
        )

    if sub is SubMode.NIGHT:
        desired = MAX_AMPS if s.ev_soc < s.target_night_soc else 0
        return Decision(
            desired_amps=desired,
            write_action=_write_action_for(desired, s.last_desired_amps),
            sub_mode=SubMode.NIGHT,
            reason=(
                f"night: soc {s.ev_soc:.0f} < target {s.target_night_soc:.0f} → {MAX_AMPS}A"
                if desired
                else f"night: soc {s.ev_soc:.0f} ≥ target {s.target_night_soc:.0f} → off"
            ),
            leftover_w=None,
        )

    # Solar sub-mode: forward calculation from leftover.
    # Sanitize anomalous EV consumption (negative or impossibly large) before use.
    if s.ev_consumption_w < 0 or s.ev_consumption_w > MAX_PLAUSIBLE_EV_W:
        sanitized_ev_w = 0.0
    else:
        sanitized_ev_w = s.ev_consumption_w

    leftover_w = -s.net_grid_w + sanitized_ev_w
    raw_amps = round(leftover_w / VOLTAGE)

    if s.ev_soc < s.target_day_soc:
        desired = max(MIN_AMPS, raw_amps)
    else:
        desired = max(0, raw_amps)

    # Clamp to circuit max
    desired = min(MAX_AMPS, desired)

    # Snap sub-MIN positive values: MIN if below target, else 0
    if 0 < desired < MIN_AMPS:
        desired = MIN_AMPS if s.ev_soc < s.target_day_soc else 0

    return Decision(
        desired_amps=desired,
        write_action=_write_action_for(desired, s.last_desired_amps),
        sub_mode=SubMode.SOLAR,
        reason=(
            f"solar: leftover={leftover_w:+.0f}W → {desired}A "
            f"(soc {s.ev_soc:.0f}, target {s.target_day_soc:.0f})"
        ),
        leftover_w=leftover_w,
    )
