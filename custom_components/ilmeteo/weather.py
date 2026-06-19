"""iLMeteo.it Weather entity (box scraper backend)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
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
    """Weather entity backed by the iLMeteo box widget."""

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
    def _days(self) -> list[dict[str, Any]]:
        return self.coordinator.data or []

    @property
    def _current_hour(self) -> dict[str, Any] | None:
        """Return the forecast slot closest to 'now' (today's nearest slot)."""
        if not self._days:
            return None
        today = self._days[0]
        hours = today.get("hours") or []
        if not hours:
            return None
        now = dt_util.now()
        best = None
        best_delta = None
        for h in hours:
            slot_time = _parse_slot_time(today.get("date"), h.get("time"), now)
            if slot_time is None:
                continue
            delta = abs((slot_time - now).total_seconds())
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best = h
        return best or hours[0]

    # ------------------------------------------------------------------
    # Current conditions
    # ------------------------------------------------------------------

    @property
    def native_temperature(self) -> float | None:
        h = self._current_hour
        return h.get("temperature") if h else None

    @property
    def native_apparent_temperature(self) -> float | None:
        h = self._current_hour
        return h.get("wind_chill") if h else None

    @property
    def humidity(self) -> float | None:
        h = self._current_hour
        return h.get("humidity") if h else None

    @property
    def native_wind_speed(self) -> float | None:
        h = self._current_hour
        return h.get("wind_speed") if h else None

    @property
    def wind_bearing(self) -> float | None:
        h = self._current_hour
        return wind_bearing(h.get("wind_dir")) if h else None

    @property
    def condition(self) -> str | None:
        h = self._current_hour
        if not h:
            return None
        return map_condition(h.get("condition_text"), h.get("condition_code"))

    # ------------------------------------------------------------------
    # Forecasts
    # ------------------------------------------------------------------

    async def async_forecast_daily(self) -> list[Forecast] | None:
        forecasts: list[Forecast] = []
        for day in self._days:
            hours = day.get("hours") or []
            if not hours:
                continue
            temps = [h["temperature"] for h in hours if h.get("temperature") is not None]
            precip = sum(h.get("precipitation") or 0.0 for h in hours)
            winds = [h["wind_speed"] for h in hours if h.get("wind_speed") is not None]

            # Representative condition: prefer the 14.00 slot, else the worst
            mid = next((h for h in hours if h.get("time", "").startswith("14")), hours[0])

            forecasts.append(
                Forecast(
                    datetime=_iso_date(day.get("date")),
                    native_temperature=max(temps) if temps else None,
                    native_templow=min(temps) if temps else None,
                    native_precipitation=round(precip, 2),
                    native_wind_speed=max(winds) if winds else None,
                    wind_bearing=wind_bearing(mid.get("wind_dir")),
                    condition=map_condition(
                        mid.get("condition_text"), mid.get("condition_code")
                    ),
                )
            )
        return forecasts or None

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        forecasts: list[Forecast] = []
        for day in self._days:
            for h in day.get("hours") or []:
                dt = _parse_slot_time(day.get("date"), h.get("time"))
                forecasts.append(
                    Forecast(
                        datetime=(dt or datetime.now()).isoformat(),
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
    """Convert 'DD/MM/YYYY' to an ISO date string."""
    if not date_str:
        return dt_util.now().isoformat()
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt_util.as_local(dt).isoformat()
    except ValueError:
        return dt_util.now().isoformat()


def _parse_slot_time(
    date_str: str | None, time_str: str | None, ref: datetime | None = None
) -> datetime | None:
    """Combine 'DD/MM/YYYY' + 'HH.MM' into a local datetime."""
    if not date_str or not time_str:
        return None
    try:
        d = datetime.strptime(date_str, "%d/%m/%Y")
        hour = int(time_str.split(".")[0])
        dt = d.replace(hour=hour, minute=0, second=0, microsecond=0)
        return dt_util.as_local(dt)
    except (ValueError, IndexError):
        return None
