"""Weather alert model and provider abstraction.

iLMeteo.it does not expose structured alert data in its public box widgets
(only real1/day1/tri1 are documented — see business/portali). Until/unless
iLMeteo provides something better, alerts are derived by HeuristicAlertProvider
from the same data already scraped for the weather/sensor entities.

AlertProvider is deliberately generic so a future provider backed by
Protezione Civile open data (bollettino di criticità per zona di allerta) or
by an official iLMeteo feed can be added without touching alert_manager.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# Heuristic thresholds. These are our own invention, not official
# Protezione Civile / iLMeteo thresholds — tune here if needed.
HEAT_YELLOW_C = 35
HEAT_ORANGE_C = 38
COLD_YELLOW_C = 0
COLD_ORANGE_C = -5
WIND_YELLOW_KMH = 40
WIND_ORANGE_KMH = 60
RAIN_PROB_YELLOW = 80


@dataclass
class WeatherAlert:
    """A single active weather alert for a location."""

    alert_id: str  # stable key per condition type, e.g. "heuristic_heat"
    severity: str  # "yellow" | "orange" | "red"
    kind: str  # "heat" | "cold" | "wind" | "storm" | "hail" | "rain"
    title: str
    message: str
    source: str  # provider name, e.g. "heuristic"

    @property
    def signature(self) -> str:
        """Changes whenever the alert is newly issued or its severity changes."""
        return f"{self.alert_id}:{self.severity}"


class AlertProvider(ABC):
    """Base class for anything that can produce WeatherAlert objects."""

    name: str = "base"

    @abstractmethod
    async def async_get_alerts(
        self, coordinator_data: dict[str, Any], citta: str, place_name: str
    ) -> list[WeatherAlert]:
        """Return the currently active alerts for this location."""


class HeuristicAlertProvider(AlertProvider):
    """Derives alerts from real1/day1/tri1 data already in the coordinator.

    Evaluates "oggi" (index 0) and "domani" (index 1) independently: each
    produces its own alert_id (e.g. heuristic_heat_today vs
    heuristic_heat_tomorrow), so they dedup and notify separately. real1
    ("current conditions") only applies to today.

    Not an official alert source — see module docstring.
    """

    name = "heuristic"

    async def async_get_alerts(
        self, coordinator_data: dict[str, Any], citta: str, place_name: str
    ) -> list[WeatherAlert]:
        daily = coordinator_data.get("daily") or []
        days = coordinator_data.get("days") or []
        current = coordinator_data.get("current") or {}

        alerts: list[WeatherAlert] = []
        alerts += self._for_day(daily, days, current, index=0, suffix="today", label="oggi")
        alerts += self._for_day(daily, days, current, index=1, suffix="tomorrow", label="domani")
        return alerts

    def _for_day(
        self,
        daily: list[dict[str, Any]],
        days: list[dict[str, Any]],
        current: dict[str, Any],
        index: int,
        suffix: str,
        label: str,
    ) -> list[WeatherAlert]:
        summary = daily[index] if len(daily) > index else {}
        hours = (
            days[index]["hours"]
            if len(days) > index and days[index].get("hours")
            else []
        )
        current_for_day = current if index == 0 else {}

        alerts: list[WeatherAlert] = []
        alerts += self._heat_cold(summary, suffix, label)
        alerts += self._wind(summary, current_for_day, suffix, label)
        alerts += self._storm_hail(hours, current_for_day, suffix, label)
        alerts += self._rain(summary, suffix, label)
        return alerts

    @staticmethod
    def _heat_cold(summary: dict[str, Any], suffix: str, label: str) -> list[WeatherAlert]:
        alerts: list[WeatherAlert] = []
        tmax = summary.get("temp_max")
        tmin = summary.get("temp_min")

        if tmax is not None and tmax >= HEAT_ORANGE_C:
            alerts.append(WeatherAlert(
                f"heuristic_heat_{suffix}", "orange", "heat", f"Caldo estremo ({label})",
                f"Temperatura massima prevista {label}: {tmax:.0f}°C.", "heuristic",
            ))
        elif tmax is not None and tmax >= HEAT_YELLOW_C:
            alerts.append(WeatherAlert(
                f"heuristic_heat_{suffix}", "yellow", "heat", f"Caldo intenso ({label})",
                f"Temperatura massima prevista {label}: {tmax:.0f}°C.", "heuristic",
            ))

        if tmin is not None and tmin <= COLD_ORANGE_C:
            alerts.append(WeatherAlert(
                f"heuristic_cold_{suffix}", "orange", "cold", f"Gelo intenso ({label})",
                f"Temperatura minima prevista {label}: {tmin:.0f}°C.", "heuristic",
            ))
        elif tmin is not None and tmin <= COLD_YELLOW_C:
            alerts.append(WeatherAlert(
                f"heuristic_cold_{suffix}", "yellow", "cold", f"Gelo ({label})",
                f"Temperatura minima prevista {label}: {tmin:.0f}°C.", "heuristic",
            ))

        return alerts

    @staticmethod
    def _wind(
        summary: dict[str, Any], current: dict[str, Any], suffix: str, label: str
    ) -> list[WeatherAlert]:
        speed = summary.get("wind_speed")
        if speed is None:
            speed = current.get("wind_speed")
        if speed is None:
            return []

        if speed >= WIND_ORANGE_KMH:
            return [WeatherAlert(
                f"heuristic_wind_{suffix}", "orange", "wind", f"Vento forte ({label})",
                f"Velocità del vento prevista {label}: {speed:.0f} km/h.", "heuristic",
            )]
        if speed >= WIND_YELLOW_KMH:
            return [WeatherAlert(
                f"heuristic_wind_{suffix}", "yellow", "wind", f"Vento sostenuto ({label})",
                f"Velocità del vento prevista {label}: {speed:.0f} km/h.", "heuristic",
            )]
        return []

    @staticmethod
    def _storm_hail(
        hours: list[dict[str, Any]], current: dict[str, Any], suffix: str, label: str
    ) -> list[WeatherAlert]:
        texts = [h.get("condition_text") or "" for h in hours]
        texts.append(current.get("condition_text") or "")
        joined = " ".join(texts).lower()

        alerts: list[WeatherAlert] = []
        if "grandine" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_hail_{suffix}", "orange", "hail", f"Rischio grandine ({label})",
                f"Condizioni compatibili con grandinate {label}.", "heuristic",
            ))
        if "temporale forte" in joined or "temporali forti" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_storm_{suffix}", "orange", "storm", f"Temporali forti ({label})",
                f"Previsti temporali forti {label}.", "heuristic",
            ))
        elif "temporal" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_storm_{suffix}", "yellow", "storm", f"Temporali ({label})",
                f"Previsti temporali {label}.", "heuristic",
            ))
        return alerts

    @staticmethod
    def _rain(summary: dict[str, Any], suffix: str, label: str) -> list[WeatherAlert]:
        prob = summary.get("precipitation_probability")
        if prob is not None and prob >= RAIN_PROB_YELLOW:
            return [WeatherAlert(
                f"heuristic_rain_{suffix}", "yellow", "rain", f"Piogge probabili ({label})",
                f"Probabilità di precipitazioni {label}: {prob:.0f}%.", "heuristic",
            )]
        return []


# Bollettino di criticità: livello -> colore (0=bianco, 1=verde: nessuna
# allerta -> ignorati; 2=giallo, 3=arancione, 4=rosso).
DPC_LEVEL_SEVERITY = {2: "yellow", 3: "orange", 4: "red"}
DPC_RISK_KIND = {
    "Temporali": "storm",
    "Idraulico": "flood",
    "Idrogeologico": "landslide",
}


class DpcSensorAlertProvider(AlertProvider):
    """Reads the sensor.dpc_alert entity from the DPC Alert custom component
    (github.com/caiosweet/Home-Assistant-custom-components-DPC-Alert), if the
    user has it installed and configured for this location.

    Official Protezione Civile data (CC-BY-SA 4.0), already fetched by that
    other integration — this provider makes no HTTP requests of its own, it
    only reads hass.states.get() on an entity the user points us to.
    """

    name = "protezione_civile"

    def __init__(self, hass: Any, entity_id: str) -> None:
        self.hass = hass
        self.entity_id = entity_id

    async def async_get_alerts(
        self, coordinator_data: dict[str, Any], citta: str, place_name: str
    ) -> list[WeatherAlert]:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return []

        alerts: list[WeatherAlert] = []
        for day_key, day_label in (
            ("events_today", "oggi"),
            ("events_tomorrow", "domani"),
        ):
            for event in state.attributes.get(day_key) or []:
                severity = DPC_LEVEL_SEVERITY.get(event.get("level"))
                if severity is None:
                    continue
                risk = event.get("risk", "?")
                alerts.append(WeatherAlert(
                    f"dpc_{risk.lower()}_{day_key}", severity,
                    DPC_RISK_KIND.get(risk, "other"),
                    f"{event.get('alert', 'Allerta')} — {risk} ({day_label})",
                    f"{event.get('info', '')} — rischio {risk}, {day_label}.".strip(),
                    "protezione_civile",
                ))

        # Older versions of the component may not expose events_today/
        # events_tomorrow: fall back to the aggregate today/tomorrow block.
        if not alerts:
            for day_key, day_label in (("today", "oggi"), ("tomorrow", "domani")):
                day = state.attributes.get(day_key)
                if not day:
                    continue
                severity = DPC_LEVEL_SEVERITY.get(day.get("level"))
                if severity is None:
                    continue
                alerts.append(WeatherAlert(
                    f"dpc_{day_key}", severity, "other",
                    f"{day.get('alert', 'Allerta')} ({day_label})",
                    f"{day.get('info', '')} ({day_label}).", "protezione_civile",
                ))

        return alerts


# Fenomeni meteorologici di vigilanza: mappa event -> kind
DPC_VIGILANCE_KIND = {
    "Venti": "wind",
    "Mare": "other",
    "Neve": "snow",
    "Temporali": "storm",
    "Piogge": "rain",
    "Temperature": "heat",
    "Ghiaccio": "cold",
}


class DpcVigilanceProvider(AlertProvider):
    """Reads the sensor.dpc_vigilance entity from the DPC Alert custom component
    (github.com/caiosweet/Home-Assistant-custom-components-DPC-Alert).

    Covers today, tomorrow and aftertomorrow. Each day produces:
    - a level-based alert when level >= 2 (precipitation quantity from the day block)
    - one alert per nearby phenomenon (event, value, distance, direction)

    Complementary to DpcSensorAlertProvider: covers meteorological phenomena
    (wind, snow, storms, etc.) that sensor.dpc_alert does not report.
    """

    name = "protezione_civile_vigilance"

    def __init__(self, hass: Any, entity_id: str) -> None:
        self.hass = hass
        self.entity_id = entity_id

    async def async_get_alerts(
        self, coordinator_data: dict[str, Any], citta: str, place_name: str
    ) -> list[WeatherAlert]:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return []

        alerts: list[WeatherAlert] = []
        for day_key, day_label in (
            ("today", "oggi"),
            ("tomorrow", "domani"),
            ("aftertomorrow", "dopodomani"),
        ):
            day = state.attributes.get(day_key)
            if not day:
                continue

            # Level-based alert for the day block
            severity = DPC_LEVEL_SEVERITY.get(day.get("level"))
            if severity is not None:
                precip = day.get("precipitation", "")
                alerts.append(WeatherAlert(
                    f"dpc_vigilance_{day_key}", severity, "rain",
                    f"Vigilanza meteo ({day_label})",
                    f"Precipitazioni previste {day_label}: {precip}.".strip(),
                    "protezione_civile_vigilance",
                ))

            # One alert per nearby phenomenon
            for phenom in day.get("phenomena") or []:
                event = phenom.get("event", "")
                value = phenom.get("value", "")
                distance = phenom.get("distance")
                direction = phenom.get("direction", "")
                alert_id = (
                    f"dpc_vigilance_{day_key}_{event.lower().replace(' ', '_')}"
                )
                desc_parts = [f"{event} {value}".strip()]
                if distance is not None and direction:
                    desc_parts.append(f"a {distance} km in direzione {direction}")
                severity_phenom = DPC_LEVEL_SEVERITY.get(
                    phenom.get("level"), severity or "yellow"
                )
                alerts.append(WeatherAlert(
                    alert_id, severity_phenom,
                    DPC_VIGILANCE_KIND.get(event, "other"),
                    f"{event} {value} ({day_label})".strip(),
                    f"{', '.join(desc_parts)} — {day_label}.",
                    "protezione_civile_vigilance",
                ))

        return alerts