"""Select entity: top-level mode (auto / force-min / force-max / off)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .algorithm import Mode
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([EVSolarModeSelect(entry.entry_id)])


class EVSolarModeSelect(SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_options: list[str] = [m.value for m in Mode]  # noqa: RUF012

    def __init__(self, entry_id: str) -> None:
        self._attr_unique_id = f"{entry_id}_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )
        self._current = Mode.AUTO.value

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self._current = last.state
