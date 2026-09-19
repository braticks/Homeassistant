"""Constants for the Tuščias bakas integration."""

DOMAIN = "tusciasbakas"
NAME = "Tuščias bakas"

KUROHUDAS_BASE_URL = "https://www.kurohudas.lt"
DEFAULT_CITY = "Kaunas"
DEFAULT_RADIUS_KM = 10.0
DEFAULT_FUEL_TYPE = "petrol_95"
DEFAULT_UPDATE_MINUTES = 60

# Kurohudas city pages contain stations within 12 km of the selected city.
MAX_RADIUS_KM = 12.0

# First-run default: only these major networks are visible.
DEFAULT_VISIBLE_NETWORK_PATTERNS = (
    "circle k",
    "circlek",
    "neste",
    "viada",
    "emsi",
)

CONF_CITY = "city"
CONF_RADIUS_KM = "radius_km"
CONF_FUEL_TYPE = "fuel_type"
CONF_DISCOUNT_RULES = "discount_rules"
CONF_DISCOUNTS = "discounts"
CONF_EXCLUDED_NETWORKS = "excluded_networks"
CONF_UPDATE_MINUTES = "update_minutes"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

FUEL_TYPES = {
    "petrol_95": "Benzinas 95",
    "diesel": "Dyzelinas",
    "lpg": "SND (dujos)",
}

ATTRIBUTION = "Kainų šaltinis: Kurohudas.lt"
