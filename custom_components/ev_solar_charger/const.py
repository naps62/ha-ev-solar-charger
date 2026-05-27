"""Constants for the EV Solar Charger integration."""

from __future__ import annotations

DOMAIN = "ev_solar_charger"
PLATFORMS = ["number", "select", "switch", "time", "sensor", "binary_sensor"]

# Config flow keys
CONF_NET_GRID_SENSOR = "net_grid_sensor"
CONF_GRID_IMPORT_SENSOR = "grid_import_sensor"
CONF_GRID_EXPORT_SENSOR = "grid_export_sensor"
CONF_EV_CONSUMPTION_SENSOR = "ev_consumption_sensor"
CONF_EV_CHARGE_CURRENT_NUMBER = "ev_charge_current_number"
CONF_EV_CHARGE_SWITCH = "ev_charge_switch"
CONF_EV_CHARGING_SENSOR = "ev_charging_sensor"
CONF_EV_CABLE_SENSOR = "ev_cable_sensor"
CONF_EV_SOC_SENSOR = "ev_soc_sensor"
CONF_EV_LOCATION_TRACKER = "ev_location_tracker"
CONF_EV_HOME_ZONE = "ev_home_zone"
CONF_SOLAR_PRODUCTION_SENSOR = "solar_production_sensor"
CONF_VOLTAGE = "voltage"
CONF_MIN_AMPS = "min_amps"
CONF_MAX_AMPS = "max_amps"
CONF_TICK_SECONDS = "tick_seconds"

# Defaults
DEFAULT_VOLTAGE = 230
DEFAULT_MIN_AMPS = 5
DEFAULT_MAX_AMPS = 16
DEFAULT_TICK_SECONDS = 120
DEFAULT_DINNER_START = "16:00:00"
DEFAULT_NIGHT_START = "22:00:00"
DEFAULT_TARGET_DAY_SOC = 80
DEFAULT_TARGET_NIGHT_SOC = 80
DINNER_AMPS = 6

# Safety
STALE_SENSOR_THRESHOLD_SECONDS = 300  # 5 min
SAFETY_FALLBACK_AMPS = 6
MAX_PLAUSIBLE_EV_W = 20000
