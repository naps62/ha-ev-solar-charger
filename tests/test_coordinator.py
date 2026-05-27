"""Tests for the EV Solar Charger coordinator."""

from __future__ import annotations

from datetime import time

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ev_solar_charger.algorithm import Mode, SunState
from custom_components.ev_solar_charger.const import (
    CONF_EV_CABLE_SENSOR,
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
