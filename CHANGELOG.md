# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Versionamento Semantico](https://semver.org/lang/it/).

## [Unreleased]

## [0.3.2] - 2026-06-19
### Changed
- Attribution dell'entità estesa a "Dati meteo forniti da iLMeteo.it (www.ilmeteo.it)".

## [0.3.1] - 2026-06-19
### Changed
- Nome del device esteso a `iLMeteo.it <località>` (comprensivo del dominio).
### Added
- Logo ufficiale iLMeteo.it come icona dell'integrazione (`brand/`) e nel README.

## [0.3.0] - 2026-06-19
### Added
- Selezione località a cascata: regione → provincia → comune (nessun codice manuale).
- Dataset di 8.218 comuni italiani incluso, in JSON compresso (~67 KB).
- Script di rigenerazione del dataset in `scripts/build_locations.py`.
- Test unitari del dataset località.

## [0.2.0] - 2026-06-19
### Changed
- Riscrittura completa del backend: dal client REST (API enterprise-only) allo
  scraping del box previsioni pubblico e gratuito di iLMeteo.it.
### Added
- Forecast giornaliero e orario (triorario).
- Distinzione automatica giorno/notte per le condizioni meteo.
- Parser HTML basato su regex (zero dipendenze aggiuntive) con test unitari.

## [0.1.0] - 2026-06-19
### Added
- Prima bozza dell'integrazione basata sull'API REST ufficiale iLMeteo
  (successivamente abbandonata perché riservata a clienti business).

[Unreleased]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/naked-head/ha-ilmeteo/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/naked-head/ha-ilmeteo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/naked-head/ha-ilmeteo/releases/tag/v0.1.0
