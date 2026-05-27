"""DataUpdateCoordinator for the EV Solar Charger integration."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .algorithm import (
    Decision,
    Mode,
    Snapshot,
    SunState,
    WriteAction,
    compute_decision,
    safety_fallback_decision,
)
from .const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_CHARGE_CURRENT_NUMBER,
    CONF_EV_CHARGE_SWITCH,
    CONF_EV_CONSUMPTION_SENSOR,
    CONF_EV_HOME_ZONE,
    CONF_EV_LOCATION_TRACKER,
    CONF_EV_SOC_SENSOR,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_NET_GRID_SENSOR,
    DEFAULT_TICK_SECONDS,
    DOMAIN,
    STALE_SENSOR_THRESHOLD_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class EVSolarChargerCoordinator(DataUpdateCoordinator[Decision | None]):
    """Owns the periodic decision loop and applies writes to the EV."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        self.entry_data = entry_data
        self.options = options
        self._last_desired_amps: int | None = None
        self._first_bad_sensor_ts: datetime | None = None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_TICK_SECONDS),
        )

    def _read_float(self, entity_id: str | None) -> float | None:
        """Read a float from a sensor; return None if unavailable/unknown/missing."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _read_bool(self, entity_id: str | None, on_state: str = "on") -> bool | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state == on_state

    def _read_at_home(self) -> bool | None:
        tracker = self.entry_data.get(CONF_EV_LOCATION_TRACKER)
        if not tracker:
            return None
        state = self.hass.states.get(tracker)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        home_zone: str = self.entry_data.get(CONF_EV_HOME_ZONE, "home")
        return state.state == home_zone

    def _read_sun_state(self) -> SunState:
        state = self.hass.states.get("sun.sun")
        if state is None or state.state != "above_horizon":
            return SunState.BELOW
        return SunState.ABOVE

    def _read_net_grid(self) -> float | None:
        """Return signed net grid power: + import, - export."""
        net = self._read_float(self.entry_data.get(CONF_NET_GRID_SENSOR))
        if net is not None:
            return net
        imp = self._read_float(self.entry_data.get(CONF_GRID_IMPORT_SENSOR))
        exp = self._read_float(self.entry_data.get(CONF_GRID_EXPORT_SENSOR))
        if imp is None or exp is None:
            return None
        return imp - exp

    async def _build_snapshot(
        self,
        *,
        mode: Mode,
        enabled: bool,
        target_day_soc: float,
        target_night_soc: float,
        dinner_start: time,
        night_start: time,
    ) -> Snapshot:
        return Snapshot(
            now=dt_util.now(),
            sun_state=self._read_sun_state(),
            net_grid_w=self._read_net_grid() or 0.0,
            ev_consumption_w=self._read_float(self.entry_data.get(CONF_EV_CONSUMPTION_SENSOR))
            or 0.0,
            ev_soc=self._read_float(self.entry_data.get(CONF_EV_SOC_SENSOR)) or 0.0,
            cable_connected=self._read_bool(self.entry_data.get(CONF_EV_CABLE_SENSOR)) or False,
            at_home=self._read_at_home() or False,
            enabled=enabled,
            mode=mode,
            target_day_soc=target_day_soc,
            target_night_soc=target_night_soc,
            dinner_start=dinner_start,
            night_start=night_start,
            last_desired_amps=self._last_desired_amps,
        )

    async def _apply_decision(self, decision: Decision) -> None:
        """Execute the decision's WriteAction against HA."""
        number_eid = self.entry_data.get(CONF_EV_CHARGE_CURRENT_NUMBER)
        switch_eid = self.entry_data.get(CONF_EV_CHARGE_SWITCH)

        if decision.write_action is WriteAction.NONE:
            return

        if decision.write_action is WriteAction.TURN_OFF and switch_eid:
            await self.hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": switch_eid},
                blocking=True,
            )

        elif decision.write_action is WriteAction.TURN_ON_AND_SET:
            if switch_eid:
                await self.hass.services.async_call(
                    "switch",
                    "turn_on",
                    {"entity_id": switch_eid},
                    blocking=True,
                )
            if number_eid and decision.desired_amps is not None:
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": number_eid, "value": decision.desired_amps},
                    blocking=True,
                )

        elif (
            decision.write_action is WriteAction.SET_AMPS
            and number_eid
            and decision.desired_amps is not None
        ):
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": number_eid, "value": decision.desired_amps},
                blocking=True,
            )

        self._last_desired_amps = decision.desired_amps

    async def _async_update_data(self) -> Decision | None:
        """Periodic tick: build snapshot, compute decision, apply."""
        mode, enabled, target_day, target_night, dinner_start, night_start = (
            self._read_user_controls()
        )

        # Check for required-sensor freshness
        bad_sensor_reason = self._check_required_sensors()
        now = dt_util.now()
        if bad_sensor_reason:
            if self._first_bad_sensor_ts is None:
                self._first_bad_sensor_ts = now
            elapsed = (now - self._first_bad_sensor_ts).total_seconds()
            if elapsed >= STALE_SENSOR_THRESHOLD_SECONDS:
                decision = safety_fallback_decision(
                    reason=bad_sensor_reason,
                    last_desired_amps=self._last_desired_amps,
                )
                await self._apply_decision(decision)
                return decision
            # Hold last-known good for now
            return None
        else:
            self._first_bad_sensor_ts = None

        snapshot = await self._build_snapshot(
            mode=mode,
            enabled=enabled,
            target_day_soc=target_day,
            target_night_soc=target_night,
            dinner_start=dinner_start,
            night_start=night_start,
        )
        decision = compute_decision(snapshot)

        # State reset on gate transitions: if the gate is closed (no-op),
        # forget last_desired_amps so the next tick after re-open writes.
        # Use desired_amps is None as the discriminator — true gate closure
        # (cable off, not home, disabled) returns None; Mode.OFF returns 0.
        if decision.desired_amps is None:  # true gate closure (cable off, not home, disabled)
            self._last_desired_amps = None
        else:
            await self._apply_decision(decision)

        return decision

    def _check_required_sensors(self) -> str | None:
        """Return a human-readable reason if any required sensor is bad, else None."""
        net = self._read_net_grid()
        if net is None:
            return "grid sensor(s) unavailable"
        if self._read_float(self.entry_data.get(CONF_EV_CONSUMPTION_SENSOR)) is None:
            return "ev consumption sensor unavailable"
        if self._read_float(self.entry_data.get(CONF_EV_SOC_SENSOR)) is None:
            return "ev soc sensor unavailable"
        return None

    def _read_user_controls(self) -> tuple[Mode, bool, float, float, time, time]:
        """Read the integration's own user-facing helper entities."""
        mode_state = self.hass.states.get(f"select.{DOMAIN}_mode")
        mode = Mode.AUTO
        if mode_state is not None and mode_state.state in {m.value for m in Mode}:
            mode = Mode(mode_state.state)

        enabled_state = self.hass.states.get(f"switch.{DOMAIN}_enabled")
        enabled = True
        if enabled_state is not None:
            enabled = enabled_state.state == "on"

        target_day = self._read_float(f"number.{DOMAIN}_target_day_soc") or 80.0
        target_night = self._read_float(f"number.{DOMAIN}_target_night_soc") or 80.0

        dinner = self._read_time(f"time.{DOMAIN}_dinner_start") or time(16, 0)
        night = self._read_time(f"time.{DOMAIN}_night_start") or time(22, 0)
        return mode, enabled, target_day, target_night, dinner, night

    def _read_time(self, entity_id: str) -> time | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            h, m, *_ = state.state.split(":")
            return time(int(h), int(m))
        except (ValueError, IndexError):
            return None
