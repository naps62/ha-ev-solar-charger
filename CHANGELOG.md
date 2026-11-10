# Changelog

## [0.2.1] - 2026-11-10

### Fixed
- **Sunset before dinner no longer counts as night.** In winter the sun sets before the dinner window starts, and that gap fell through to night mode, charging at full rate from the grid at peak time. Afternoon hours before dinner now use solar rules whatever the sun state, which means the minimum current while below the day SOC target, or nothing once it's reached.

## [0.2.0] - 2026-11-09

### Added
- **Grid-limit guard** (options flow): pick a near-limit binary sensor and/or a grid usage sensor plus contracted power. Charging pauses while the near-limit sensor is on, and is reduced to fit under the contract minus a safety margin when a usage sensor is set. Applies in every mode, force-max included. Charging resumes only after the limit has been clear for a resume delay (default 300 s).
- `binary_sensor.ev_solar_charger_grid_limited`, and a `grid-limit` sub-mode while paused.
- Options changes reload the integration.

## [0.1.3] - 2026-05-28

### Fixed
- **Power-sensor unit handling**: the coordinator now reads the `unit_of_measurement` attribute on every configured power sensor (grid import/export, net grid, EV consumption) and converts kW to W automatically. Before this fix, a sensor reporting in kW (e.g. Tesla integration's `leomobile_charger_power`) was treated as raw watts, undercounting the value by 1000×. In practice this caused the integration to systematically under-charge from solar surplus.

### Changed
- **Solar surplus is now rounded up (ceil), not nearest (round)**, when computing the EV's charge amps from leftover_w. Trade-off: up to ~VOLTAGE watts of grid import per tick in exchange for zero solar export to grid. Goal is to maximize PV self-consumption.

## [0.1.2] - 2026-05-27

### Changed
- `MAX_AMPS` lowered from 16 to 14 to fit single-phase 14 A residential circuits. (Hardware-specific; making this configurable per install is on the v0.1.3 follow-up list.)

## [0.1.1] - 2026-05-27

### Fixed
- Service-call failures (e.g. Tesla rejecting a redundant `switch.turn_on` because the car is already charging) are now logged at WARNING and tolerated instead of crashing the coordinator and putting the integration into setup_retry.

## [0.1.0] - 2026-05-27

### Added
- Initial release: solar/dinner/night sub-modes, two SOC targets, safety fallback.
