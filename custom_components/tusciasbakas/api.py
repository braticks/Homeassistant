"""Kurohudas.lt client for Tuščias bakas."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

from aiohttp import ClientError, ClientSession

from .const import KUROHUDAS_BASE_URL


class KurohudasApiError(Exception):
    """Base Kurohudas client error."""


@dataclass(slots=True)
class Station:
    """Normalized Kurohudas station."""

    name: str
    network: str
    address: str
    prices: dict[str, float]
    detail_url: str
    updated: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class ApiData:
    """Normalized Kurohudas city result."""

    stations: list[Station]
    data_date: str | None = None


KNOWN_NETWORKS = (
    "Baltic Petroleum",
    "Circle K",
    "Boost Petrol",
    "Neste",
    "EMSI",
    "ORLEN",
    "Orlen",
    "Viada",
    "Jozita",
    "Stateta",
    "Skulas",
    "Saurida",
    "Alauša",
    "Alausa",
    "Regusa",
    "Lanx",
)

_UPDATED_RE = re.compile(
    r"(Šiandien|Vakar|Užvakar|\d{4}-\d{2}-\d{2})\s*$",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"Kainų data\s*[—-]\s*(\d{4}-\d{2}-\d{2})")
_COORD_RE = re.compile(
    r"destination=([-+]?\d+(?:\.\d+)?)%2C([-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class _FuelTableParser(HTMLParser):
    """Extract station table rows from Kurohudas HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_tr = False
        self.in_cell = False
        self.current_cells: list[str] = []
        self.current_cell_parts: list[str] = []
        self.current_href: str | None = None
        self.rows: list[tuple[list[str], str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_tr = True
            self.current_cells = []
            self.current_href = None
        elif self.in_tr and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell_parts = []
        elif self.in_tr and self.in_cell and tag == "a" and self.current_href is None:
            href = dict(attrs).get("href")
            if href and "/degalines/" in href:
                self.current_href = href

    def handle_endtag(self, tag: str) -> None:
        if self.in_tr and tag in {"td", "th"} and self.in_cell:
            value = " ".join("".join(self.current_cell_parts).split())
            self.current_cells.append(value)
            self.current_cell_parts = []
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.current_cells:
                self.rows.append((self.current_cells, self.current_href))
            self.in_tr = False
            self.in_cell = False

    def handle_data(self, data: str) -> None:
        if self.in_tr and self.in_cell:
            self.current_cell_parts.append(data)


def _price(value: str) -> float | None:
    text = value.strip().replace(",", ".")
    if text in {"", "-", "—"}:
        return None
    try:
        number = float(re.sub(r"[^0-9.]", "", text))
    except ValueError:
        return None
    return number if 0.1 < number < 10 else None


def _strip_updated(text: str) -> tuple[str, str | None]:
    match = _UPDATED_RE.search(text)
    if not match:
        return text.strip(), None
    return text[: match.start()].strip(" ,"), match.group(1)


def _network_and_address(text: str) -> tuple[str, str]:
    clean = text.strip()
    for network in sorted(KNOWN_NETWORKS, key=len, reverse=True):
        if clean.casefold().startswith(network.casefold()):
            address = clean[len(network):].strip(" ,-")
            canonical = "ORLEN" if network.casefold() == "orlen" else network
            return canonical, address

    first, _, rest = clean.partition(" ")
    return first or "Degalinė", rest.strip()


def parse_city_page(html: str) -> ApiData:
    """Parse the Kurohudas city table."""
    parser = _FuelTableParser()
    parser.feed(html)

    data_date_match = _DATE_RE.search(html)
    data_date = data_date_match.group(1) if data_date_match else None

    stations: list[Station] = []
    for cells, href in parser.rows:
        if not href or len(cells) < 5:
            continue

        station_text, updated = _strip_updated(cells[0])
        network, address = _network_and_address(station_text)

        prices: dict[str, float] = {}
        values = {
            "diesel": _price(cells[1]),
            "petrol_95": _price(cells[2]),
            "petrol_98": _price(cells[3]),
            "lpg": _price(cells[4]),
        }
        for fuel, value in values.items():
            if value is not None:
                prices[fuel] = value

        stations.append(
            Station(
                name=station_text,
                network=network,
                address=address,
                prices=prices,
                detail_url=urljoin(KUROHUDAS_BASE_URL, href),
                updated=updated,
            )
        )

    if not stations:
        raise KurohudasApiError("Kurohudas puslapyje nerasta degalinių lentelė")

    return ApiData(stations=stations, data_date=data_date)


def parse_coordinates(html: str) -> tuple[float, float] | None:
    """Extract coordinates from Google Maps navigation link."""
    match = _COORD_RE.search(html)
    if match:
        return float(match.group(1)), float(match.group(2))

    for href in re.findall(
        r'href=["\']([^"\']*google\.com/maps/dir/[^"\']*)',
        html,
    ):
        parsed = urlparse(href.replace("&amp;", "&"))
        destination = parse_qs(parsed.query).get("destination")
        if not destination:
            continue
        parts = unquote(destination[0]).split(",", 1)
        if len(parts) != 2:
            continue
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            continue
    return None


class KurohudasApi:
    """Async Kurohudas web client."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {
            "User-Agent": "HomeAssistant TuščiasBakas integration/0.3",
            "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.7",
        }

    async def _get_text(self, url: str) -> str:
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=30,
            ) as response:
                if response.status != 200:
                    raise KurohudasApiError(f"HTTP {response.status}: {url}")
                return await response.text()
        except (ClientError, TimeoutError) as err:
            raise KurohudasApiError(str(err)) from err

    async def async_get_stations(self, city: str) -> ApiData:
        url = f"{KUROHUDAS_BASE_URL}/miestas/{quote(city.strip(), safe='')}"
        return parse_city_page(await self._get_text(url))

    async def async_get_coordinates(
        self,
        detail_url: str,
    ) -> tuple[float, float] | None:
        return parse_coordinates(await self._get_text(detail_url))


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine straight-line distance in kilometres."""
    import math

    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
