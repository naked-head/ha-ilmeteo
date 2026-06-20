# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-06-20
### Added
- True real-time current conditions, sourced from iLMeteo's `real1` box
  (an actual current-hour reading) instead of approximating from the
  nearest 3-hourly forecast slot. Eliminates the "jumps forward after each
  3-hour mark" behavior entirely, not just mitigates it.
- Daily forecast min/max now sourced from iLMeteo's official `day1` daily
  summary box (their own model aggregate across the full day) instead of
  being derived from 5 sparse 3-hourly samples. Verified to match the
  public site's forecast strip exactly across a 6-day window.
- `precipitation_probability` field on the daily forecast (previously
  unavailable).
- Unit tests for both new parsers, including a regression test for a
  nested-markup parsing bug found during development (a precipitation-cell
  mini-table was throwing off cell-index counting and, separately, its own
  inline `width="100%"` style was being misread as the data value).
### Changed
- `weather.py`: removed the "closest forecast slot" matching logic for
  current conditions entirely — no longer needed now that real-time data
  is available directly.
### Removed
- The two daily-low and current-conditions approximation caveats from the
  README — both underlying limitations are now fully resolved rather than
  documented as known issues.

## [0.3.4] - 2026-06-20
### Fixed
- Timezone bug in the weather entity: forecast slot timestamps were computed
  with `dt_util.as_local()` on naive datetimes that already represented local
  Italian time. `as_local()` treats naive input as UTC and converts it,
  silently shifting every parsed time by the local UTC offset (+2h in CEST).
  This caused the "current conditions" to display the wrong 3-hour slot
  (e.g. showing the 14:00 reading instead of 11:00 when queried mid-morning).
  Fixed by attaching local tzinfo directly instead of converting from UTC.

## [0.3.3] - 2026-06-19
### Fixed
- README: replaced relative image and link paths with absolute URLs. HACS
  does not resolve relative paths in rendered READMEs and strips the `src`/
  `href` attribute entirely (see hacs/integration#4787, unfixed upstream).
  This affected the logo, the License badge, the CHANGELOG link, and the
  demo screenshot.
### Added
- README: HACS direct-install button (`my.home-assistant.io` badge).
- README: demo screenshot of the weather card in the Home Assistant UI.

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

[Unreleased]: https://github.com/naked-head/ha-ilmeteo/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.4...v0.4.0
[0.3.4]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/naked-head/ha-ilmeteo/releases/tag/v0.1.0
