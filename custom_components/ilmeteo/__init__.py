"""The iLMeteo.it integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IlMeteoClient
from .const import CONF_MODEL, CONF_PLACE_ID, CONF_PLACE_NAME, DOMAIN
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iLMeteo.it from a config entry."""
    session = async_get_clientsession(hass)
    client = IlMeteoClient(entry.data[CONF_API_KEY], session)

    coordinator = IlMeteoCoordinator(
        hass=hass,
        client=client,
        place_id=entry.data[CONF_PLACE_ID],
        place_name=entry.data[CONF_PLACE_NAME],
        model=entry.data.get(CONF_MODEL, "ilmeteo"),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
