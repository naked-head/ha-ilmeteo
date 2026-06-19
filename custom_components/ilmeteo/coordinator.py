"""DataUpdateCoordinator for iLMeteo.it (box scraper)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IlMeteoError, IlMeteoScraper
from .const import DEFAULT_NUM_DAYS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IlMeteoCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Fetch and cache the multi-day forecast from the iLMeteo box widget."""

    def __init__(
        self,
        hass: HomeAssistant,
        scraper: IlMeteoScraper,
        citta: str,
        place_name: str,
    ) -> None:
        self.scraper = scraper
        self.citta = citta
        self.place_name = place_name

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{citta}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch fresh forecast data. Returns a list of day dicts."""
        try:
            days = await self.scraper.fetch_forecast(DEFAULT_NUM_DAYS)
            _LOGGER.debug(
                "Fetched %s forecast days for %s", len(days), self.place_name
            )
            return days
        except IlMeteoError as err:
            raise UpdateFailed(f"iLMeteo scrape error: {err}") from err
