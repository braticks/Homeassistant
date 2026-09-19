"""Constants for the Tuščias bakas integration."""

DOMAIN = "tusciasbakas"
NAME = "Tuščias bakas"

API_URL = "https://tusciasbakas.lt/api/v1/stations.json"
DEFAULT_RADIUS_KM = 10.0
DEFAULT_FUEL_TYPE = "petrol_95"
DEFAULT_UPDATE_MINUTES = 60

# First-run default: only these major networks are visible.
DEFAULT_VISIBLE_NETWORK_PATTERNS = (
    "circle k",
    "circlek",
    "neste",
    "viada",
    "emsi",
)

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

ATTRIBUTION = (
    "Duomenys: Lietuvos energetikos agentūra (LEA) ir degalines valdančios "
    "įmonės, per tusciasbakas.lt"
)
