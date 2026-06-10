"""DataUpdateCoordinator for iLMeteo.it."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IlMeteoApiError, IlMeteoClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IlMeteoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches forecast data from iLMeteo and caches it."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: IlMeteoClient,
        place_id: int,
        place_name: str,
        model: str,
    ) -> None:
        self.client = client
        self.place_id = place_id
        self.place_name = place_name
        self.model = model

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{place_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh forecast data from the API."""
        try:
            data = await self.client.get_forecast(
                place_id=self.place_id,
                model=self.model,
            )
            _LOGGER.debug("Received forecast data for %s: %s", self.place_name, data)
            return data
        except IlMeteoApiError as err:
            raise UpdateFailed(f"iLMeteo API error: {err}") from err
