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
