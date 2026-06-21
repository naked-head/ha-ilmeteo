"""Config flow for the iLMeteo.it integration.

Flows: initial setup (user -> province -> city -> details), Reconfigure
(change location only), Options (change name and/or enabled sensors).
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from . import location_data
from .api import IlMeteoError, IlMeteoScraper
from .const import (
    ALL_OPTIONAL_SENSORS,
    CONF_CITTA,
    CONF_PLACE_NAME,
    CONF_SITE_NUMBER,
    DOMAIN,
    OPT_ENABLED_SENSORS,
    SENSOR_HUMIDITY,
    SENSOR_PRECIPITATION_PROBABILITY,
    SENSOR_TEMPERATURE,
    SENSOR_TEMPERATURE_MAX,
    SENSOR_TEMPERATURE_MIN,
    SENSOR_WIND_BEARING,
    SENSOR_WIND_SPEED,
)

_LOGGER = logging.getLogger(__name__)

CONF_REGION = "region"
CONF_PROVINCE = "province"
CONF_CITY = "city"
CONF_NAME = "name"

# Shared between the creation "details" step and the Options flow
_SENSOR_LABELS = {
    SENSOR_TEMPERATURE: "Temperatura (attuale)",
    SENSOR_HUMIDITY: "Umidità (attuale)",
    SENSOR_WIND_SPEED: "Velocità del vento (attuale)",
    SENSOR_WIND_BEARING: "Direzione del vento (attuale)",
    SENSOR_TEMPERATURE_MIN: "Temperatura minima (oggi)",
    SENSOR_TEMPERATURE_MAX: "Temperatura massima (oggi)",
    SENSOR_PRECIPITATION_PROBABILITY: "Probabilità di precipitazioni (oggi)",
}


def _sensor_selector() -> selector.SelectSelector:
    """Multi-select checklist widget for optional sensors."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(
                    value=s, label=_SENSOR_LABELS.get(s, s)
                )
                for s in ALL_OPTIONAL_SENSORS
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


_SITE_COUNTER_STORAGE_VERSION = 1
_SITE_COUNTER_STORAGE_KEY = f"{DOMAIN}_site_counter"


async def _next_site_number(hass) -> int:
    """Next site number; persisted independently of existing entries
    so numbers are never reused."""
    store: Store[dict] = Store(
        hass, _SITE_COUNTER_STORAGE_VERSION, _SITE_COUNTER_STORAGE_KEY
    )
    data = await store.async_load() or {"highest": 0}
    next_number = data["highest"] + 1
    await store.async_save({"highest": next_number})
    return next_number


class IlMeteoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Cascading config flow: region -> province -> city -> details."""

    VERSION = 3

    def __init__(self) -> None:
        self._region: str | None = None
        self._province: str | None = None
        self._citta: str | None = None
        self._city_name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the Options flow for this entry."""
        return OptionsFlowHandler(config_entry)

    # ------------------------------------------------------------------
    # Initial setup
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: pick the region."""
        if user_input is not None:
            self._region = user_input[CONF_REGION]
            return await self.async_step_province()

        regions = await self.hass.async_add_executor_job(location_data.get_regions)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_REGION): vol.In(regions)}
            ),
        )

    async def async_step_province(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: pick the province within the chosen region."""
        if user_input is not None:
            self._province = user_input[CONF_PROVINCE]
            return await self.async_step_city()

        provinces = await self.hass.async_add_executor_job(
            location_data.get_provinces, self._region
        )
        return self.async_show_form(
            step_id="province",
            data_schema=vol.Schema(
                {vol.Required(CONF_PROVINCE): vol.In(provinces)}
            ),
            description_placeholders={"region": self._region},
        )

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 3: pick the city and validate it against the live widget."""
        errors: dict[str, str] = {}

        cities = await self.hass.async_add_executor_job(
            location_data.get_cities, self._region, self._province
        )

        if user_input is not None:
            city = user_input[CONF_CITY]
            citta = cities.get(city)

            if not citta:
                errors[CONF_CITY] = "invalid_city"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{citta}")
                self._abort_if_unique_id_configured()

                session = async_get_clientsession(self.hass)
                scraper = IlMeteoScraper(citta, session)
                try:
                    day = await scraper.fetch_day(0)
                except IlMeteoError:
                    _LOGGER.exception("Validation fetch failed for %s", citta)
                    errors["base"] = "cannot_connect"
                else:
                    if not day.get("hours"):
                        errors["base"] = "no_data"
                    else:
                        self._citta = citta
                        self._city_name = city
                        return await self.async_step_details()

        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY): vol.In(sorted(cities.keys()))}
            ),
            errors=errors,
            description_placeholders={
                "province": self._province,
                "region": self._region,
            },
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 4: custom display name + which optional sensors to enable."""
        if user_input is not None:
            name = user_input.get(CONF_NAME) or self._city_name
            site_number = await _next_site_number(self.hass)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_CITTA: self._citta,
                    CONF_PLACE_NAME: name,
                    CONF_SITE_NUMBER: site_number,
                },
                options={
                    OPT_ENABLED_SENSORS: user_input.get(OPT_ENABLED_SENSORS, [])
                },
            )

        return self.async_show_form(
            step_id="details",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=self._city_name): str,
                    vol.Optional(OPT_ENABLED_SENSORS, default=[]): _sensor_selector(),
                }
            ),
            description_placeholders={"city": self._city_name},
        )

    # ------------------------------------------------------------------
    # Reconfigure — location only, name resets to new city (editable
    # again via Options), site number and sensors untouched.
    # ------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Entry point when the user selects "Reconfigure"."""
        return await self.async_step_reconfigure_region()

    async def async_step_reconfigure_region(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._region = user_input[CONF_REGION]
            return await self.async_step_reconfigure_province()

        regions = await self.hass.async_add_executor_job(location_data.get_regions)
        return self.async_show_form(
            step_id="reconfigure_region",
            data_schema=vol.Schema({vol.Required(CONF_REGION): vol.In(regions)}),
        )

    async def async_step_reconfigure_province(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._province = user_input[CONF_PROVINCE]
            return await self.async_step_reconfigure_city()

        provinces = await self.hass.async_add_executor_job(
            location_data.get_provinces, self._region
        )
        return self.async_show_form(
            step_id="reconfigure_province",
            data_schema=vol.Schema({vol.Required(CONF_PROVINCE): vol.In(provinces)}),
            description_placeholders={"region": self._region},
        )

    async def async_step_reconfigure_city(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        cities = await self.hass.async_add_executor_job(
            location_data.get_cities, self._region, self._province
        )

        if user_input is not None:
            city = user_input[CONF_CITY]
            citta = cities.get(city)
            entry = self._get_reconfigure_entry()

            if not citta:
                errors[CONF_CITY] = "invalid_city"
            elif any(
                e.entry_id != entry.entry_id and e.data.get(CONF_CITTA) == citta
                for e in self.hass.config_entries.async_entries(DOMAIN)
            ):
                errors["base"] = "already_configured"
            else:
                session = async_get_clientsession(self.hass)
                scraper = IlMeteoScraper(citta, session)
                try:
                    day = await scraper.fetch_day(0)
                except IlMeteoError:
                    _LOGGER.exception("Validation fetch failed for %s", citta)
                    errors["base"] = "cannot_connect"
                else:
                    if not day.get("hours"):
                        errors["base"] = "no_data"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            title=city,
                            data_updates={
                                CONF_CITTA: citta,
                                CONF_PLACE_NAME: city,
                            },
                        )

        return self.async_show_form(
            step_id="reconfigure_city",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY): vol.In(sorted(cities.keys()))}
            ),
            errors=errors,
            description_placeholders={
                "province": self._province,
                "region": self._region,
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: change the display name and/or enabled sensors."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            new_name = user_input.get(CONF_NAME) or self._entry.data[CONF_PLACE_NAME]

            # Name lives in entry.data/title, not entry.options — update
            # it explicitly here rather than via the Options write path.
            if new_name != self._entry.data.get(CONF_PLACE_NAME):
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    title=new_name,
                    data={**self._entry.data, CONF_PLACE_NAME: new_name},
                )

            return self.async_create_entry(
                title="",
                data={OPT_ENABLED_SENSORS: user_input.get(OPT_ENABLED_SENSORS, [])},
            )

        current_name = self._entry.data.get(CONF_PLACE_NAME, "")
        current_sensors = self._entry.options.get(OPT_ENABLED_SENSORS, [])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=current_name): str,
                    vol.Optional(
                        OPT_ENABLED_SENSORS, default=current_sensors
                    ): _sensor_selector(),
                }
            ),
        )
