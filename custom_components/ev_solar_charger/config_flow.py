"""Config flow for EV Solar Charger."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_CHARGE_CURRENT_NUMBER,
    CONF_EV_CHARGE_SWITCH,
    CONF_EV_CONSUMPTION_SENSOR,
    CONF_EV_HOME_ZONE,
    CONF_EV_LOCATION_TRACKER,
    CONF_EV_SOC_SENSOR,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_NET_GRID_SENSOR,
    CONF_SOLAR_PRODUCTION_SENSOR,
    DOMAIN,
)


def _schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_NET_GRID_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_GRID_IMPORT_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_GRID_EXPORT_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_EV_CONSUMPTION_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_EV_CHARGE_CURRENT_NUMBER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="number")
            ),
            vol.Required(CONF_EV_CHARGE_SWITCH): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_EV_CABLE_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Required(CONF_EV_SOC_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_EV_LOCATION_TRACKER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker")
            ),
            vol.Required(CONF_EV_HOME_ZONE, default="home"): str,
            vol.Optional(CONF_SOLAR_PRODUCTION_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }
    )


def _read_float(hass: HomeAssistant, eid: str | None) -> float | None:
    if not eid:
        return None
    state = hass.states.get(eid)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            net = user_input.get(CONF_NET_GRID_SENSOR)
            imp = user_input.get(CONF_GRID_IMPORT_SENSOR)
            exp = user_input.get(CONF_GRID_EXPORT_SENSOR)

            if not net and (not imp or not exp):
                errors["base"] = "missing_grid_signal"
            elif imp and exp:
                imp_v = _read_float(self.hass, imp)
                exp_v = _read_float(self.hass, exp)
                if imp_v is not None and exp_v is not None and imp_v > 0 and exp_v > 0:
                    errors["base"] = "mutual_exclusivity_failed"

            solar = user_input.get(CONF_SOLAR_PRODUCTION_SENSOR)
            if not errors and solar:
                solar_v = _read_float(self.hass, solar)
                if solar_v is not None and solar_v < 0:
                    errors["base"] = "negative_solar"

            # EV draw plausibility: only validate when the EV is actively drawing
            # (>100W) at a non-zero amp setting. If it's idle, we can't tell from
            # the snapshot whether a 0W reading means "not charging" or "wrong
            # sensor selected", so we skip the check.
            if not errors:
                ev_v = _read_float(self.hass, user_input[CONF_EV_CONSUMPTION_SENSOR])
                amps_v = _read_float(self.hass, user_input[CONF_EV_CHARGE_CURRENT_NUMBER])
                if (
                    ev_v is not None
                    and amps_v is not None
                    and ev_v > 100
                    and amps_v > 0
                ):
                    expected_w = amps_v * 230  # nominal voltage
                    if abs(ev_v - expected_w) > 300:
                        errors["base"] = "ev_draw_implausible"

            if not errors:
                return self.async_create_entry(title="EV Solar Charger", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)
