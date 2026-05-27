"""Tests for the EV Solar Charger coordinator."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ev_solar_charger.const import DEFAULT_TICK_SECONDS, DOMAIN
from custom_components.ev_solar_charger.coordinator import EVSolarChargerCoordinator


@pytest.mark.asyncio
async def test_coordinator_constructs(hass: HomeAssistant) -> None:
    """Coordinator should construct with the expected interval."""
    coord = EVSolarChargerCoordinator(hass=hass, entry_data={}, options={})
    assert coord.update_interval is not None
    assert coord.update_interval.total_seconds() == DEFAULT_TICK_SECONDS
    assert coord.name == DOMAIN
