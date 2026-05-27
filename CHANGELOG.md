# Changelog

## [0.1.2] - 2026-05-27

### Changed
- `MAX_AMPS` lowered from 16 to 14 to fit single-phase 14 A residential circuits. (Hardware-specific; making this configurable per install is on the v0.1.3 follow-up list.)

## [0.1.1] - 2026-05-27

### Fixed
- Service-call failures (e.g. Tesla rejecting a redundant `switch.turn_on` because the car is already charging) are now logged at WARNING and tolerated instead of crashing the coordinator and putting the integration into setup_retry.

## [0.1.0] - 2026-05-27

### Added
- Initial release: solar/dinner/night sub-modes, two SOC targets, safety fallback.
