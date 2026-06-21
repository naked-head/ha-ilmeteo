# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.1] - 2026-06-21
### Fixed
- Entity IDs were not actually location-independent (`weather.ilmeteo_it_roma_ilmeteo_site_2` instead of `weather.ilmeteo_site_2`); fixed by setting `entity_id` directly.
- Reconfigure now also updates the config entry title, not just the device name.
### Added
- Sensor selection is now offered during initial setup, not only via Options.
- Custom display name, editable at creation and any time via Options.
- 3 more optional sensors: wind direction, daily min/max temperature. 7 total.
### Changed
- Reconfigure resets the display name to the new municipality (editable again via Options).

## [0.6.0] - 2026-06-21
### Added
- Optional dedicated sensors (temperature, humidity, precipitation probability, wind speed) via Options flow. Off by default.
- Reconfigure flow: change tracked municipality without recreating the integration.
### Changed
- Entity identifiers decoupled from location: `unique_id` tied to the config entry, entity IDs generic and sequential (`weather.ilmeteo_site_1`, ...), never reused. Display name still tracks location.
- Deselecting a sensor deletes it and its history.
### Notes
- From-scratch redesign of entity identity; no migration path from pre-0.6.0 IDs.

## [0.5.1] - 2026-06-20
### Added
- Diagnostics platform: download button exporting tracked location, last update status, and cached box data.

## [0.5.0] - 2026-06-20
### Added
- CI workflow running the test suite on every push/PR (Python 3.12/3.13).
- Home Assistant Repair issues for genuine box parsing failures, auto-clearing on recovery.
### Changed
- Each box (real1/day1/tri1) fetched and parsed independently; a failure on one falls back to last-known-good data instead of failing the whole update.
- `async_unload_entry` clears open Repair issues on removal.

## [0.4.1] - 2026-06-20
### Fixed
- `parse_real1` rewritten against genuine HTML: styled `<b>` tag, HTML entities, unrelated `<a>` link.
### Changed
- Day/night handling now uses real1's own sprite code instead of a fixed hour range.
### Added
- Regression tests for the issues above.

## [0.4.0] - 2026-06-20
### Added
- True real-time current conditions from the `real1` box.
- Daily min/max sourced from the official `day1` box instead of derived from hourly samples.
- `precipitation_probability` field on the daily forecast.
- Unit tests for both new parsers.
### Changed
- Removed the "closest forecast slot" matching logic for current conditions.
### Removed
- Daily-low and current-conditions approximation caveats from the README (now fully resolved).

## [0.3.4] - 2026-06-20
### Fixed
- Timezone bug: `dt_util.as_local()` on naive local datetimes shifted forecast slot times by the UTC offset. Fixed by attaching local tzinfo directly.

## [0.3.3] - 2026-06-19
### Fixed
- README: relative image/link paths replaced with absolute URLs (HACS does not resolve relative paths).
### Added
- README: HACS direct-install button, demo screenshot.

## [0.3.2] - 2026-06-19
### Changed
- Extended entity attribution to "Dati meteo forniti da iLMeteo.it (www.ilmeteo.it)".

## [0.3.1] - 2026-06-19
### Changed
- Device name extended to `iLMeteo.it <location>`.
### Added
- Official iLMeteo.it logo as integration icon and in the README.

## [0.3.0] - 2026-06-19
### Added
- Cascading location selection: region → province → municipality.
- Bundled dataset of 8,218 Italian municipalities (~67 KB compressed).
- Dataset regeneration script.
- Unit tests for the location dataset.

## [0.2.0] - 2026-06-19
### Changed
- Backend rewrite: from REST client (enterprise-only API) to public box widget scraping.
### Added
- Daily and hourly (3-hourly) forecasts.
- Automatic day/night condition handling.
- Regex-based HTML parser with unit tests.

## [0.1.0] - 2026-06-12
### Added
- Initial draft based on the official iLMeteo REST API (later abandoned, enterprise-only).

[Unreleased]: https://github.com/naked-head/ha-ilmeteo/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.4...v0.4.0
[0.3.4]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/naked-head/ha-ilmeteo/releases/tag/v0.1.0
