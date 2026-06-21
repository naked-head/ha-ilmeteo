"""The iLMeteo.it integration (box-widget scraper backend)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IlMeteoScraper
from .const import CONF_CITTA, CONF_PLACE_NAME, DOMAIN
from .coordinator import BOX_TYPES, IlMeteoCoordinator, issue_id_for

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER, Platform.SENSOR]


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

    # Reload whenever the Options flow is submitted (e.g. the user changes
    # which optional sensors are enabled), so sensor.py re-runs and picks
    # up the new selection — Home Assistant does not do this automatically.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Clear any Repair issues left open for this location so removing
        # the integration doesn't leave orphaned warnings behind.
        citta = str(entry.data[CONF_CITTA])
        for box_type in BOX_TYPES:
            ir.async_delete_issue(hass, DOMAIN, issue_id_for(citta, box_type))
    return unload_ok
