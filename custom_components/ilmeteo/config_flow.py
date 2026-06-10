"""Config flow for iLMeteo.it integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IlMeteoAuthError, IlMeteoClient
from .const import CONF_PLACE_ID, CONF_PLACE_NAME, CONF_MODEL, DEFAULT_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IlMeteoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for iLMeteo.it."""

    VERSION = 1

    def __init__(self) -> None:
        self._token: str | None = None
        self._search_results: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: ask for API token and location search query."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._token = user_input[CONF_API_KEY]
            query = user_input["search_query"]

            session = async_get_clientsession(self.hass)
            client = IlMeteoClient(self._token, session)

            try:
                results = await client.search_places(query)
                if not results:
                    errors["search_query"] = "no_results"
                else:
                    self._search_results = results
                    return await self.async_step_pick_place()
            except IlMeteoAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during place search")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required("search_query"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_place(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: let user pick a place from the search results."""
        errors: dict[str, str] = {}

        # Build a dict {place_id_str: "City Name (region)"} for the selector
        place_options = {
            str(p["id"]): self._format_place(p)
            for p in self._search_results
        }

        if user_input is not None:
            place_id = user_input["place_id"]
            place_name = place_options[place_id]

            # Unique ID = token hash + place_id to allow multiple locations
            await self.async_set_unique_id(f"{DOMAIN}_{place_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=place_name,
                data={
                    CONF_API_KEY: self._token,
                    CONF_PLACE_ID: int(place_id),
                    CONF_PLACE_NAME: place_name,
                    CONF_MODEL: DEFAULT_MODEL,
                },
            )

        return self.async_show_form(
            step_id="pick_place",
            data_schema=vol.Schema(
                {
                    vol.Required("place_id"): vol.In(place_options),
                }
            ),
            errors=errors,
            description_placeholders={
                "count": str(len(self._search_results))
            },
        )

    @staticmethod
    def _format_place(place: dict) -> str:
        """Return a human-readable label for a place dict."""
        name = place.get("name", place.get("city", "Unknown"))
        region = place.get("region", place.get("province", ""))
        if region:
            return f"{name} ({region})"
        return name
