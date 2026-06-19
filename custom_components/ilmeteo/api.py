"""iLMeteo.it scraper client.

Since the official REST API is enterprise-only, this client scrapes the
free public "box" forecast widget that iLMeteo provides for embedding on
third-party sites:

    https://www.ilmeteo.it/box/previsioni.php?type=tri1&g=<day>&citta=<id>...

The widget is rendered server-side as static HTML (no JS required), with
each 3-hour forecast row delimited by <!-- hour:begin --> markers and a
``<tr class="tb-riga1|tb-riga2">`` structure of 9 cells.
"""
from __future__ import annotations

import html
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BOX_BASE_URL = "https://www.ilmeteo.it/box/previsioni.php"

# Fixed query params that keep the layout we parse. type=tri1 = triorario (type B).
_DEFAULT_PARAMS = {
    "type": "tri1",
    "width": "500",
    "ico": "1",
    "lang": "ita",
    "days": "6",
    "font": "Arial",
    "fontsize": "12",
    "mode": "citta",
}


class IlMeteoError(Exception):
    """Generic scraper error."""


class IlMeteoParseError(IlMeteoError):
    """Raised when the HTML structure does not match expectations."""


class IlMeteoScraper:
    """Async client that fetches and parses the iLMeteo box widget."""

    def __init__(self, citta: str | int, session: aiohttp.ClientSession) -> None:
        self._citta = str(citta)
        self._session = session

    async def fetch_day(self, day: int = 0) -> dict[str, Any]:
        """Fetch and parse a single day (g=day, 0=today)."""
        params = dict(_DEFAULT_PARAMS)
        params["citta"] = self._citta
        params["g"] = str(day)

        try:
            async with self._session.get(
                BOX_BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise IlMeteoError(f"HTTP {resp.status} from box endpoint")
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise IlMeteoError(f"Connection error: {err}") from err

        return parse_box(text)

    async def fetch_forecast(self, num_days: int = 6) -> list[dict[str, Any]]:
        """Fetch multiple consecutive days. Returns a list of parsed days."""
        days = []
        for g in range(num_days):
            try:
                day = await self.fetch_day(g)
                if day.get("hours"):
                    days.append(day)
            except IlMeteoError as err:
                _LOGGER.warning("Failed to fetch day %s: %s", g, err)
                # Stop on first failure rather than spamming requests
                break
        if not days:
            raise IlMeteoError("No forecast days could be retrieved")
        return days


# ---------------------------------------------------------------------------
# Pure HTML parsing (no HA / aiohttp dependency, easy to unit-test)
# ---------------------------------------------------------------------------

def parse_box(html_text: str) -> dict[str, Any]:
    """Parse a single box-widget HTML page into a structured dict.

    Uses regex rather than BeautifulSoup to avoid adding a dependency to the
    integration. The markup is stable and line-oriented, so regex is adequate
    and fast.
    """
    result: dict[str, Any] = {"city": None, "date": None, "hours": []}

    # --- City + date from the title block ---
    title_match = re.search(
        r'<div class="left">(.*?)</div>', html_text, re.S
    )
    if title_match:
        block = title_match.group(1)
        city_m = re.search(r"<a[^>]*>(.*?)</a>", block, re.S)
        if city_m:
            result["city"] = _clean(city_m.group(1))
        date_m = re.search(r"(\d{2}/\d{2}/\d{4})", block)
        if date_m:
            result["date"] = date_m.group(1)

    # --- Hourly rows ---
    rows = re.findall(
        r'<tr class="tb-riga[12]">(.*?)</tr>', html_text, re.S
    )
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 9:
            continue

        # Condition code from sprite class ss-smallN
        code = None
        code_m = re.search(r"ss-small(\d+\w*)", cells[1])
        if code_m:
            code = code_m.group(1)

        wind_dir, wind_speed, wind_desc = _parse_wind(cells[4])

        result["hours"].append(
            {
                "time": _clean(cells[0]),
                "condition_code": code,
                "condition_text": _clean(cells[2]),
                "temperature": _num(cells[3]),
                "wind_dir": wind_dir,
                "wind_speed": wind_speed,
                "wind_desc": wind_desc,
                "precipitation": _parse_precip(cells[5]),
                "visibility": _clean(cells[6]),
                "humidity": _num(cells[7]),
                "wind_chill": _num(cells[8]),
            }
        )

    if result["date"] is None and not result["hours"]:
        raise IlMeteoParseError("Could not parse box HTML (layout changed?)")

    return result


def _clean(text: str) -> str:
    """Strip tags, unescape entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _num(text: str) -> float | None:
    """Extract the first (signed, decimal) number from a cell."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    m = re.search(r"(-?\d+[.,]?\d*)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_wind(cell: str) -> tuple[str | None, float | None, str | None]:
    """Parse a wind cell like 'NW 5 km/h<br>debole'."""
    txt = _clean(cell)
    direction = speed = desc = None
    m = re.match(r"([A-Z]+)\s+(\d+)", txt)
    if m:
        direction = m.group(1)
        try:
            speed = float(m.group(2))
        except ValueError:
            speed = None
    desc_m = re.search(r"(debole|moderato|forte|teso|fresco|calmo)", txt, re.I)
    if desc_m:
        desc = desc_m.group(1).lower()
    return direction, speed, desc


def _parse_precip(cell: str) -> float:
    """Parse precipitation cell; '-' means 0."""
    txt = _clean(cell)
    m = re.search(r"([\d.]+)\s*mm", txt)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return 0.0
    return 0.0


# Map of Italian 16-wind-rose abbreviations to degrees
WIND_DIR_DEGREES = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
    # Italian variants sometimes use O (Ovest) instead of W
    "O": 270, "NO": 315, "NNO": 337.5, "ONO": 292.5,
    "OSO": 247.5, "SO": 225, "SSO": 202.5,
}


def wind_bearing(direction: str | None) -> float | None:
    """Convert a compass abbreviation to degrees."""
    if not direction:
        return None
    return WIND_DIR_DEGREES.get(direction.upper())
