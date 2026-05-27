"""Number entities: target SOCs for day and night sub-modes."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_TARGET_DAY_SOC, DEFAULT_TARGET_NIGHT_SOC, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            EVSolarTargetSocNumber(
                entry_id=entry.entry_id,
                unique_id_suffix="target_day_soc",
                name="Target day SOC",
                default=DEFAULT_TARGET_DAY_SOC,
            ),
            EVSolarTargetSocNumber(
                entry_id=entry.entry_id,
                unique_id_suffix="target_night_soc",
                name="Target night SOC",
                default=DEFAULT_TARGET_NIGHT_SOC,
            ),
        ]
    )


class EVSolarTargetSocNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        entry_id: str,
        unique_id_suffix: str,
        name: str,
        default: float,
    ) -> None:
        self._attr_unique_id = f"{entry_id}_{unique_id_suffix}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )
        self._value = float(default)

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = float(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last.state)
            except ValueError:
                pass
