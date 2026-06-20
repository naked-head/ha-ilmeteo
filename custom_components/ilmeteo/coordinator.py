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


class IlMeteoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and cache weather data from three complementary box widgets:

    - ``current``: real-time conditions (type=real1) — a genuine current
      reading, not a forecast slot, so it never goes stale between the
      fixed 3-hour marks.
    - ``daily``: official daily min/max + precipitation probability
      (type=day1) — computed by iLMeteo from their full model run, far more
      accurate than deriving min/max from the sparse 3-hourly samples.
    - ``days``: 3-hourly forecast detail (type=tri1) — wind, humidity,
      visibility, wind chill, used for the hourly forecast.
    """

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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from all three box widgets."""
        try:
            current = await self.scraper.fetch_current()
        except IlMeteoError as err:
            raise UpdateFailed(f"iLMeteo real-time fetch error: {err}") from err

        try:
            daily = await self.scraper.fetch_daily_summary(DEFAULT_NUM_DAYS)
        except IlMeteoError as err:
            raise UpdateFailed(f"iLMeteo daily summary fetch error: {err}") from err

        try:
            days = await self.scraper.fetch_forecast(DEFAULT_NUM_DAYS)
        except IlMeteoError as err:
            raise UpdateFailed(f"iLMeteo hourly forecast fetch error: {err}") from err

        _LOGGER.debug(
            "Fetched data for %s: current=%s, %s daily summaries, %s hourly days",
            self.place_name,
            current,
            len(daily),
            len(days),
        )
        return {"current": current, "daily": daily, "days": days}
