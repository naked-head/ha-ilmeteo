"""DataUpdateCoordinator for iLMeteo.it (box scraper)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable, TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IlMeteoError, IlMeteoParseError, IlMeteoScraper
from .const import DEFAULT_NUM_DAYS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

# The three box types we scrape, used to build stable Repair issue IDs.
BOX_TYPES = ("real1", "day1", "tri1")


def issue_id_for(citta: str, box_type: str) -> str:
    """Build the stable Repair issue_id for a given location + box type."""
    return f"box_parse_error_{citta}_{box_type}"


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

    Each box is fetched and parsed independently: a failure on one (most
    likely a network hiccup, or — more interestingly — an upstream markup
    change) does not take the other two down with it. The coordinator falls
    back to the last successfully parsed data for that specific box rather
    than failing the whole update.

    A *parsing* failure specifically (as opposed to a network error) raises
    a persistent, visible Home Assistant Repair issue, since it usually
    means iLMeteo changed the box's HTML and the integration needs an
    update — something worth surfacing prominently rather than leaving
    buried in the log. The issue clears itself automatically the next time
    that box parses successfully again.
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
        self._last_good: dict[str, Any] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{citta}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from all three box widgets, independently."""
        current = await self._fetch_box("real1", self.scraper.fetch_current, default={})
        daily = await self._fetch_box(
            "day1",
            lambda: self.scraper.fetch_daily_summary(DEFAULT_NUM_DAYS),
            default=[],
        )
        days = await self._fetch_box(
            "tri1",
            lambda: self.scraper.fetch_forecast(DEFAULT_NUM_DAYS),
            default=[],
        )

        if not current and not daily and not days:
            # Every box failed (and there's no previous data to fall back
            # on either) — nothing usable at all, so this is a hard failure.
            raise UpdateFailed(
                f"All iLMeteo box fetches failed for {self.place_name}"
            )

        _LOGGER.debug(
            "Fetched data for %s: current=%s, %s daily summaries, %s hourly days",
            self.place_name,
            current,
            len(daily),
            len(days),
        )
        return {"current": current, "daily": daily, "days": days}

    async def _fetch_box(
        self,
        box_type: str,
        fetch_fn: Callable[[], Awaitable[T]],
        default: T,
    ) -> T:
        """Fetch+parse a single box, managing its Repair issue and fallback.

        - On success: clears any open Repair issue for this box, caches the
          result as the new "last known good" value, and returns it.
        - On a parsing error (layout change): raises a Repair issue and
          falls back to the last known-good value for this box (or
          ``default`` if there isn't one yet).
        - On a network/transient error: same fallback, but *no* Repair
          issue — a single missed poll isn't worth alarming the user about.
        """
        issue_id = issue_id_for(self.citta, box_type)
        try:
            result = await fetch_fn()
        except IlMeteoParseError as err:
            _LOGGER.warning(
                "Parse error on the %s box for %s (upstream layout may have "
                "changed): %s",
                box_type,
                self.place_name,
                err,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="box_parse_error",
                translation_placeholders={
                    "place_name": self.place_name,
                    "box_type": box_type,
                },
                learn_more_url="https://github.com/naked-head/ha-ilmeteo/issues",
            )
            return self._last_good.get(box_type, default)
        except IlMeteoError as err:
            _LOGGER.debug(
                "Fetch error on the %s box for %s: %s", box_type, self.place_name, err
            )
            return self._last_good.get(box_type, default)
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._last_good[box_type] = result
            return result