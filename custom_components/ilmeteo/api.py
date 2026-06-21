"""iLMeteo.it box-widget scraper client."""
from __future__ import annotations

import html
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BOX_BASE_URL = "https://www.ilmeteo.it/box/previsioni.php"

# type=tri1 -> triorario (3-hourly) box layout
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
    """Async client for the iLMeteo box widgets."""

    def __init__(self, citta: str | int, session: aiohttp.ClientSession) -> None:
        self._citta = str(citta)
        self._session = session

    async def fetch_day(self, day: int = 0) -> dict[str, Any]:
        """tri1 box, single day (g=day, 0=today)."""
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
        """tri1 box, multiple consecutive days."""
        days = []
        for g in range(num_days):
            try:
                day = await self.fetch_day(g)
                if day.get("hours"):
                    days.append(day)
            except IlMeteoError as err:
                _LOGGER.warning("Failed to fetch day %s: %s", g, err)
                break
        if not days:
            raise IlMeteoError("No forecast days could be retrieved")
        return days

    async def fetch_current(self) -> dict[str, Any]:
        """real1 box: true current-hour conditions."""
        text = await self._get_box(type_="real1")
        return parse_real1(text)

    async def fetch_daily_summary(self, num_days: int = 6) -> list[dict[str, Any]]:
        """day1 box: official daily min/max + precip probability."""
        text = await self._get_box(type_="day1", days=num_days)
        return parse_day1(text)

    async def _get_box(self, type_: str, **extra: Any) -> str:
        """Fetch a box widget page and return raw HTML."""
        params = dict(_DEFAULT_PARAMS)
        params["citta"] = self._citta
        params["type"] = type_
        params.update({k: str(v) for k, v in extra.items()})

        try:
            async with self._session.get(
                BOX_BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise IlMeteoError(f"HTTP {resp.status} from box endpoint")
                return await resp.text()
        except aiohttp.ClientError as err:
            raise IlMeteoError(f"Connection error: {err}") from err


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def parse_box(html_text: str) -> dict[str, Any]:
    """Parse the tri1 box into {city, date, hours: [...]}."""
    result: dict[str, Any] = {"city": None, "date": None, "hours": []}

    # City + date
    title_match = re.search(r'<div class="left">(.*?)</div>', html_text, re.S)
    if title_match:
        block = title_match.group(1)
        city_m = re.search(r"<a[^>]*>(.*?)</a>", block, re.S)
        if city_m:
            result["city"] = _clean(city_m.group(1))
        date_m = re.search(r"(\d{2}/\d{2}/\d{4})", block)
        if date_m:
            result["date"] = date_m.group(1)

    # Hourly rows
    rows = re.findall(r'<tr class="tb-riga[12]">(.*?)</tr>', html_text, re.S)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 9:
            continue

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
    """Extract the first decimal number from a cell."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    m = re.search(r"(-?\d+[.,]?\d*)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_wind(cell: str) -> tuple[str | None, float | None, str | None]:
    """Parse a wind cell, e.g. 'NW 5 km/h<br>debole'."""
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


# 16-point compass -> degrees
WIND_DIR_DEGREES = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
    "O": 270, "NO": 315, "NNO": 337.5, "ONO": 292.5,
    "OSO": 247.5, "SO": 225, "SSO": 202.5,
}


def wind_bearing(direction: str | None) -> float | None:
    """Compass abbreviation -> degrees."""
    if not direction:
        return None
    return WIND_DIR_DEGREES.get(direction.upper())


def parse_real1(html_text: str) -> dict[str, Any]:
    """Parse the real1 box into current-conditions fields."""
    result: dict[str, Any] = {
        "condition_text": None,
        "condition_code": None,
        "hour": None,
        "temperature": None,
        "humidity": None,
        "wind_dir": None,
        "wind_speed": None,
        "wind_desc": None,
    }

    code_m = re.search(r"ss-small(\d+\w*)", html_text)
    if code_m:
        result["condition_code"] = code_m.group(1)

    # Isolate the "situazione" cell to avoid an unrelated <a> earlier in the page
    block_m = re.search(r'<td class="situazione">(.*?)</td>', html_text, re.S)
    block = block_m.group(1) if block_m else html_text
    text = _clean(block)

    hour_m = re.search(r"ore\s+(\d{1,2}:\d{2})", text)
    if hour_m:
        result["hour"] = hour_m.group(1)

    cond_m = re.match(r"(.*?)\s+ore\s+\d", text)
    if cond_m:
        result["condition_text"] = cond_m.group(1).strip()

    temp_m = re.search(r"Temperatura:\s*(-?\d+[.,]?\d*)", text)
    if temp_m:
        result["temperature"] = float(temp_m.group(1).replace(",", "."))

    hum_m = re.search(r"Umidit[àa]:\s*(\d+[.,]?\d*)", text)
    if hum_m:
        result["humidity"] = float(hum_m.group(1).replace(",", "."))

    wind_m = re.search(
        r"Vento:\s*([a-zàèìòù]+)\s*-\s*([A-Z]+)\s+(\d+[.,]?\d*)\s*km/h",
        text,
        re.I,
    )
    if wind_m:
        result["wind_desc"] = wind_m.group(1).lower()
        result["wind_dir"] = wind_m.group(2).upper()
        result["wind_speed"] = float(wind_m.group(3).replace(",", "."))

    if result["temperature"] is None:
        raise IlMeteoParseError("Could not parse real1 box (layout changed?)")

    return result


def parse_day1(html_text: str) -> list[dict[str, Any]]:
    """Parse the day1 box into a list of per-day summaries."""
    days: list[dict[str, Any]] = []
    blocks = re.findall(r"<!-- day:begin -->(.*?)<!-- day:end -->", html_text, re.S)

    for block in blocks:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", block, re.S)
        if len(cells) < 6:
            continue

        day_label = _clean(cells[0])

        code = None
        code_m = re.search(r"ss-small(\d+\w*)", cells[1])
        if code_m:
            code = code_m.group(1)

        tmin = _num(cells[2])
        tmax = _num(cells[3])

        wind_dir = _clean(cells[4]) or None
        wind_speed = _num(cells[5])

        # Precip % cell has nested markup; search cleaned full block instead
        # of an indexed cell to avoid both cell-count and width="100%" traps.
        precip_prob = None
        prob_m = re.search(r"(\d+)\s*%", _clean(block))
        if prob_m:
            precip_prob = float(prob_m.group(1))

        days.append(
            {
                "day_label": day_label,
                "condition_code": code,
                "temp_min": tmin,
                "temp_max": tmax,
                "wind_dir": wind_dir,
                "wind_speed": wind_speed,
                "precipitation_probability": precip_prob,
            }
        )

    if not days:
        raise IlMeteoParseError("Could not parse day1 box (layout changed?)")

    return days
