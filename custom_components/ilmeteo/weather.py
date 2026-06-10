"""iLMeteo.it Weather entity."""
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
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONDITION_MAP, CONF_PLACE_NAME, DOMAIN
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iLMeteo weather entity from a config entry."""
    coordinator: IlMeteoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IlMeteoWeather(coordinator, entry)], update_before_add=True)


class IlMeteoWeather(CoordinatorEntity[IlMeteoCoordinator], WeatherEntity):
    """Weather entity backed by iLMeteo.it API."""

    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(
        self,
        coordinator: IlMeteoCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._place_name = entry.data[CONF_PLACE_NAME]
        self._attr_unique_id = f"{DOMAIN}_{coordinator.place_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(coordinator.place_id))},
            "name": f"iLMeteo {self._place_name}",
            "manufacturer": "iLMeteo.it",
            "model": coordinator.model,
        }

    # ------------------------------------------------------------------
    # Current conditions — taken from the first day of the forecast
    # ------------------------------------------------------------------

    @property
    def _today(self) -> dict[str, Any] | None:
        """Return today's forecast dict from coordinator data."""
        data = self.coordinator.data
        if not data:
            return None
        # The API returns a list of days; first element is today
        days = data.get("days") or data.get("forecasts") or (
            [data] if isinstance(data, dict) and "tmax" in data else []
        )
        return days[0] if days else None

    @property
    def native_temperature(self) -> float | None:
        """Return current (max) temperature."""
        day = self._today
        if day is None:
            return None
        # Prefer tmax for current; adapt once real API fields are known
        return _safe_float(day.get("tmax") or day.get("temperature_max"))

    @property
    def native_temperature_unit(self) -> str:
        return UnitOfTemperature.CELSIUS

    @property
    def humidity(self) -> float | None:
        day = self._today
        return _safe_float(day.get("hrel") or day.get("humidity")) if day else None

    @property
    def native_wind_speed(self) -> float | None:
        day = self._today
        return _safe_float(day.get("windvel") or day.get("wind_speed")) if day else None

    @property
    def wind_bearing(self) -> float | None:
        day = self._today
        return _safe_float(day.get("windir") or day.get("wind_direction")) if day else None

    @property
    def native_pressure(self) -> float | None:
        day = self._today
        return _safe_float(day.get("pressure") or day.get("slp")) if day else None

    @property
    def condition(self) -> str | None:
        day = self._today
        if day is None:
            return None
        code = day.get("description") or day.get("condition_code")
        if code is None:
            return None
        return CONDITION_MAP.get(int(code))

    # ------------------------------------------------------------------
    # Daily forecast
    # ------------------------------------------------------------------

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return multi-day forecast."""
        data = self.coordinator.data
        if not data:
            return None

        days = data.get("days") or data.get("forecasts") or []
        if not days and isinstance(data, dict) and "tmax" in data:
            days = [data]

        forecasts: list[Forecast] = []
        for day in days:
            date_str = day.get("date") or day.get("value")
            code = day.get("description") or day.get("condition_code")
            forecasts.append(
                Forecast(
                    datetime=_parse_date(date_str),
                    native_temperature=_safe_float(
                        day.get("tmax") or day.get("temperature_max")
                    ),
                    native_templow=_safe_float(
                        day.get("tmin") or day.get("temperature_min")
                    ),
                    native_precipitation=_safe_float(
                        day.get("precipitation") or day.get("rain")
                    ),
                    native_wind_speed=_safe_float(
                        day.get("windvel") or day.get("wind_speed")
                    ),
                    wind_bearing=_safe_float(
                        day.get("windir") or day.get("wind_direction")
                    ),
                    condition=CONDITION_MAP.get(int(code)) if code is not None else None,
                )
            )
        return forecasts or None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    """Convert value to float, return None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> str:
    """Return an ISO datetime string from various date formats."""
    if value is None:
        return datetime.now().isoformat()
    # Already ISO
    if isinstance(value, str) and "T" in value:
        return value
    # Format DD.MM.YYYY (used in XML examples)
    if isinstance(value, str) and "." in value:
        try:
            dt = datetime.strptime(value, "%d.%m.%Y")
            return dt.isoformat()
        except ValueError:
            pass
    # Format YYYY-MM-DD
    if isinstance(value, str) and "-" in value:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.isoformat()
        except ValueError:
            pass
    return str(value)
