"""Constants for the iLMeteo.it integration."""

DOMAIN = "ilmeteo"
PLATFORMS = ["weather"]

# API
API_BASE_URL = "https://apigateway-prod.ilmeteov3.ilmeteo.biz/v1"
API_SEARCH_ENDPOINT = "/geography/places/search/{query}"
API_FORECAST_ENDPOINT = "/forecasts/{date}/daily/{model}/places/{place}"

# Default values
DEFAULT_MODEL = "ilmeteo"
DEFAULT_SCAN_INTERVAL = 3600  # seconds (1 hour)

# Config entries
CONF_PLACE_ID = "place_id"
CONF_PLACE_NAME = "place_name"
CONF_MODEL = "model"

# Condition mapping from iLMeteo description codes to HA condition strings
# Codes are indicative — to be refined once the real API response is available
CONDITION_MAP = {
    1:  "sunny",           # Soleggiato
    2:  "partlycloudy",    # Parzialmente nuvoloso
    3:  "cloudy",          # Nuvoloso
    4:  "cloudy",          # Molto nuvoloso
    5:  "fog",             # Nebbia
    6:  "rainy",           # Pioggia debole
    7:  "rainy",           # Pioggia moderata
    8:  "pouring",         # Pioggia forte
    9:  "lightning-rainy", # Temporale
    10: "snowy",           # Neve
    11: "snowy-rainy",     # Pioggia e neve miste
    12: "hail",            # Grandine
    13: "windy",           # Ventoso
    14: "fog",             # Nebbia fitta
}
