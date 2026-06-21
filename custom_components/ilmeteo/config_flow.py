"""Config flow for the iLMeteo.it integration.

Three distinct flows live here:

- Initial setup (``async_step_user`` -> ``province`` -> ``city``): the usual
  cascading region/province/city picker. Assigns a permanent, generic
  ``site_number`` to the new entry (e.g. 1, 2, 3...) used to build stable,
  location-independent entity IDs (``weather.ilmeteo_site_1``). The
  *displayed* name, by contrast, does track the real place name and is
  free to change later without touching any identifier.

- Reconfigure (``async_step_reconfigure`` -> ``_province`` -> ``_city``):
  the same cascading picker, but only updates which location the existing
  entry tracks (``citta`` / ``place_name``). Site number, unique_ids and
  any enabled sensors are left untouched — this is intentionally scoped to
  "where does the data come from", nothing else.

- Options (``OptionsFlowHandler``): a checklist of optional dedicated
  sensor entities (temperature, humidity, ...) the user can turn on/off
  independently of the location.
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
    SENSOR_WIND_SPEED,
)

_LOGGER = logging.getLogger(__name__)

CONF_REGION = "region"
CONF_PROVINCE = "province"
CONF_CITY = "city"


_SITE_COUNTER_STORAGE_VERSION = 1
_SITE_COUNTER_STORAGE_KEY = f"{DOMAIN}_site_counter"


async def _next_site_number(hass) -> int:
    """Return the next site number, persisted independently of which
    config entries currently exist."""
    store: Store[dict] = Store(
        hass, _SITE_COUNTER_STORAGE_VERSION, _SITE_COUNTER_STORAGE_KEY
    )
    data = await store.async_load() or {"highest": 0}
    next_number = data["highest"] + 1
    await store.async_save({"highest": next_number})
    return next_number


class IlMeteoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Cascading config flow: region -> province -> city."""

    VERSION = 3

    def __init__(self) -> None:
        self._region: str | None = None
        self._province: str | None = None

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
                        site_number = await _next_site_number(self.hass)
                        return self.async_create_entry(
                            title=city,
                            data={
                                CONF_CITTA: citta,
                                CONF_PLACE_NAME: city,
                                CONF_SITE_NUMBER: site_number,
                            },
                        )

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

    # ------------------------------------------------------------------
    # Reconfigure — same cascade, but only updates citta/place_name on the
    # existing entry. Site number and options are left untouched.
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
    """Options flow: pick which optional dedicated sensors to expose."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={OPT_ENABLED_SENSORS: user_input.get(OPT_ENABLED_SENSORS, [])},
            )

        current = self._entry.options.get(OPT_ENABLED_SENSORS, [])
        sensor_labels = {
            SENSOR_TEMPERATURE: "Temperatura",
            SENSOR_HUMIDITY: "Umidità",
            SENSOR_PRECIPITATION_PROBABILITY: "Probabilità di precipitazioni",
            SENSOR_WIND_SPEED: "Velocità del vento",
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        OPT_ENABLED_SENSORS, default=current
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=s, label=sensor_labels.get(s, s)
                                )
                                for s in ALL_OPTIONAL_SENSORS
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
