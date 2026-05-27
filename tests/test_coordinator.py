"""Tests for the EV Solar Charger coordinator."""

from __future__ import annotations

from datetime import time
from datetime import timedelta as _td
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.ev_solar_charger.algorithm import (
    Decision,
    Mode,
    SubMode,
    SunState,
    WriteAction,
)
from custom_components.ev_solar_charger.const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_CHARGE_CURRENT_NUMBER,
    CONF_EV_CHARGE_SWITCH,
    CONF_EV_CONSUMPTION_SENSOR,
    CONF_EV_LOCATION_TRACKER,
    CONF_EV_SOC_SENSOR,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    DEFAULT_TICK_SECONDS,
    DOMAIN,
)
from custom_components.ev_solar_charger.coordinator import EVSolarChargerCoordinator


@pytest.mark.asyncio
async def test_coordinator_constructs(hass: HomeAssistant) -> None:
    """Coordinator should construct with the expected interval."""
    coord = EVSolarChargerCoordinator(hass=hass, entry_data={}, options={})
    assert coord.update_interval is not None
    assert coord.update_interval.total_seconds() == DEFAULT_TICK_SECONDS
    assert coord.name == DOMAIN


@pytest.mark.asyncio
async def test_coordinator_reads_snapshot(hass: HomeAssistant) -> None:
    """Coordinator should assemble a Snapshot from HA state."""
    hass.states.async_set("sensor.grid_import", "100", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.grid_export", "1500", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.ev_consumption", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.ev_soc", "60", {"unit_of_measurement": "%"})
    hass.states.async_set("binary_sensor.ev_cable", "on")
    hass.states.async_set("device_tracker.ev", "home")
    hass.states.async_set("sun.sun", "above_horizon")

    entry_data = {
        CONF_GRID_IMPORT_SENSOR: "sensor.grid_import",
        CONF_GRID_EXPORT_SENSOR: "sensor.grid_export",
        CONF_EV_CONSUMPTION_SENSOR: "sensor.ev_consumption",
        CONF_EV_SOC_SENSOR: "sensor.ev_soc",
        CONF_EV_CABLE_SENSOR: "binary_sensor.ev_cable",
        CONF_EV_LOCATION_TRACKER: "device_tracker.ev",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    snapshot = await coord._build_snapshot(
        mode=Mode.AUTO,
        enabled=True,
        target_day_soc=80.0,
        target_night_soc=80.0,
        dinner_start=time(16, 0),
        night_start=time(22, 0),
    )

    assert snapshot.net_grid_w == -1400.0  # 100 import - 1500 export
    assert snapshot.ev_consumption_w == 0.0
    assert snapshot.ev_soc == 60.0
    assert snapshot.cable_connected is True
    assert snapshot.at_home is True
    assert snapshot.sun_state is SunState.ABOVE


@pytest.mark.asyncio
async def test_apply_set_amps(hass: HomeAssistant) -> None:
    entry_data = {
        CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
        CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        decision = Decision(
            desired_amps=10,
            write_action=WriteAction.SET_AMPS,
            sub_mode=SubMode.SOLAR,
            reason="solar",
            leftover_w=2300.0,
        )
        await coord._apply_decision(decision)
        mock_call.assert_called_once_with(
            "number",
            "set_value",
            {"entity_id": "number.ev_charge_current", "value": 10},
            blocking=True,
        )
    assert coord._last_desired_amps == 10


@pytest.mark.asyncio
async def test_apply_turn_off(hass: HomeAssistant) -> None:
    entry_data = {
        CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
        CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    coord._last_desired_amps = 10
    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        decision = Decision(
            desired_amps=0,
            write_action=WriteAction.TURN_OFF,
            sub_mode=SubMode.NIGHT,
            reason="at target",
            leftover_w=None,
        )
        await coord._apply_decision(decision)
        mock_call.assert_called_once_with(
            "switch",
            "turn_off",
            {"entity_id": "switch.ev_charge"},
            blocking=True,
        )
    assert coord._last_desired_amps == 0


@pytest.mark.asyncio
async def test_apply_turn_on_and_set(hass: HomeAssistant) -> None:
    entry_data = {
        CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
        CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        decision = Decision(
            desired_amps=10,
            write_action=WriteAction.TURN_ON_AND_SET,
            sub_mode=SubMode.SOLAR,
            reason="cable just plugged",
            leftover_w=2300.0,
        )
        await coord._apply_decision(decision)
        assert mock_call.call_count == 2
        # first call: switch.turn_on
        assert mock_call.call_args_list[0].args[:2] == ("switch", "turn_on")
        # second call: number.set_value
        assert mock_call.call_args_list[1].args[:2] == ("number", "set_value")
    assert coord._last_desired_amps == 10


@pytest.mark.asyncio
async def test_apply_none_makes_no_calls(hass: HomeAssistant) -> None:
    coord = EVSolarChargerCoordinator(hass=hass, entry_data={}, options={})
    coord._last_desired_amps = 10
    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        decision = Decision(
            desired_amps=10,
            write_action=WriteAction.NONE,
            sub_mode=SubMode.SOLAR,
            reason="no change",
            leftover_w=2300.0,
        )
        await coord._apply_decision(decision)
        mock_call.assert_not_called()
    # last_desired_amps stays as before
    assert coord._last_desired_amps == 10


@pytest.mark.asyncio
async def test_gate_failure_resets_state(hass: HomeAssistant) -> None:
    """When the gate fails (cable off), last_desired_amps must reset to None."""
    hass.states.async_set("sensor.grid_import", "0")
    hass.states.async_set("sensor.grid_export", "0")
    hass.states.async_set("sensor.ev_consumption", "0")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("binary_sensor.ev_cable", "off")  # cable disconnected
    hass.states.async_set("device_tracker.ev", "home")
    hass.states.async_set("sun.sun", "above_horizon")

    entry_data = {
        CONF_GRID_IMPORT_SENSOR: "sensor.grid_import",
        CONF_GRID_EXPORT_SENSOR: "sensor.grid_export",
        CONF_EV_CONSUMPTION_SENSOR: "sensor.ev_consumption",
        CONF_EV_SOC_SENSOR: "sensor.ev_soc",
        CONF_EV_CABLE_SENSOR: "binary_sensor.ev_cable",
        CONF_EV_LOCATION_TRACKER: "device_tracker.ev",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    coord._last_desired_amps = 10  # previously charging

    # Stub user-control reads (those land in a later task)
    coord._read_user_controls = lambda: (Mode.AUTO, True, 80.0, 80.0, time(16, 0), time(22, 0))

    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        result = await coord._async_update_data()

    assert coord._last_desired_amps is None
    assert result is not None
    assert result.sub_mode is SubMode.DISABLED


@pytest.mark.asyncio
async def test_safety_fallback_on_stale_sensor(hass: HomeAssistant) -> None:
    """If a required sensor has been unavailable for >5 min, force 6A."""
    # Grid import is missing (unavailable for > threshold)
    hass.states.async_set("sensor.grid_import", "unavailable")
    hass.states.async_set("sensor.grid_export", "0")
    hass.states.async_set("sensor.ev_consumption", "0")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("binary_sensor.ev_cable", "on")
    hass.states.async_set("device_tracker.ev", "home")
    hass.states.async_set("sun.sun", "above_horizon")

    entry_data = {
        CONF_GRID_IMPORT_SENSOR: "sensor.grid_import",
        CONF_GRID_EXPORT_SENSOR: "sensor.grid_export",
        CONF_EV_CONSUMPTION_SENSOR: "sensor.ev_consumption",
        CONF_EV_SOC_SENSOR: "sensor.ev_soc",
        CONF_EV_CABLE_SENSOR: "binary_sensor.ev_cable",
        CONF_EV_LOCATION_TRACKER: "device_tracker.ev",
        CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
        CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})

    # Simulate the sensor having been bad for longer than the threshold
    coord._first_bad_sensor_ts = dt_util.now() - _td(seconds=400)

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as mock_call:
        result = await coord._async_update_data()
        # Should have written 6A
        assert any(
            call.args[:2] == ("number", "set_value") and call.args[2]["value"] == 6
            for call in mock_call.call_args_list
        )
    assert result is not None
    assert result.sub_mode is SubMode.SAFETY_FALLBACK


@pytest.mark.asyncio
async def test_mode_off_does_not_oscillate(hass: HomeAssistant) -> None:
    """Mode.OFF steady-state must not flip last_desired_amps None ↔ 0.

    Regression test for the gate-reset bug: when mode=OFF and EV is already at
    0A, the algorithm returns (desired=0, write=NONE, sub_mode=DISABLED). If
    the gate-reset condition incorrectly fires here, the next tick re-issues
    switch.turn_off (because last_desired_amps was set to None, so
    _write_action_for(0, None) → TURN_OFF). That produces a redundant write
    every other tick.
    """
    hass.states.async_set("sensor.grid_import", "100")
    hass.states.async_set("sensor.grid_export", "0")
    hass.states.async_set("sensor.ev_consumption", "0")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("binary_sensor.ev_cable", "on")
    hass.states.async_set("device_tracker.ev", "home")
    hass.states.async_set("sun.sun", "above_horizon")

    entry_data = {
        CONF_GRID_IMPORT_SENSOR: "sensor.grid_import",
        CONF_GRID_EXPORT_SENSOR: "sensor.grid_export",
        CONF_EV_CONSUMPTION_SENSOR: "sensor.ev_consumption",
        CONF_EV_SOC_SENSOR: "sensor.ev_soc",
        CONF_EV_CABLE_SENSOR: "binary_sensor.ev_cable",
        CONF_EV_LOCATION_TRACKER: "device_tracker.ev",
        CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
        CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
    }
    coord = EVSolarChargerCoordinator(hass=hass, entry_data=entry_data, options={})
    coord._last_desired_amps = 0  # EV already off

    # Stub user controls: mode=OFF, enabled
    coord._read_user_controls = lambda: (
        Mode.OFF, True, 80.0, 80.0, time(16, 0), time(22, 0)
    )

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as mock_call:
        # First tick: decision should be (desired=0, write=NONE) — no calls
        result1 = await coord._async_update_data()
        assert result1 is not None
        assert result1.desired_amps == 0
        assert result1.write_action is WriteAction.NONE
        # State must NOT reset — Mode.OFF is not a gate closure
        assert coord._last_desired_amps == 0

        # Second tick: same. Still no calls.
        result2 = await coord._async_update_data()
        assert result2.write_action is WriteAction.NONE
        assert coord._last_desired_amps == 0

        # No service calls made across both ticks
        mock_call.assert_not_called()
