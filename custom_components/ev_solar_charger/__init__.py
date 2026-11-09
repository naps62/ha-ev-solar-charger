"""EV Solar Charger integration entry point."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_LOCATION_TRACKER,
    CONF_GRID_NEAR_LIMIT_SENSOR,
    CONF_GRID_USAGE_SENSOR,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EVSolarChargerCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = EVSolarChargerCoordinator(
        hass=hass,
        entry_data=dict(entry.data),
        options=dict(entry.options),
    )
    await coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coord

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Fast-tick event listeners
    watched = [
        eid
        for eid in (
            entry.data.get(CONF_EV_CABLE_SENSOR),
            entry.data.get(CONF_EV_LOCATION_TRACKER),
            entry.options.get(CONF_GRID_NEAR_LIMIT_SENSOR),
            f"select.{DOMAIN}_mode",
            f"switch.{DOMAIN}_enabled",
            f"time.{DOMAIN}_dinner_start",
            f"time.{DOMAIN}_night_start",
        )
        if eid
    ]

    @callback
    def _on_change(event: Event[EventStateChangedData]) -> None:
        hass.async_create_task(coord.async_request_refresh())

    entry.async_on_unload(
        async_track_state_change_event(hass, watched, _on_change)
    )

    usage_sensor = entry.options.get(CONF_GRID_USAGE_SENSOR)
    if usage_sensor:

        @callback
        def _on_usage_change(event: Event[EventStateChangedData]) -> None:
            if coord.grid_refresh_needed():
                hass.async_create_task(coord.async_request_refresh())

        entry.async_on_unload(
            async_track_state_change_event(hass, [usage_sensor], _on_usage_change)
        )

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
