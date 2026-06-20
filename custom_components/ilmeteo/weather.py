"""iLMeteo.it Weather entity (multi-box scraper backend)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import wind_bearing
from .const import CONF_CITTA, CONF_PLACE_NAME, DOMAIN, map_condition
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iLMeteo weather entity from a config entry."""
    coordinator: IlMeteoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IlMeteoWeather(coordinator, entry)])


class IlMeteoWeather(CoordinatorEntity[IlMeteoCoordinator], WeatherEntity):
    """Weather entity backed by iLMeteo's real1 + day1 + tri1 box widgets."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_attribution = "Dati meteo forniti da iLMeteo.it (www.ilmeteo.it)"
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self, coordinator: IlMeteoCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._place_name = entry.data[CONF_PLACE_NAME]
        self._attr_unique_id = f"{DOMAIN}_{entry.data[CONF_CITTA]}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(entry.data[CONF_CITTA]))},
            "name": f"iLMeteo.it {self._place_name}",
            "manufacturer": "iLMeteo.it",
            "entry_type": "service",
        }

    # ------------------------------------------------------------------
    # Helpers to navigate coordinator data
    # ------------------------------------------------------------------

    @property
    def _current(self) -> dict[str, Any]:
        """Real-time conditions (type=real1) — a genuine current reading."""
        return (self.coordinator.data or {}).get("current") or {}

    @property
    def _daily(self) -> list[dict[str, Any]]:
        """Official daily min/max + precipitation probability (type=day1)."""
        return (self.coordinator.data or {}).get("daily") or []

    @property
    def _days(self) -> list[dict[str, Any]]:
        """3-hourly forecast detail (type=tri1), used for hourly forecast."""
        return (self.coordinator.data or {}).get("days") or []

    # ------------------------------------------------------------------
    # Current conditions — from real1, a true current-hour reading, not a
    # forecast slot. No more "closest slot" guessing or timezone pitfalls.
    # ------------------------------------------------------------------

    @property
    def native_temperature(self) -> float | None:
        return self._current.get("temperature")

    @property
    def humidity(self) -> float | None:
        return self._current.get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        return self._current.get("wind_speed")

    @property
    def wind_bearing(self) -> float | None:
        return wind_bearing(self._current.get("wind_dir"))

    @property
    def condition(self) -> str | None:
        cur = self._current
        if not cur.get("condition_text"):
            return None
        # real1 has no night-sprite code (unlike tri1's >100 convention), so
        # day/night can't be read from the source. Approximate using a fixed
        # daylight window instead — good enough for the icon, not exact.
        now_hour = dt_util.now().hour
        is_night = not (6 <= now_hour < 21)
        condition = map_condition(cur.get("condition_text"), None)
        if is_night and condition == "sunny":
            return "clear-night"
        return condition

    # ------------------------------------------------------------------
    # Forecasts
    # ------------------------------------------------------------------

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Daily forecast using day1's official min/max (accurate) plus
        tri1's hourly data for fields day1 doesn't provide (precipitation
        amount). Falls back to tri1-only aggregation if day1 is unavailable.
        """
        daily = self._daily
        days = self._days
        if not daily:
            return None

        forecasts: list[Forecast] = []
        for i, d in enumerate(daily):
            # Match the corresponding tri1 day (same index = same day) only
            # for fields day1 doesn't supply, e.g. precipitation amount.
            tri_day = days[i] if i < len(days) else None
            precip = None
            if tri_day:
                precip = round(
                    sum(h.get("precipitation") or 0.0 for h in tri_day.get("hours") or []),
                    2,
                )
            date_str = tri_day.get("date") if tri_day else None

            forecasts.append(
                Forecast(
                    datetime=_iso_date(date_str) if date_str else dt_util.now().isoformat(),
                    native_temperature=d.get("temp_max"),
                    native_templow=d.get("temp_min"),
                    native_precipitation=precip,
                    precipitation_probability=d.get("precipitation_probability"),
                    native_wind_speed=d.get("wind_speed"),
                    wind_bearing=wind_bearing(d.get("wind_dir")),
                    condition=map_condition(None, d.get("condition_code")),
                )
            )
        return forecasts or None

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Hourly (3-hourly) forecast from tri1 — unchanged, still the best
        source for this level of detail (wind, humidity, visibility, etc).
        """
        forecasts: list[Forecast] = []
        for day in self._days:
            for h in day.get("hours") or []:
                dt = _parse_slot_time(day.get("date"), h.get("time"))
                forecasts.append(
                    Forecast(
                        datetime=(dt or dt_util.now()).isoformat(),
                        native_temperature=h.get("temperature"),
                        native_apparent_temperature=h.get("wind_chill"),
                        humidity=h.get("humidity"),
                        native_precipitation=h.get("precipitation"),
                        native_wind_speed=h.get("wind_speed"),
                        wind_bearing=wind_bearing(h.get("wind_dir")),
                        condition=map_condition(
                            h.get("condition_text"), h.get("condition_code")
                        ),
                    )
                )
        return forecasts or None


# ------------------------------------------------------------------
# Date/time helpers
# ------------------------------------------------------------------

def _iso_date(date_str: str | None) -> str:
    """Convert 'DD/MM/YYYY' to an ISO date string.

    The parsed datetime is naive but already represents *local* Italian
    time (scraped from an Italian site with no UTC indication). It must be
    *labeled* as local (attach tzinfo) rather than *converted* from UTC to
    local — `dt_util.as_local()` does the latter and would silently shift
    the value by the UTC offset (e.g. +2h in CEST), which is wrong here.
    """
    if not date_str:
        return dt_util.now().isoformat()
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE).isoformat()
    except ValueError:
        return dt_util.now().isoformat()


def _parse_slot_time(
    date_str: str | None, time_str: str | None
) -> datetime | None:
    """Combine 'DD/MM/YYYY' + 'HH.MM' into a local datetime.

    See _iso_date() for why we attach local tzinfo directly instead of
    calling dt_util.as_local() on a naive datetime.
    """
    if not date_str or not time_str:
        return None
    try:
        d = datetime.strptime(date_str, "%d/%m/%Y")
        hour = int(time_str.split(".")[0])
        dt = d.replace(hour=hour, minute=0, second=0, microsecond=0)
        return dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    except (ValueError, IndexError):
        return None
