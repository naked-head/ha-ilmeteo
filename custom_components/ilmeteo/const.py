"""Constants for the iLMeteo.it integration."""

DOMAIN = "ilmeteo"
PLATFORMS = ["weather"]

DEFAULT_SCAN_INTERVAL = 1800  # seconds (30 minutes)
DEFAULT_NUM_DAYS = 6

# Config entry keys
CONF_CITTA = "citta"
CONF_PLACE_NAME = "place_name"

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
# unknown.
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
