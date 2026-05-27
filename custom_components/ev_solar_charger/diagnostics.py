"""Diagnostics support for EV Solar Charger."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EVSolarChargerCoordinator

TO_REDACT_OPT: set[str] = set()  # nothing sensitive by default


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    coord: EVSolarChargerCoordinator = hass.data[DOMAIN][entry.entry_id]
    last = coord.data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT_OPT),
        "options": dict(entry.options),
        "last_decision": (
            {
                "desired_amps": last.desired_amps,
                "write_action": last.write_action.value,
                "sub_mode": last.sub_mode.value,
                "reason": last.reason,
                "leftover_w": last.leftover_w,
            }
            if last is not None
            else None
        ),
        "last_desired_amps": coord._last_desired_amps,
        "last_update_success": coord.last_update_success,
    }
