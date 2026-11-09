"""Binary sensor entities: healthy, grid limited."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .algorithm import SubMode
from .const import DOMAIN
from .coordinator import EVSolarChargerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord: EVSolarChargerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HealthySensor(coord, entry.entry_id), GridLimitedSensor(coord, entry.entry_id)]
    )


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


class GridLimitedSensor(CoordinatorEntity[EVSolarChargerCoordinator], BinarySensorEntity):
    """On while the grid limit is pausing or reducing charging."""

    _attr_has_entity_name = True
    _attr_name = "Grid limited"

    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_grid_limited"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )

    @property
    def is_on(self) -> bool:
        d = self.coordinator.data
        return d is not None and d.grid_cap_amps is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        d = self.coordinator.data
        return {
            "paused": d is not None and d.sub_mode is SubMode.GRID_LIMIT,
            "cap_amps": d.grid_cap_amps if d else None,
            "held_cap_amps": self.coordinator.grid_limiter.held_cap,
        }
