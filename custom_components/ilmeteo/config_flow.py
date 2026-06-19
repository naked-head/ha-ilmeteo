"""Config flow for the iLMeteo.it integration (cascading region/province/city)."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import location_data
from .api import IlMeteoError, IlMeteoScraper
from .const import CONF_CITTA, CONF_PLACE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_REGION = "region"
CONF_PROVINCE = "province"
CONF_CITY = "city"


class IlMeteoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Cascading config flow: region -> province -> city."""

    VERSION = 2

    def __init__(self) -> None:
        self._region: str | None = None
        self._province: str | None = None

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

                # Validate the code actually returns data
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
                        return self.async_create_entry(
                            title=city,
                            data={
                                CONF_CITTA: citta,
                                CONF_PLACE_NAME: city,
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
