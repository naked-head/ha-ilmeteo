"""Optional dedicated sensor entities for iLMeteo.it.

These are off by default for every entry (new or existing) and are turned
on individually via the integration's Options flow. They exist alongside
the weather entity specifically so their values can be tracked in Home
Assistant's long-term statistics (graphs, the Statistics card, etc.) —
something a weather entity's attributes cannot do, since attributes have
no state_class.

Each sensor's unique_id is tied to the config entry (entry_id), exactly
like the weather entity, so it survives a location reconfigure unchanged.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALL_OPTIONAL_SENSORS,
    CONF_PLACE_NAME,
    CONF_SITE_NUMBER,
    DOMAIN,
    OPT_ENABLED_SENSORS,
    SENSOR_HUMIDITY,
    SENSOR_PRECIPITATION_PROBABILITY,
    SENSOR_TEMPERATURE,
    SENSOR_WIND_SPEED,
)
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)

# Per-sensor static config: (friendly name suffix, device_class, unit, icon)
_SENSOR_SPECS: dict[str, dict[str, Any]] = {
    SENSOR_TEMPERATURE: {
        "name": "Temperatura",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": None,
    },
    SENSOR_HUMIDITY: {
        "name": "Umidità",
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": None,
    },
    SENSOR_PRECIPITATION_PROBABILITY: {
        "name": "Probabilità di precipitazioni",
        "device_class": None,
        "unit": PERCENTAGE,
        "icon": "mdi:weather-rainy",
    },
    SENSOR_WIND_SPEED: {
        "name": "Velocità del vento",
        "device_class": SensorDeviceClass.WIND_SPEED,
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "icon": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the enabled optional sensors, and remove any deselected ones."""
    coordinator: IlMeteoCoordinator = hass.data[DOMAIN][entry.entry_id]
    enabled = set(entry.options.get(OPT_ENABLED_SENSORS, []))

    # Add the currently-enabled sensors.
    entities = [
        IlMeteoSensor(coordinator, entry, sensor_type)
        for sensor_type in ALL_OPTIONAL_SENSORS
        if sensor_type in enabled
    ]
    if entities:
        async_add_entities(entities)

    # Remove any sensor the user has since deselected. Just not adding it
    # again above would leave it registered and permanently "unavailable" —
    # the user explicitly asked for deselecting to mean deletion.
    registry = er.async_get(hass)
    for sensor_type in ALL_OPTIONAL_SENSORS:
        if sensor_type in enabled:
            continue
        unique_id = f"{entry.entry_id}_{sensor_type}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            _LOGGER.debug("Removing deselected sensor %s", entity_id)
            registry.async_remove(entity_id)


class IlMeteoSensor(CoordinatorEntity[IlMeteoCoordinator], SensorEntity):
    """A single optional dedicated sensor (temperature, humidity, ...)."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IlMeteoCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._site_number = entry.data[CONF_SITE_NUMBER]
        place_name = entry.data[CONF_PLACE_NAME]

        spec = _SENSOR_SPECS[sensor_type]
        self._attr_name = spec["name"]
        self._attr_device_class = spec["device_class"]
        self._attr_native_unit_of_measurement = spec["unit"]
        self._attr_icon = spec["icon"]

        # Same identifiers as the weather entity -> groups under one device.
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"iLMeteo.it {place_name}",
            "manufacturer": "iLMeteo.it",
            "entry_type": "service",
        }

    @property
    def suggested_object_id(self) -> str | None:
        """Generic, location-independent entity_id seed (see weather.py)."""
        return f"ilmeteo_site_{self._site_number}_{self._sensor_type}"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}

        if self._sensor_type == SENSOR_PRECIPITATION_PROBABILITY:
            daily = data.get("daily") or []
            if not daily:
                return None
            return daily[0].get("precipitation_probability")

        current = data.get("current") or {}
        if self._sensor_type == SENSOR_TEMPERATURE:
            return current.get("temperature")
        if self._sensor_type == SENSOR_HUMIDITY:
            return current.get("humidity")
        if self._sensor_type == SENSOR_WIND_SPEED:
            return current.get("wind_speed")
        return None
