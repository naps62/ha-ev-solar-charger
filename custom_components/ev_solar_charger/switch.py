"""Switch entity: master enabled."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([EVSolarEnabledSwitch(entry.entry_id)])


class EVSolarEnabledSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"

    def __init__(self, entry_id: str) -> None:
        self._attr_unique_id = f"{entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )
        self._state = True

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._state = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._state = last.state == "on"
