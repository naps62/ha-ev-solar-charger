"""DataUpdateCoordinator for the EV Solar Charger integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .algorithm import Decision
from .const import DEFAULT_TICK_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EVSolarChargerCoordinator(DataUpdateCoordinator[Decision | None]):
    """Owns the periodic decision loop and applies writes to the EV."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        self.entry_data = entry_data
        self.options = options
        self._last_desired_amps: int | None = None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_TICK_SECONDS),
        )

    async def _async_update_data(self) -> Decision | None:
        """Per-tick: read snapshot, compute decision, apply.

        Skeleton: returns None. Subsequent tasks fill this in.
        """
        return None
