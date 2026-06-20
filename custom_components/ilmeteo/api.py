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

    async def fetch_current(self) -> dict[str, Any]:
        """Fetch the real-time conditions box (type=real1).

        Unlike the 3-hourly box, this reflects the actual current hour, not
        a fixed forecast slot, so it never goes stale or "jumps forward"
        once a slot elapses.
        """
        text = await self._get_box(type_="real1")
        return parse_real1(text)

    async def fetch_daily_summary(self, num_days: int = 6) -> list[dict[str, Any]]:
        """Fetch the official daily min/max box (type=day1) for all days at once.

        This reflects iLMeteo's own daily aggregate (computed from their full
        model run, not just the 5 samples in the 3-hourly box), so the daily
        low in particular is materially more accurate than what can be
        derived from the tri1 box alone.
        """
        text = await self._get_box(type_="day1", days=num_days)
        return parse_day1(text)

    async def _get_box(self, type_: str, **extra: Any) -> str:
        """Fetch a box widget page of the given type and return raw HTML."""
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
# Pure HTML parsing (no HA / aiohttp dependency, easy to unit-test)
# ---------------------------------------------------------------------------

def parse_box(html_text: str) -> dict[str, Any]:
    """Parse a single box-widget HTML page into a structured dict.

    Uses regex rather than BeautifulSoup to avoid adding a dependency to the
    integration (HA discourages heavy requirements). The markup is stable and
    line-oriented, so regex is adequate and fast.
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


def parse_real1(html_text: str) -> dict[str, Any]:
    """Parse the real-time conditions box (type=real1).

    Markup (simplified, see tests/fixtures/real1_roma.html for the full
    real example this was built from):

        <td class="simbolo"><span class="... ss-smallN ..."></span></td>
        <td class="situazione">
            <div class="previsione">
                <a ...>CONDITION TEXT</a>
                <span>ore HH:MM*</span>
            </div>
            Temperatura: <b style="color:red">NN&deg;C</b><br>
            Umidit&agrave;: NN%<br>
            Vento: DESC - DIR NN&nbsp;km/h
        </td>

    Two things make this trickier than it looks: the <b> around the
    temperature carries an inline style (no bare '<b>' to match), and the
    page uses HTML entities (&agrave;, &nbsp;, &deg;) rather than literal
    characters. We isolate the relevant cell, strip tags and unescape
    entities first (via _clean()), then regex the resulting plain text —
    the same robust approach used for the tri1/day1 boxes — rather than
    pattern-matching the raw markup directly.
    """
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

    # Condition sprite code, for day/night handling consistent with the
    # tri1/day1 boxes (the >100 = night convention).
    code_m = re.search(r"ss-small(\d+\w*)", html_text)
    if code_m:
        result["condition_code"] = code_m.group(1)

    # Isolate the "situazione" cell specifically — the page also has an
    # unrelated <a> for the city name in the title bar, earlier in the
    # document, which a generic "first <a>" match would wrongly pick up.
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

    # "Vento: debole - WNW 8 km/h" (after cleaning, &nbsp; is a real space)
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
    """Parse the official daily min/max box (type=day1).

    Each day is a <!-- day:begin --> ... <!-- day:end --> block containing a
    day-name link, a condition sprite, T min/max cells, wind direction +
    speed, and a precipitation-probability mini bar chart with the % as
    text (e.g. '&nbsp;5%' or '25%&nbsp;').

    Returns a list of dicts (ordered today -> future), one per day, with:
    day_label, condition_code, temp_min, temp_max, wind_dir, wind_speed,
    precipitation_probability.
    """
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

        # The precipitation-probability cell contains a nested mini-table
        # (a colored bar + a text cell) whose own <td> tags throw off simple
        # cell-index counting, AND whose inline style can contain its own
        # misleading '%' (e.g. width='100%'). Strip all tags first so only
        # visible text remains, then search that for the real figure.
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
