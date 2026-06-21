"""Diagnostics support for the iLMeteo.it integration.

No redaction needed: public scraping, no API token.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CITTA, CONF_PLACE_NAME, DOMAIN
from .coordinator import IlMeteoCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Tracked location, last update status, and cached box data."""
    coordinator: IlMeteoCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": {
            "citta": entry.data.get(CONF_CITTA),
            "place_name": entry.data.get(CONF_PLACE_NAME),
        },
        "last_update_success": coordinator.last_update_success,
        "last_exception": (
            str(coordinator.last_exception) if coordinator.last_exception else None
        ),
        "data": coordinator.data,
    }
