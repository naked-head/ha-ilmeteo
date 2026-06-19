# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.2] - 2026-06-19
### Changed
- Extended the entity attribution to "Dati meteo forniti da iLMeteo.it (www.ilmeteo.it)".

## [0.3.1] - 2026-06-19
### Changed
- Device name extended to `iLMeteo.it <location>` (including the domain).
### Added
- Official iLMeteo.it logo as the integration icon (`brand/`) and in the README.

## [0.3.0] - 2026-06-19
### Added
- Cascading location selection: region → province → municipality (no manual codes).
- Bundled dataset of 8,218 Italian municipalities as compressed JSON (~67 KB).
- Dataset regeneration script at `scripts/build_locations.py`.
- Unit tests for the location dataset.

## [0.2.0] - 2026-06-19
### Changed
- Complete backend rewrite: from the REST client (enterprise-only API) to
  scraping iLMeteo.it's free public forecast box widget.
### Added
- Daily and hourly (3-hourly) forecasts.
- Automatic day/night handling for weather conditions.
- Regex-based HTML parser (no extra dependencies) with unit tests.

## [0.1.0] - 2026-06-19
### Added
- Initial draft of the integration based on the official iLMeteo REST API
  (later abandoned because it is reserved for business customers).

[Unreleased]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/naked-head/ha-ilmeteo/releases/tag/v0.1.0
