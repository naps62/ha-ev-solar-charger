# Changelog

## [0.1.1] - 2026-05-27

### Fixed
- Service-call failures (e.g. Tesla rejecting a redundant `switch.turn_on` because the car is already charging) are now logged at WARNING and tolerated instead of crashing the coordinator and putting the integration into setup_retry.

## [0.1.0] - 2026-05-27

### Added
- Initial release: solar/dinner/night sub-modes, two SOC targets, safety fallback.
