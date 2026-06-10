"""iLMeteo.it API client."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE_URL, DEFAULT_MODEL

_LOGGER = logging.getLogger(__name__)


class IlMeteoApiError(Exception):
    """Generic API error."""


class IlMeteoAuthError(IlMeteoApiError):
    """Authentication error (invalid or missing token)."""


class IlMeteoClient:
    """Async HTTP client for the iLMeteo API Gateway."""

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        self._token = token
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def search_places(self, query: str) -> list[dict[str, Any]]:
        """Search for places by name. Returns a list of matching locations."""
        url = f"{API_BASE_URL}/geography/places/search/{query}"
        return await self._get(url)

    async def get_forecast(
        self,
        place_id: int | str,
        forecast_date: date | None = None,
        model: str = DEFAULT_MODEL,
    ) -> dict[str, Any]:
        """
        Fetch daily forecast for a given place.

        Args:
            place_id: Numeric ID of the locality (from search_places).
            forecast_date: The starting date for the forecast (defaults to today).
            model: Forecast model name (default: 'ilmeteo').

        Returns:
            Raw JSON dict from the API.
        """
        if forecast_date is None:
            forecast_date = date.today()
        date_str = forecast_date.strftime("%Y-%m-%d")
        url = f"{API_BASE_URL}/forecasts/{date_str}/daily/{model}/places/{place_id}"
        return await self._get(url)

    async def _get(self, url: str) -> Any:
        """Perform a GET request and return parsed JSON."""
        _LOGGER.debug("GET %s", url)
        try:
            async with self._session.get(url, headers=self._headers) as resp:
                if resp.status == 401:
                    raise IlMeteoAuthError("Invalid or expired API token")
                if resp.status == 403:
                    raise IlMeteoAuthError("Token not authorized for this resource")
                if resp.status != 200:
                    text = await resp.text()
                    raise IlMeteoApiError(
                        f"Unexpected status {resp.status}: {text[:200]}"
                    )
                return await resp.json()
        except aiohttp.ClientError as err:
            raise IlMeteoApiError(f"Connection error: {err}") from err
