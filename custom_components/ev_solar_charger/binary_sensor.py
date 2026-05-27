"""Binary sensor entity: healthy."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EVSolarChargerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord: EVSolarChargerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HealthySensor(coord, entry.entry_id)])


class HealthySensor(CoordinatorEntity[EVSolarChargerCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Healthy"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM  # on = problem; we invert via is_on

    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_healthy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )

    @property
    def is_on(self) -> bool:
        # Problem ON = unhealthy
        return not (self.coordinator.last_update_success and self.coordinator.data is not None)
