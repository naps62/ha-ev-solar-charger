"""Time entities: dinner_start and night_start window boundaries."""

from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_DINNER_START, DEFAULT_NIGHT_START, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            EVSolarTimeEntity(entry.entry_id, "dinner_start", "Dinner start", DEFAULT_DINNER_START),
            EVSolarTimeEntity(entry.entry_id, "night_start", "Night start", DEFAULT_NIGHT_START),
        ]
    )


class EVSolarTimeEntity(TimeEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, entry_id: str, suffix: str, name: str, default: str) -> None:
        self._attr_unique_id = f"{entry_id}_{suffix}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )
        h, m, s = (int(x) for x in default.split(":"))
        self._value = dt_time(h, m, s)

    @property
    def native_value(self) -> dt_time:
        return self._value

    async def async_set_value(self, value: dt_time) -> None:
        self._value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable"):
            try:
                h, m, s = (int(x) for x in last.state.split(":"))
                self._value = dt_time(h, m, s)
            except ValueError:
                pass
