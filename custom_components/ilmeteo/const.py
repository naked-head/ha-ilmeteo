"""Constants for the iLMeteo.it integration."""

DOMAIN = "ilmeteo"
PLATFORMS = ["weather", "sensor"]

DEFAULT_SCAN_INTERVAL = 1800  # seconds (30 minutes)
DEFAULT_NUM_DAYS = 6

# Config entry keys (entry.data — set once at creation/reconfigure)
CONF_CITTA = "citta"
CONF_PLACE_NAME = "place_name"
CONF_SITE_NUMBER = "site_number"

# Config entry options keys (entry.options — user-adjustable via Options flow)
OPT_ENABLED_SENSORS = "enabled_sensors"

# Identifiers for the optional dedicated sensors, used both as the
# entry.options list values and as unique_id/translation_key suffixes.
SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_PRECIPITATION_PROBABILITY = "precipitation_probability"
SENSOR_WIND_SPEED = "wind_speed"

ALL_OPTIONAL_SENSORS = [
    SENSOR_TEMPERATURE,
    SENSOR_HUMIDITY,
    SENSOR_PRECIPITATION_PROBABILITY,
    SENSOR_WIND_SPEED,
]

# ---------------------------------------------------------------------------
# Condition mapping
#
# The box widget exposes a numeric sprite code (ss-smallN) plus an Italian
# text label. Day codes are 1..24; night variants are the same icon + 100
# (e.g. 3 = "Poco nuvoloso" day, 103 = night). We map the Italian text to HA
# conditions (robust to icon renumbering) and use the >100 offset only to
# switch a clear sky between 'sunny' and 'clear-night'.
#
# HA valid conditions: clear-night, cloudy, fog, hail, lightning,
# lightning-rainy, partlycloudy, pouring, rainy, snowy, snowy-rainy, sunny,
# windy, windy-variant, exceptional.
# ---------------------------------------------------------------------------

# Italian label (lowercased) -> HA condition
CONDITION_TEXT_MAP = {
    "sereno": "sunny",
    "poco nuvoloso": "partlycloudy",
    "parzialmente nuvoloso": "partlycloudy",
    "nubi sparse": "partlycloudy",
    "velato": "partlycloudy",
    "poco velato": "partlycloudy",
    "nuvoloso": "cloudy",
    "molto nuvoloso": "cloudy",
    "coperto": "cloudy",
    "nebbia": "fog",
    "foschia": "fog",
    "pioggia debole": "rainy",
    "pioggia": "rainy",
    "pioggia moderata": "rainy",
    "pioviggine": "rainy",
    "pioggia forte": "pouring",
    "rovesci": "pouring",
    "rovesci di pioggia": "pouring",
    "temporale": "lightning-rainy",
    "temporali": "lightning-rainy",
    "temporale forte": "lightning-rainy",
    "neve": "snowy",
    "neve debole": "snowy",
    "nevischio": "snowy",
    "pioggia e neve": "snowy-rainy",
    "pioggia mista a neve": "snowy-rainy",
    "grandine": "hail",
    "ventoso": "windy",
}

# Fallback by numeric code (day base codes). Only used if the text label is
# unknown. Refine as more codes are observed in the wild.
CONDITION_CODE_MAP = {
    1: "sunny",
    2: "partlycloudy",
    3: "partlycloudy",
    4: "cloudy",
    5: "cloudy",
    6: "fog",
    7: "rainy",
    8: "rainy",
    9: "pouring",
    10: "lightning-rainy",
    11: "snowy",
    12: "snowy-rainy",
    13: "hail",
}


def map_condition(text: str | None, code: str | None) -> str | None:
    """Resolve an HA condition from the Italian label and/or sprite code.

    Night handling: sprite codes >= 100 are night variants. A clear sky at
    night must be 'clear-night' rather than 'sunny'.
    """
    is_night = False
    base_code = None
    if code:
        digits = "".join(ch for ch in code if ch.isdigit())
        if digits:
            num = int(digits)
            if num >= 100:
                is_night = True
                num -= 100
            base_code = num

    condition = None
    if text:
        condition = CONDITION_TEXT_MAP.get(text.strip().lower())
    if condition is None and base_code is not None:
        condition = CONDITION_CODE_MAP.get(base_code)

    if is_night and condition == "sunny":
        return "clear-night"
    return condition
