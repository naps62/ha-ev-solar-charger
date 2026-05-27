"""Tests for the EV Solar Charger config flow."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ev_solar_charger.const import DOMAIN


@pytest.mark.asyncio
async def test_config_flow_happy_path(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.grid_import", "0")
    hass.states.async_set("sensor.grid_export", "100")
    hass.states.async_set("sensor.ev_consumption", "0")
    hass.states.async_set("number.ev_amps", "16")
    hass.states.async_set("switch.ev_charge", "off")
    hass.states.async_set("binary_sensor.ev_cable", "off")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("device_tracker.ev", "home")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "ev_consumption_sensor": "sensor.ev_consumption",
            "ev_charge_current_number": "number.ev_amps",
            "ev_charge_switch": "switch.ev_charge",
            "ev_cable_sensor": "binary_sensor.ev_cable",
            "ev_soc_sensor": "sensor.ev_soc",
            "ev_location_tracker": "device_tracker.ev",
            "ev_home_zone": "home",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "EV Solar Charger"


@pytest.mark.asyncio
async def test_config_flow_missing_grid_signal(hass: HomeAssistant) -> None:
    """If neither net_grid nor import+export are provided, surface an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ev_consumption_sensor": "sensor.ev_consumption",
            "ev_charge_current_number": "number.ev_amps",
            "ev_charge_switch": "switch.ev_charge",
            "ev_cable_sensor": "binary_sensor.ev_cable",
            "ev_soc_sensor": "sensor.ev_soc",
            "ev_location_tracker": "device_tracker.ev",
            "ev_home_zone": "home",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "missing_grid_signal"


@pytest.mark.asyncio
async def test_config_flow_mutual_exclusivity_warning(hass: HomeAssistant) -> None:
    """grid_import and grid_export both > 0 → error."""
    hass.states.async_set("sensor.grid_import", "200")
    hass.states.async_set("sensor.grid_export", "200")
    hass.states.async_set("sensor.ev_consumption", "0")
    hass.states.async_set("number.ev_amps", "16")
    hass.states.async_set("switch.ev_charge", "off")
    hass.states.async_set("binary_sensor.ev_cable", "off")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("device_tracker.ev", "home")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "ev_consumption_sensor": "sensor.ev_consumption",
            "ev_charge_current_number": "number.ev_amps",
            "ev_charge_switch": "switch.ev_charge",
            "ev_cable_sensor": "binary_sensor.ev_cable",
            "ev_soc_sensor": "sensor.ev_soc",
            "ev_location_tracker": "device_tracker.ev",
            "ev_home_zone": "home",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "mutual_exclusivity_failed"
