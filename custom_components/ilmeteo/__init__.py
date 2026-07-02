"""The iLMeteo.it integration (box-widget scraper backend)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alert_manager import IlMeteoAlertManager
from .api import IlMeteoScraper
from .const import (
    CONF_CITTA,
    CONF_PLACE_NAME,
    DEFAULT_ALERT_NOTIFICATIONS,
    DOMAIN,
    OPT_ALERT_NOTIFICATIONS,
    OPT_DPC_ALERT_ENTITY,
    OPT_DPC_VIGILANCE_ENTITY,
    OPT_NOTIFY_TARGETS,
)
from .coordinator import BOX_TYPES, IlMeteoCoordinator, issue_id_for

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER, Platform.SENSOR]

# Keyed separately from hass.data[DOMAIN] (which holds coordinators, keyed by
# entry_id, and is relied upon as-is by weather.py/sensor.py/diagnostics.py).
_ALERT_MANAGERS_KEY = f"{DOMAIN}_alert_managers"


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

    if entry.options.get(OPT_ALERT_NOTIFICATIONS, DEFAULT_ALERT_NOTIFICATIONS):
        alert_manager = IlMeteoAlertManager(
            hass=hass,
            coordinator=coordinator,
            entry_id=entry.entry_id,
            citta=str(entry.data[CONF_CITTA]),
            place_name=entry.data[CONF_PLACE_NAME],
            dpc_entity_id=entry.options.get(OPT_DPC_ALERT_ENTITY) or None,
            dpc_vigilance_entity_id=entry.options.get(OPT_DPC_VIGILANCE_ENTITY) or None,
            notify_targets=entry.options.get(OPT_NOTIFY_TARGETS) or [],
        )
        await alert_manager.async_start()
        hass.data.setdefault(_ALERT_MANAGERS_KEY, {})[entry.entry_id] = alert_manager

    # Reload on options change (e.g. enabled sensors, alert toggle) so
    # platforms and the alert manager re-run with the new options.
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
        alert_manager = hass.data.get(_ALERT_MANAGERS_KEY, {}).pop(entry.entry_id, None)
        if alert_manager is not None:
            alert_manager.async_stop()
        # Clear any open Repair issues for this location
        citta = str(entry.data[CONF_CITTA])
        for box_type in BOX_TYPES:
            ir.async_delete_issue(hass, DOMAIN, issue_id_for(citta, box_type))
    return unload_ok