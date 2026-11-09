"""Tests for the grid-limit pause/cap."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ev_solar_charger.algorithm import (
    Decision,
    GridLimiter,
    Mode,
    SubMode,
    WriteAction,
    apply_grid_cap,
    grid_cap_amps,
)
from custom_components.ev_solar_charger.const import (
    CONF_EV_CABLE_SENSOR,
    CONF_EV_CHARGE_CURRENT_NUMBER,
    CONF_EV_CHARGE_SWITCH,
    CONF_EV_CONSUMPTION_SENSOR,
    CONF_EV_LOCATION_TRACKER,
    CONF_EV_SOC_SENSOR,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_GRID_LIMIT_ENTITY,
    CONF_GRID_NEAR_LIMIT_SENSOR,
    CONF_GRID_RESUME_DELAY_SECONDS,
    CONF_GRID_USAGE_SENSOR,
    DOMAIN,
)
from custom_components.ev_solar_charger.coordinator import EVSolarChargerCoordinator

T0 = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)


def _decision(amps: int, sub_mode: SubMode = SubMode.FORCE_MAX) -> Decision:
    return Decision(
        desired_amps=amps,
        write_action=WriteAction.NONE,
        sub_mode=sub_mode,
        reason=f"{sub_mode.value}: {amps}A",
        leftover_w=None,
    )


# --- grid_cap_amps ---


def test_near_limit_pauses() -> None:
    cap = grid_cap_amps(
        near_limit=True, usage_w=None, limit_w=None, margin_w=500, ev_consumption_w=0
    )
    assert cap == 0


def test_no_inputs_means_no_cap() -> None:
    cap = grid_cap_amps(
        near_limit=False, usage_w=None, limit_w=None, margin_w=500, ev_consumption_w=0
    )
    assert cap is None


def test_usage_caps_to_remaining_headroom() -> None:
    # House without EV: 5000 - 2300 = 2700 W. Room: 6900 - 500 - 2700 = 3700 W → 16 A.
    # That is above MAX_AMPS, so no cap.
    assert (
        grid_cap_amps(
            near_limit=False, usage_w=5000, limit_w=6900, margin_w=500, ev_consumption_w=2300
        )
        is None
    )
    # House without EV: 6500 - 3220 = 3280 W. Room: 6400 - 3280 = 3120 W → 13 A.
    assert (
        grid_cap_amps(
            near_limit=False, usage_w=6500, limit_w=6900, margin_w=500, ev_consumption_w=3220
        )
        == 13
    )


def test_usage_pauses_when_min_amps_does_not_fit() -> None:
    # House without EV: 6000 W. Room: 400 W → 1 A, below MIN_AMPS.
    assert (
        grid_cap_amps(
            near_limit=False, usage_w=6000, limit_w=6900, margin_w=500, ev_consumption_w=0
        )
        == 0
    )


# --- apply_grid_cap ---


def test_pause_overrides_force_max() -> None:
    d = apply_grid_cap(_decision(14), 0, last_desired_amps=14)
    assert d.desired_amps == 0
    assert d.write_action is WriteAction.TURN_OFF
    assert d.sub_mode is SubMode.GRID_LIMIT
    assert d.grid_cap_amps == 0
    assert "force-max" in d.reason


def test_cap_keeps_sub_mode() -> None:
    d = apply_grid_cap(_decision(14, SubMode.NIGHT), 9, last_desired_amps=14)
    assert d.desired_amps == 9
    assert d.write_action is WriteAction.SET_AMPS
    assert d.sub_mode is SubMode.NIGHT
    assert d.grid_cap_amps == 9


def test_cap_above_desired_is_noop() -> None:
    original = _decision(6, SubMode.DINNER)
    assert apply_grid_cap(original, 9, last_desired_amps=6) is original


def test_gate_closed_is_untouched() -> None:
    original = Decision(None, WriteAction.NONE, SubMode.DISABLED, "cable off", None)
    assert apply_grid_cap(original, 0, last_desired_amps=None) is original


# --- GridLimiter ---


def test_limiter_holds_pause_for_resume_delay() -> None:
    lim = GridLimiter(resume_delay=timedelta(seconds=300))
    assert lim.update(T0, 0) == 0
    # Clears, but stays paused until 300 s of continuous clear.
    assert lim.update(T0 + timedelta(seconds=60), None) == 0
    assert lim.update(T0 + timedelta(seconds=300), None) == 0
    assert lim.update(T0 + timedelta(seconds=360), None) is None


def test_limiter_restarts_delay_when_limit_returns() -> None:
    lim = GridLimiter(resume_delay=timedelta(seconds=300))
    lim.update(T0, 0)
    lim.update(T0 + timedelta(seconds=60), None)
    lim.update(T0 + timedelta(seconds=200), 0)  # flaps back on
    assert lim.update(T0 + timedelta(seconds=400), None) == 0
    assert lim.update(T0 + timedelta(seconds=700), None) is None


def test_limiter_tightens_immediately_and_loosens_after_delay() -> None:
    lim = GridLimiter(resume_delay=timedelta(seconds=300))
    assert lim.update(T0, 10) == 10
    assert lim.update(T0 + timedelta(seconds=10), 7) == 7
    assert lim.update(T0 + timedelta(seconds=20), 12) == 7
    assert lim.update(T0 + timedelta(seconds=320), 12) == 12


# --- coordinator ---


ENTRY_DATA = {
    CONF_GRID_IMPORT_SENSOR: "sensor.grid_import",
    CONF_GRID_EXPORT_SENSOR: "sensor.grid_export",
    CONF_EV_CONSUMPTION_SENSOR: "sensor.ev_consumption",
    CONF_EV_SOC_SENSOR: "sensor.ev_soc",
    CONF_EV_CABLE_SENSOR: "binary_sensor.ev_cable",
    CONF_EV_LOCATION_TRACKER: "device_tracker.ev",
    CONF_EV_CHARGE_CURRENT_NUMBER: "number.ev_charge_current",
    CONF_EV_CHARGE_SWITCH: "switch.ev_charge",
}


def _set_ev_states(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.grid_import", "6800")
    hass.states.async_set("sensor.grid_export", "0")
    hass.states.async_set("sensor.ev_consumption", "3220")
    hass.states.async_set("sensor.ev_soc", "60")
    hass.states.async_set("binary_sensor.ev_cable", "on")
    hass.states.async_set("device_tracker.ev", "home")
    hass.states.async_set("sun.sun", "below_horizon")


@pytest.mark.asyncio
async def test_coordinator_pauses_force_max_and_resumes(hass: HomeAssistant) -> None:
    _set_ev_states(hass)
    hass.states.async_set("binary_sensor.grid_near_limit", "on")
    coord = EVSolarChargerCoordinator(
        hass=hass,
        entry_data=ENTRY_DATA,
        options={
            CONF_GRID_NEAR_LIMIT_SENSOR: "binary_sensor.grid_near_limit",
            CONF_GRID_RESUME_DELAY_SECONDS: 300,
        },
    )
    coord._last_desired_amps = 14
    coord._read_user_controls = lambda: (
        Mode.FORCE_MAX, True, 80.0, 80.0, time(16, 0), time(22, 0)
    )

    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        paused = await coord._async_update_data()
        assert paused is not None
        assert paused.sub_mode is SubMode.GRID_LIMIT
        mock_call.assert_called_once_with(
            "switch", "turn_off", {"entity_id": "switch.ev_charge"}, blocking=True
        )

        # Limit clears: still paused within the resume delay.
        hass.states.async_set("binary_sensor.grid_near_limit", "off")
        held = await coord._async_update_data()
        assert held is not None
        assert held.desired_amps == 0
        assert held.write_action is WriteAction.NONE

        # After the delay, force-max resumes.
        coord.grid_limiter._eased_since = dt_util.now() - timedelta(hours=1)
        mock_call.reset_mock()
        resumed = await coord._async_update_data()
        assert resumed is not None
        assert resumed.sub_mode is SubMode.FORCE_MAX
        assert resumed.write_action is WriteAction.TURN_ON_AND_SET
        assert resumed.grid_cap_amps is None


@pytest.mark.asyncio
async def test_coordinator_caps_from_usage_and_limit_entity(hass: HomeAssistant) -> None:
    _set_ev_states(hass)
    hass.states.async_set("sensor.grid_power", "6500", {"unit_of_measurement": "W"})
    hass.states.async_set("input_number.contracted_power", "6900")
    coord = EVSolarChargerCoordinator(
        hass=hass,
        entry_data=ENTRY_DATA,
        options={
            CONF_GRID_USAGE_SENSOR: "sensor.grid_power",
            CONF_GRID_LIMIT_ENTITY: "input_number.contracted_power",
        },
    )
    coord._last_desired_amps = 14
    coord._read_user_controls = lambda: (
        Mode.FORCE_MAX, True, 80.0, 80.0, time(16, 0), time(22, 0)
    )

    assert coord.grid_refresh_needed() is True
    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        result = await coord._async_update_data()
    assert result is not None
    assert result.desired_amps == 13
    assert result.sub_mode is SubMode.FORCE_MAX
    assert result.grid_cap_amps == 13


@pytest.mark.asyncio
async def test_unavailable_near_limit_sensor_does_not_pause(hass: HomeAssistant) -> None:
    _set_ev_states(hass)
    hass.states.async_set("binary_sensor.grid_near_limit", "unavailable")
    coord = EVSolarChargerCoordinator(
        hass=hass,
        entry_data=ENTRY_DATA,
        options={CONF_GRID_NEAR_LIMIT_SENSOR: "binary_sensor.grid_near_limit"},
    )
    coord._read_user_controls = lambda: (
        Mode.FORCE_MAX, True, 80.0, 80.0, time(16, 0), time(22, 0)
    )
    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        result = await coord._async_update_data()
    assert result is not None
    assert result.sub_mode is SubMode.FORCE_MAX


@pytest.mark.asyncio
async def test_pause_applies_while_holding_for_bad_sensor(hass: HomeAssistant) -> None:
    _set_ev_states(hass)
    hass.states.async_set("sensor.ev_soc", "unavailable")
    hass.states.async_set("binary_sensor.grid_near_limit", "on")
    coord = EVSolarChargerCoordinator(
        hass=hass,
        entry_data=ENTRY_DATA,
        options={CONF_GRID_NEAR_LIMIT_SENSOR: "binary_sensor.grid_near_limit"},
    )
    coord._last_desired_amps = 14
    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        result = await coord._async_update_data()
    assert result is not None
    assert result.sub_mode is SubMode.GRID_LIMIT
    assert coord._last_desired_amps == 0


# --- options flow ---


@pytest.mark.asyncio
async def test_options_flow_saves_grid_inputs(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRID_NEAR_LIMIT_SENSOR: "binary_sensor.grid_near_limit"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_GRID_NEAR_LIMIT_SENSOR] == "binary_sensor.grid_near_limit"


@pytest.mark.asyncio
async def test_options_flow_usage_needs_limit(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRID_USAGE_SENSOR: "sensor.grid_power"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "missing_grid_limit"


@pytest.mark.asyncio
async def test_setup_entry_with_grid_options(hass: HomeAssistant) -> None:
    """The integration loads with grid options and exposes the grid-limited sensor."""
    _set_ev_states(hass)
    hass.states.async_set("binary_sensor.grid_near_limit", "on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options={CONF_GRID_NEAR_LIMIT_SENSOR: "binary_sensor.grid_near_limit"},
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    limited = [
        s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("grid_limited")
    ]
    assert len(limited) == 1
    assert limited[0].state == "on"
    assert limited[0].attributes["paused"] is True
