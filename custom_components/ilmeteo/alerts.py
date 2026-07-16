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

# Hysteresis deltas: an active alert is kept alive until the value drops
# this much below the threshold that triggered it. Prevents rapid on/off
# oscillation when values hover near a boundary between refreshes.
HEAT_HYSTERESIS_C = 2
COLD_HYSTERESIS_C = 2
WIND_HYSTERESIS_KMH = 5
RAIN_PROB_HYSTERESIS = 5


@dataclass
class WeatherAlert:
    """A single active weather alert for a location."""

    alert_id: str  # stable key per condition type, e.g. "heuristic_heat"
    severity: str  # "yellow" | "orange" | "red"
    kind: str  # "heat" | "cold" | "wind" | "storm" | "hail" | "rain"
    title: str
    message: str
    source: str  # provider name, e.g. "heuristic"
    day: str = "today"  # "today" | "tomorrow" | "aftertomorrow" — grouping key for batched notifications

    @property
    def signature(self) -> str:
        """Changes whenever the alert is newly issued or its severity changes."""
        return f"{self.alert_id}:{self.severity}"


class AlertProvider(ABC):
    """Base class for anything that can produce WeatherAlert objects."""

    name: str = "base"

    @abstractmethod
    async def async_get_alerts(
        self,
        coordinator_data: dict[str, Any],
        citta: str,
        place_name: str,
        active_alert_ids: frozenset[str] | None = None,
    ) -> list[WeatherAlert]:
        """Return the currently active alerts for this location.

        active_alert_ids: the set of alert_ids currently in the dedup store.
        Providers that implement hysteresis use this to keep an alert alive
        even when the value has dipped just below the trigger threshold.
        """


class HeuristicAlertProvider(AlertProvider):
    """Derives alerts from real1/day1/tri1 data already in the coordinator.

    Evaluates "oggi" (index 0) and "domani" (index 1) independently: each
    produces its own alert_id (e.g. heuristic_heat_today vs
    heuristic_heat_tomorrow), so they dedup and notify separately. real1
    ("current conditions") only applies to today.

    Hysteresis: once an alert is active, it is kept alive until the value
    drops below (threshold - delta), preventing rapid on/off oscillation
    when values hover near a boundary between 30-minute refreshes.

    Not an official alert source — see module docstring.
    """

    name = "heuristic"

    async def async_get_alerts(
        self,
        coordinator_data: dict[str, Any],
        citta: str,
        place_name: str,
        active_alert_ids: frozenset[str] | None = None,
    ) -> list[WeatherAlert]:
        daily = coordinator_data.get("daily") or []
        days = coordinator_data.get("days") or []
        current = coordinator_data.get("current") or {}
        active = active_alert_ids or frozenset()

        alerts: list[WeatherAlert] = []
        alerts += self._for_day(daily, days, current, index=0, suffix="today", label="oggi", active=active)
        alerts += self._for_day(daily, days, current, index=1, suffix="tomorrow", label="domani", active=active)
        return alerts

    def _for_day(
        self,
        daily: list[dict[str, Any]],
        days: list[dict[str, Any]],
        current: dict[str, Any],
        index: int,
        suffix: str,
        label: str,
        active: frozenset[str],
    ) -> list[WeatherAlert]:
        summary = daily[index] if len(daily) > index else {}
        hours = (
            days[index]["hours"]
            if len(days) > index and days[index].get("hours")
            else []
        )
        current_for_day = current if index == 0 else {}

        alerts: list[WeatherAlert] = []
        alerts += self._heat_cold(summary, suffix, label, active)
        alerts += self._wind(summary, current_for_day, suffix, label, active)
        alerts += self._storm_hail(hours, current_for_day, suffix, label)
        alerts += self._rain(summary, suffix, label, active)
        return alerts

    @staticmethod
    def _heat_cold(
        summary: dict[str, Any], suffix: str, label: str, active: frozenset[str]
    ) -> list[WeatherAlert]:
        alerts: list[WeatherAlert] = []
        tmax = summary.get("temp_max")
        tmin = summary.get("temp_min")
        h = HEAT_HYSTERESIS_C
        c = COLD_HYSTERESIS_C

        heat_id = f"heuristic_heat_{suffix}"
        cold_id = f"heuristic_cold_{suffix}"
        heat_active = heat_id in active
        cold_active = cold_id in active

        if tmax is not None:
            # Trigger orange at HEAT_ORANGE_C; keep alive until HEAT_ORANGE_C - h
            # Trigger yellow at HEAT_YELLOW_C; keep alive until HEAT_YELLOW_C - h
            if tmax >= HEAT_ORANGE_C or (heat_active and tmax >= HEAT_ORANGE_C - h):
                alerts.append(WeatherAlert(
                    heat_id, "orange", "heat", f"Caldo estremo ({label})",
                    f"Temperatura massima prevista {label}: {tmax:.0f}°C.", "heuristic", day=suffix,
                ))
            elif tmax >= HEAT_YELLOW_C or (heat_active and tmax >= HEAT_YELLOW_C - h):
                alerts.append(WeatherAlert(
                    heat_id, "yellow", "heat", f"Caldo intenso ({label})",
                    f"Temperatura massima prevista {label}: {tmax:.0f}°C.", "heuristic", day=suffix,
                ))

        if tmin is not None:
            if tmin <= COLD_ORANGE_C or (cold_active and tmin <= COLD_ORANGE_C + c):
                alerts.append(WeatherAlert(
                    cold_id, "orange", "cold", f"Gelo intenso ({label})",
                    f"Temperatura minima prevista {label}: {tmin:.0f}°C.", "heuristic", day=suffix,
                ))
            elif tmin <= COLD_YELLOW_C or (cold_active and tmin <= COLD_YELLOW_C + c):
                alerts.append(WeatherAlert(
                    cold_id, "yellow", "cold", f"Gelo ({label})",
                    f"Temperatura minima prevista {label}: {tmin:.0f}°C.", "heuristic", day=suffix,
                ))

        return alerts

    @staticmethod
    def _wind(
        summary: dict[str, Any], current: dict[str, Any],
        suffix: str, label: str, active: frozenset[str]
    ) -> list[WeatherAlert]:
        speed = summary.get("wind_speed")
        if speed is None:
            speed = current.get("wind_speed")
        if speed is None:
            return []

        wind_id = f"heuristic_wind_{suffix}"
        wind_active = wind_id in active
        h = WIND_HYSTERESIS_KMH

        if speed >= WIND_ORANGE_KMH or (wind_active and speed >= WIND_ORANGE_KMH - h):
            return [WeatherAlert(
                wind_id, "orange", "wind", f"Vento forte ({label})",
                f"Velocità del vento prevista {label}: {speed:.0f} km/h.", "heuristic", day=suffix,
            )]
        if speed >= WIND_YELLOW_KMH or (wind_active and speed >= WIND_YELLOW_KMH - h):
            return [WeatherAlert(
                wind_id, "yellow", "wind", f"Vento sostenuto ({label})",
                f"Velocità del vento prevista {label}: {speed:.0f} km/h.", "heuristic", day=suffix,
            )]
        return []

    @staticmethod
    def _storm_hail(
        hours: list[dict[str, Any]], current: dict[str, Any], suffix: str, label: str
    ) -> list[WeatherAlert]:
        # No hysteresis for storm/hail: condition_text is binary (present/absent)
        texts = [h.get("condition_text") or "" for h in hours]
        texts.append(current.get("condition_text") or "")
        joined = " ".join(texts).lower()

        alerts: list[WeatherAlert] = []
        if "grandine" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_hail_{suffix}", "orange", "hail", f"Rischio grandine ({label})",
                f"Condizioni compatibili con grandinate {label}.", "heuristic", day=suffix,
            ))
        if "temporale forte" in joined or "temporali forti" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_storm_{suffix}", "orange", "storm", f"Temporali forti ({label})",
                f"Previsti temporali forti {label}.", "heuristic", day=suffix,
            ))
        elif "temporal" in joined:
            alerts.append(WeatherAlert(
                f"heuristic_storm_{suffix}", "yellow", "storm", f"Temporali ({label})",
                f"Previsti temporali {label}.", "heuristic", day=suffix,
            ))
        return alerts

    @staticmethod
    def _rain(
        summary: dict[str, Any], suffix: str, label: str, active: frozenset[str]
    ) -> list[WeatherAlert]:
        prob = summary.get("precipitation_probability")
        if prob is None:
            return []
        rain_id = f"heuristic_rain_{suffix}"
        h = RAIN_PROB_HYSTERESIS
        if prob >= RAIN_PROB_YELLOW or (rain_id in active and prob >= RAIN_PROB_YELLOW - h):
            return [WeatherAlert(
                rain_id, "yellow", "rain", f"Piogge probabili ({label})",
                f"Probabilità di precipitazioni {label}: {prob:.0f}%.", "heuristic", day=suffix,
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
        self, coordinator_data: dict[str, Any], citta: str, place_name: str,
        active_alert_ids: frozenset[str] | None = None,
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
                    day="today" if day_key == "events_today" else "tomorrow",
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
                    day=day_key,
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
        self, coordinator_data: dict[str, Any], citta: str, place_name: str,
        active_alert_ids: frozenset[str] | None = None,
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

            day_severity = DPC_LEVEL_SEVERITY.get(day.get("level"))

            # Level-based alert for the day block
            if day_severity is not None:
                precip = day.get("precipitation", "")
                alerts.append(WeatherAlert(
                    f"dpc_vigilance_{day_key}", day_severity, "rain",
                    f"Vigilanza meteo ({day_label})",
                    f"Precipitazioni previste {day_label}: {precip}.".strip(),
                    "protezione_civile_vigilance",
                    day=day_key,
                ))

            # Phenomena alerts: only if the day level meets the threshold.
            # Phenomena don't carry their own level — we use the day level.
            # Distance/direction are geographic coordinates of the zone centroid
            # and are meaningful only for spatially localised phenomena (wind,
            # storms, snow) — not for temperature which affects the whole zone.
            if day_severity is None:
                continue

            PHENOMENA_WITH_LOCATION = {"Venti", "Temporali", "Neve", "Mare", "Ghiaccio"}

            for phenom in day.get("phenomena") or []:
                event = phenom.get("event", "")
                value = phenom.get("value", "")
                distance = phenom.get("distance")
                direction = phenom.get("direction", "")
                alert_id = (
                    f"dpc_vigilance_{day_key}_{event.lower().replace(' ', '_')}"
                )
                desc_parts = [f"{event} {value}".strip()]
                if event in PHENOMENA_WITH_LOCATION and distance is not None and direction:
                    desc_parts.append(f"a {distance} km in direzione {direction}")
                alerts.append(WeatherAlert(
                    alert_id, day_severity,
                    DPC_VIGILANCE_KIND.get(event, "other"),
                    f"{event} {value} ({day_label})".strip(),
                    f"{', '.join(desc_parts)} — {day_label}.",
                    "protezione_civile_vigilance",
                    day=day_key,
                ))

        return alerts
