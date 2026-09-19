"""Official LEA fuel price API client."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from urllib.parse import urljoin

from aiohttp import ClientError, ClientSession

from .const import LEA_SITE_URL


class LeaApiError(Exception):
    """Base LEA API error."""


@dataclass(slots=True)
class Station:
    """Normalized LEA station."""

    name: str
    network: str
    company_name: str
    address: str
    latitude: float
    longitude: float
    available_fuels: set[str] = field(default_factory=set)
    prices: dict[str, float] = field(default_factory=dict)
    updated: dict[str, str] = field(default_factory=dict)
    logo_url: str | None = None


@dataclass(slots=True)
class ApiData:
    """Normalized LEA result."""

    stations: list[Station]
    data_date: str | None = None


FUEL_MAP = {
    "benzinas_95": "petrol_95",
    "dyzelinas": "diesel",
    "snd": "lpg",
}

NETWORK_PATTERNS = (
    ("circle k", "Circle K"),
    ("neste", "Neste"),
    ("viada", "Viada"),
    ("emsi", "EMSI"),
    ("orlen", "ORLEN"),
    ("baltic petroleum", "Baltic Petroleum"),
    ("jozita", "Jozita"),
    ("saurida", "Saurida"),
    ("stateta", "Stateta"),
    ("skulas", "Skulas"),
    ("alauša", "Alauša"),
    ("alausa", "Alauša"),
    ("regusa", "Regusa"),
    ("boost", "Boost Petrol"),
)


def _canonical_network(company: str, station_name: str) -> str:
    text = f"{station_name} {company}".casefold()
    for pattern, label in NETWORK_PATTERNS:
        if pattern in text:
            return label
    return station_name.strip() or company.strip() or "Degalinė"


class LeaFuelApi:
    """Client for the public LEA fuel-price frontend API."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._api_base: str | None = None
        self._token: str | None = None
        self._headers = {
            "User-Agent": "HomeAssistant TuščiasBakas integration",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        }

    async def _get_text(self, url: str) -> str:
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=30,
            ) as response:
                if response.status != 200:
                    raise LeaApiError(f"HTTP {response.status}: {url}")
                return await response.text()
        except (ClientError, TimeoutError) as err:
            raise LeaApiError(str(err)) from err

    async def _discover_api_config(self) -> None:
        """Read the API base and public read token from LEA's frontend bundle."""
        html = await self._get_text(LEA_SITE_URL)

        script_urls = [
            urljoin(LEA_SITE_URL, src)
            for src in re.findall(
                r'<script[^>]+src=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        ]

        app_bundle_url: str | None = None
        for script_url in script_urls:
            if "xlsx" in script_url or "cloudflare" in script_url:
                continue
            try:
                javascript = await self._get_text(script_url)
            except LeaApiError:
                continue
            match = re.search(
                r'["\'](?:\./)?(FuelPriceSiteApp-[A-Za-z0-9_-]+\.js)["\']',
                javascript,
            )
            if match:
                app_bundle_url = urljoin(script_url, match.group(1))
                break

        if not app_bundle_url:
            raise LeaApiError("LEA puslapyje nerastas FuelPriceSiteApp failas")

        app_js = await self._get_text(app_bundle_url)
        config = re.search(
            r'apiBase:"([^"]+)",token:"([^"]+)"',
            app_js,
        )
        if not config:
            raise LeaApiError("LEA puslapyje nerasta viešo API konfigūracija")

        self._api_base = config.group(1).rstrip("/")
        self._token = config.group(2)

    async def _request_latest(self, retry_auth: bool = True) -> dict:
        if not self._api_base or not self._token:
            await self._discover_api_config()

        assert self._api_base is not None
        assert self._token is not None

        url = f"{self._api_base}/read/prices/latest"
        headers = {
            **self._headers,
            "Authorization": f"Bearer {self._token}",
        }

        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=30,
            ) as response:
                if response.status == 401 and retry_auth:
                    self._api_base = None
                    self._token = None
                    await self._discover_api_config()
                    return await self._request_latest(retry_auth=False)
                if response.status != 200:
                    raise LeaApiError(f"LEA API HTTP {response.status}")
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise LeaApiError(str(err)) from err

    async def async_get_stations(self) -> ApiData:
        payload = await self._request_latest()
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise LeaApiError("LEA API grąžino netikėtą duomenų formatą")

        grouped: dict[str, Station] = {}
        latest_date: str | None = None

        for row in rows:
            if not isinstance(row, dict):
                continue

            try:
                latitude = float(row.get("latitude"))
                longitude = float(row.get("longitude"))
            except (TypeError, ValueError):
                continue

            company = str(row.get("company_name") or "").strip()
            station_name = str(row.get("gas_station_name") or "").strip()
            address = str(row.get("address") or "").strip()
            network = _canonical_network(company, station_name)

            key = "|".join(
                (
                    company.casefold(),
                    station_name.casefold(),
                    address.casefold(),
                    f"{latitude:.6f}",
                    f"{longitude:.6f}",
                )
            )
            station = grouped.get(key)
            if station is None:
                station = Station(
                    name=station_name or network,
                    network=network,
                    company_name=company,
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    logo_url=row.get("logo_url") or None,
                )
                grouped[key] = station
            elif not station.logo_url and row.get("logo_url"):
                station.logo_url = str(row["logo_url"])

            for raw_fuel in row.get("fuel_types") or []:
                mapped = FUEL_MAP.get(str(raw_fuel))
                if mapped:
                    station.available_fuels.add(mapped)

            raw_fuel = str(row.get("fuel_type") or "")
            fuel = FUEL_MAP.get(raw_fuel)
            if not fuel:
                continue
            station.available_fuels.add(fuel)

            submitted_at = str(row.get("submitted_at") or "")
            if submitted_at:
                station.updated[fuel] = submitted_at
                date = submitted_at[:10]
                if date and (latest_date is None or date > latest_date):
                    latest_date = date

            raw_price = row.get("price")
            if raw_price is None:
                continue
            try:
                price = float(str(raw_price).replace(",", "."))
            except ValueError:
                continue
            if 0 < price < 10:
                station.prices[fuel] = price

        if not grouped:
            raise LeaApiError("LEA API negrąžino degalinių")

        last_updated = str(payload.get("last_updated") or "")
        data_date = last_updated[:10] if last_updated else latest_date
        return ApiData(stations=list(grouped.values()), data_date=data_date)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine straight-line distance in kilometres."""
    import math

    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
