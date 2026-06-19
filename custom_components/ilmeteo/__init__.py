"""The iLMeteo.it integration (box-widget scraper backend)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IlMeteoScraper
from .const import CONF_CITTA, CONF_PLACE_NAME, DOMAIN
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iLMeteo.it from a config entry."""
    session = async_get_clientsession(hass)
    scraper = IlMeteoScraper(entry.data[CONF_CITTA], session)

    coordinator = IlMeteoCoordinator(
        hass=hass,
        scraper=scraper,
        citta=str(entry.data[CONF_CITTA]),
        place_name=entry.data[CONF_PLACE_NAME],
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
