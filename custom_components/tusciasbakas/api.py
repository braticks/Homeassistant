"""Client and tolerant parser for the public Tuščias bakas JSON API."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_URL


class TusciasBakasApiError(Exception):
    """Base API error."""


@dataclass(slots=True)
class Station:
    """Normalized fuel station record."""

    name: str
    network: str
    address: str
    latitude: float
    longitude: float
    prices: dict[str, float]


@dataclass(slots=True)
class ApiData:
    """Normalized API result."""

    stations: list[Station]
    data_date: str | None = None


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    normalized = {_norm_key(k): v for k, v in mapping.items()}
    for key in keys:
        if _norm_key(key) in normalized:
            value = normalized[_norm_key(key)]
            if value not in (None, ""):
                return value
    return None


FUEL_ALIASES: dict[str, tuple[str, ...]] = {
    "petrol_95": (
        "95", "p95", "a95", "e5", "e10", "petrol95", "petrol_95", "gasoline95",
        "gasoline_95", "benzinas95", "benzinas_95", "benzinas", "unleaded95",
    ),
    "diesel": (
        "diesel", "dyzelinas", "b7", "d", "diesel_b7", "dyzelinas_b7",
    ),
    "lpg": (
        "lpg", "snd", "dujos", "gas", "autogas", "propane", "propanas",
    ),
}


def _extract_prices(props: dict[str, Any]) -> dict[str, float]:
    containers: list[Any] = [props]
    for key in ("prices", "price", "fuels", "fuel_prices", "fuelPrices"):
        val = props.get(key)
        if val is not None:
            containers.append(val)

    result: dict[str, float] = {}
    for fuel, aliases in FUEL_ALIASES.items():
        for container in containers:
            if isinstance(container, dict):
                value = _first(container, aliases)
                number = _float(value)
                if number is not None and 0.1 < number < 10:
                    result[fuel] = number
                    break
            elif isinstance(container, list):
                for item in container:
                    if not isinstance(item, dict):
                        continue
                    kind = _first(item, ("fuel", "type", "name", "product", "code"))
                    if kind is None:
                        continue
                    if _norm_key(kind) not in {_norm_key(a) for a in aliases}:
                        continue
                    number = _float(_first(item, ("price", "value", "amount")))
                    if number is not None and 0.1 < number < 10:
                        result[fuel] = number
                        break
                if fuel in result:
                    break
    return result


def _extract_station(item: Any) -> Station | None:
    if not isinstance(item, dict):
        return None

    props = item.get("properties") if isinstance(item.get("properties"), dict) else item
    props = dict(props)

    coords_obj = props.get("coordinates") or props.get("coords") or props.get("coordinate")
    if isinstance(coords_obj, dict):
        for key, value in coords_obj.items():
            props.setdefault(key, value)

    lat = _float(_first(props, ("lat", "latitude", "y", "gps_lat", "gpsLatitude")))
    lon = _float(_first(props, ("lon", "lng", "longitude", "x", "gps_lon", "gpsLongitude")))

    geometry = item.get("geometry")
    if (lat is None or lon is None) and isinstance(geometry, dict):
        coords = geometry.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lon = _float(coords[0])
            lat = _float(coords[1])

    if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    name = _first(props, ("name", "station_name", "stationName", "station", "title", "degaline"))
    network = _first(props, ("network", "brand", "company", "company_name", "operator", "operator_name", "chain", "tinklas", "imone"))
    address = _first(props, ("address", "addr", "full_address", "location", "adresas"))

    name_s = str(name or network or "Degalinė").strip()
    network_s = str(network or name or "").strip()
    address_s = str(address or "").strip()

    return Station(
        name=name_s,
        network=network_s,
        address=address_s,
        latitude=lat,
        longitude=lon,
        prices=_extract_prices(props),
    )


def parse_api_payload(payload: Any) -> ApiData:
    """Parse a few common static-JSON / GeoJSON layouts defensively."""
    data_date: str | None = None
    raw_stations: Any = payload

    if isinstance(payload, dict):
        date_value = _first(payload, ("date", "data_date", "prices_date", "updated", "updated_at", "generated_at"))
        if date_value is not None:
            data_date = str(date_value)

        for key in ("stations", "items", "features", "data", "results"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                raw_stations = candidate
                break
            if isinstance(candidate, dict):
                for subkey in ("stations", "items", "features", "results"):
                    sub = candidate.get(subkey)
                    if isinstance(sub, list):
                        raw_stations = sub
                        break
                if isinstance(raw_stations, list):
                    break

    if isinstance(raw_stations, dict):
        values = list(raw_stations.values())
        if values and all(isinstance(value, dict) for value in values):
            raw_stations = values

    if not isinstance(raw_stations, list):
        raise TusciasBakasApiError("API atsakymas neturi atpažįstamo degalinių sąrašo")

    stations = [station for item in raw_stations if (station := _extract_station(item))]
    if not stations:
        raise TusciasBakasApiError("API atsakyme nepavyko atpažinti degalinių koordinačių")

    return ApiData(stations=stations, data_date=data_date)


class TusciasBakasApi:
    """Small async API client."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_get_stations(self) -> ApiData:
        try:
            async with self._session.get(API_URL, timeout=20) as response:
                if response.status != 200:
                    raise TusciasBakasApiError(f"HTTP {response.status}")
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise TusciasBakasApiError(str(err)) from err
        return parse_api_payload(payload)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine straight-line distance in kilometres."""
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
