"""EV Solar Charger integration entry point."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_LOCATION_TRACKER,
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
