"""Sensor entities: leftover, desired/actual amps, sub-mode, reason."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EV_CHARGE_CURRENT_NUMBER, DOMAIN
from .coordinator import EVSolarChargerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord: EVSolarChargerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LeftoverSensor(coord, entry.entry_id),
            DesiredAmpsSensor(coord, entry.entry_id),
            ActualAmpsSensor(coord, entry.entry_id),
            SubModeSensor(coord, entry.entry_id),
            ReasonSensor(coord, entry.entry_id),
        ]
    )


class _BaseSensor(CoordinatorEntity[EVSolarChargerCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coord: EVSolarChargerCoordinator, entry_id: str, suffix: str, name: str
    ) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_{suffix}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Solar Charger",
        )


class LeftoverSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord, entry_id, "leftover_w", "Leftover")

    @property
    def native_value(self) -> float | None:
        d = self.coordinator.data
        return d.leftover_w if d else None


class DesiredAmpsSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord, entry_id, "desired_amps", "Desired amps")

    @property
    def native_value(self) -> int | None:
        d = self.coordinator.data
        return d.desired_amps if d else None


class ActualAmpsSensor(_BaseSensor):
    """Reads back the EV's actual charge current from the configured number entity."""

    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord, entry_id, "actual_amps", "Actual amps")

    @property
    def native_value(self) -> float | None:
        eid = self.coordinator.entry_data.get(CONF_EV_CHARGE_CURRENT_NUMBER)
        if not eid:
            return None
        state = self.coordinator.hass.states.get(eid)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None


class SubModeSensor(_BaseSensor):
    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord, entry_id, "sub_mode", "Sub-mode")

    @property
    def native_value(self) -> str | None:
        d = self.coordinator.data
        return d.sub_mode.value if d else None


class ReasonSensor(_BaseSensor):
    def __init__(self, coord: EVSolarChargerCoordinator, entry_id: str) -> None:
        super().__init__(coord, entry_id, "reason", "Last decision reason")

    @property
    def native_value(self) -> str | None:
        d = self.coordinator.data
        return d.reason if d else None
