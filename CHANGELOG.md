# Changelog

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
