<p align="center">
  <img src="images/logo.png" alt="iLMeteo.it" width="120">
</p>

# iLMeteo.it — Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/naked-head/ha-ilmeteo.svg)](https://github.com/naked-head/ha-ilmeteo/releases)
[![Validate](https://github.com/naked-head/ha-ilmeteo/actions/workflows/validate.yml/badge.svg)](https://github.com/naked-head/ha-ilmeteo/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/naked-head/ha-ilmeteo.svg)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) integration that exposes weather data from **[iLMeteo.it](https://www.ilmeteo.it/)** (a popular Italian weather service) as native `weather` entities, with **daily** and **hourly** (3-hourly) forecasts — just like the OpenWeatherMap or Met.no integrations.

> **How it works:** iLMeteo's official REST API is reserved for business customers. Instead, this integration uses the **free public forecast box widget** that iLMeteo provides for embedding on third-party sites (see the [business portals page](https://www.ilmeteo.it/business/portali)). The widget endpoint (`ilmeteo.it/box/previsioni.php`) is parsed server-side. No token required.

---

## ⚠️ Important notes

- This integration **scrapes** a public web page. There is no contractual stability guarantee: if iLMeteo changes the box markup, the parser may need an update.
- Out of respect for iLMeteo's [terms of use](https://www.ilmeteo.it/portale/termini_e_condizioni), the integration shows the attribution "Dati meteo forniti da iLMeteo.it (www.ilmeteo.it)" on the entity and polls at a low frequency (every 30 minutes).
- Unofficial project, not affiliated with iLMeteo Srl.
- The "iLMeteo" logo and trademark are property of iLMeteo Srl and are used solely to identify the data source.

---

## Features

- Native `weather` entity with current conditions (the 3-hour slot closest to the current time)
- **Daily forecast** up to 6 days (min/max temperature, cumulative precipitation, wind)
- **Hourly forecast** (3-hourly): 5 slots per day with temperature, apparent temperature, humidity, wind, precipitation
- Automatic day/night condition handling (e.g. `sunny` → `clear-night`)
- **Multi-location** support: each city is a separate instance
- UI configuration — no YAML, no token

---

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ menu → **Custom repositories**
2. Add `https://github.com/naked-head/ha-ilmeteo`, category **Integration**
3. Search for "iLMeteo" and install
4. Restart Home Assistant

### Manual

1. Download the latest [release](https://github.com/naked-head/ha-ilmeteo/releases/latest)
2. Copy `custom_components/ilmeteo` into `/config/custom_components/`
3. Restart Home Assistant

---

## Configuration

1. **Settings → Devices & Services → Add Integration → iLMeteo.it**
2. Select **region**, then **province**, then **municipality** from the dropdowns
3. Done: the entity is created and validated automatically

The full list of Italian municipalities (8,218 municipalities, 110 provinces, 20 regions) is bundled with the integration, so there is no need to look up codes manually. To add more locations, repeat the procedure.

> The dataset is generated from iLMeteo's official location codes via
> `scripts/build_locations.py` and stored compressed (~67 KB) in
> `custom_components/ilmeteo/data/locations.json.gz`.

## Exposed data

**Current conditions:** `temperature`, `apparent_temperature`, `humidity`, `wind_speed`, `wind_bearing`, `condition`

**Daily forecast:** for each day → max/min temperature, total precipitation, peak wind, representative condition (the 2:00 PM slot)

**Hourly forecast:** for each 3-hour slot → temperature, apparent temperature, humidity, wind, precipitation, condition

---

## Development & testing

The HTML parser is isolated in `api.py` (`parse_box`) with no Home Assistant dependency, so it can be tested directly:

```bash
python tests/test_parser.py
```

The tests use a real HTML fixture in `tests/fixtures/`.

To regenerate the bundled location dataset from the official iLMeteo CSV files:

```bash
python scripts/build_locations.py codici_comuni.csv codici_province.csv \
  custom_components/ilmeteo/data/locations.json.gz
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## License

MIT — see [LICENSE](LICENSE)

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by iLMeteo Srl. Weather data is retrieved from the publicly available iLMeteo.it forecast box. Use at your own risk and in accordance with iLMeteo's terms of use.
