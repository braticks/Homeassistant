"""Data coordinator for Tuščias bakas."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import KurohudasApi, KurohudasApiError, Station, distance_km
from .const import (
    CONF_CITY,
    CONF_DISCOUNT_RULES,
    CONF_DISCOUNTS,
    CONF_EXCLUDED_NETWORKS,
    CONF_FUEL_TYPE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    CONF_UPDATE_MINUTES,
    DEFAULT_CITY,
    DEFAULT_FUEL_TYPE,
    DEFAULT_RADIUS_KM,
    DEFAULT_UPDATE_MINUTES,
    DEFAULT_VISIBLE_NETWORK_PATTERNS,
    DOMAIN,
)
from .discounts import parse_discount_rules, rules_from_structured

_LOGGER = logging.getLogger(__name__)
_COORD_STORE_VERSION = 1


class TusciasBakasCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Kurohudas prices and calculate nearby station results."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        options = {**entry.data, **entry.options}
        self.latitude = float(options.get(CONF_LATITUDE, hass.config.latitude))
        self.longitude = float(options.get(CONF_LONGITUDE, hass.config.longitude))
        self.radius_km = min(
            12.0,
            float(options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)),
        )
        self.city = str(options.get(CONF_CITY, DEFAULT_CITY)).strip() or DEFAULT_CITY
        self.fuel_type = str(options.get(CONF_FUEL_TYPE, DEFAULT_FUEL_TYPE))

        self.has_custom_network_filter = (
            CONF_EXCLUDED_NETWORKS in entry.options
            or CONF_EXCLUDED_NETWORKS in entry.data
        )
        self.excluded_networks = {
            str(value).strip().casefold()
            for value in options.get(CONF_EXCLUDED_NETWORKS, [])
            if str(value).strip()
        }

        if CONF_DISCOUNTS in entry.options:
            self.discount_rules = rules_from_structured(
                entry.options.get(CONF_DISCOUNTS, [])
            )
        elif CONF_DISCOUNTS in entry.data:
            self.discount_rules = rules_from_structured(
                entry.data.get(CONF_DISCOUNTS, [])
            )
        else:
            legacy_text = str(options.get(CONF_DISCOUNT_RULES, ""))
            self.discount_rules, _ = parse_discount_rules(legacy_text)

        update_minutes = int(options.get(CONF_UPDATE_MINUTES, DEFAULT_UPDATE_MINUTES))
        self.api = KurohudasApi(async_get_clientsession(hass))
        self._coord_store = Store(
            hass,
            _COORD_STORE_VERSION,
            f"{DOMAIN}_kurohudas_coordinates",
        )
        self._coord_cache: dict[str, list[float]] | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(15, update_minutes)),
        )

    def _network_allowed(self, station: Station) -> bool:
        network_cf = (station.network or station.name or "").strip().casefold()
        if self.has_custom_network_filter:
            return network_cf not in self.excluded_networks
        return any(
            pattern in network_cf
            for pattern in DEFAULT_VISIBLE_NETWORK_PATTERNS
        )

    async def _ensure_coordinate_cache(self) -> None:
        if self._coord_cache is not None:
            return
        loaded = await self._coord_store.async_load()
        self._coord_cache = loaded if isinstance(loaded, dict) else {}

    async def _resolve_station_coordinates(self, station: Station) -> bool:
        await self._ensure_coordinate_cache()
        assert self._coord_cache is not None

        cached = self._coord_cache.get(station.detail_url)
        if (
            isinstance(cached, list)
            and len(cached) == 2
            and all(isinstance(value, (int, float)) for value in cached)
        ):
            station.latitude = float(cached[0])
            station.longitude = float(cached[1])
            return True

        try:
            coords = await self.api.async_get_coordinates(station.detail_url)
        except KurohudasApiError as err:
            _LOGGER.debug("Nepavyko gauti %s koordinačių: %s", station.name, err)
            return False

        if coords is None:
            return False

        station.latitude, station.longitude = coords
        self._coord_cache[station.detail_url] = [coords[0], coords[1]]
        return True

    async def _resolve_missing_coordinates(self, stations: list[Station]) -> None:
        await self._ensure_coordinate_cache()
        assert self._coord_cache is not None

        before = len(self._coord_cache)
        semaphore = asyncio.Semaphore(5)

        async def resolve(station: Station) -> None:
            async with semaphore:
                await self._resolve_station_coordinates(station)

        await asyncio.gather(*(resolve(station) for station in stations))
        if len(self._coord_cache) != before:
            await self._coord_store.async_save(self._coord_cache)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            api_data = await self.api.async_get_stations(self.city)
        except KurohudasApiError as err:
            raise UpdateFailed(
                f"Nepavyko gauti Kurohudas duomenų: {err}"
            ) from err

        candidates = [
            station
            for station in api_data.stations
            if self.fuel_type in station.prices and self._network_allowed(station)
        ]
        await self._resolve_missing_coordinates(candidates)

        today = dt_util.now().date()
        rows: list[dict[str, Any]] = []

        for station in candidates:
            if station.latitude is None or station.longitude is None:
                continue

            dist = distance_km(
                self.latitude,
                self.longitude,
                station.latitude,
                station.longitude,
            )
            if dist > self.radius_km:
                continue

            price = station.prices[self.fuel_type]
            station_text = " ".join(
                filter(None, (station.network, station.name, station.address))
            )
            active = [
                rule
                for rule in self.discount_rules
                if rule.active(station_text, today)
            ]
            discount = round(sum(rule.amount_eur_l for rule in active), 3)
            effective = max(0.0, round(price - discount, 3))

            rows.append(
                {
                    "name": station.name,
                    "network": station.network,
                    "address": station.address,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance_km": round(dist, 2),
                    "price": round(price, 3),
                    "discount_eur_l": discount,
                    "effective_price": effective,
                    "discount_rules": [rule.source for rule in active],
                    "price_updated": station.updated,
                    "source": "Kurohudas.lt",
                    "detail_url": station.detail_url,
                }
            )

        by_price = sorted(
            rows,
            key=lambda row: (row["price"], row["distance_km"]),
        )
        by_effective = sorted(
            rows,
            key=lambda row: (row["effective_price"], row["distance_km"]),
        )
        by_distance = sorted(rows, key=lambda row: row["distance_km"])

        return {
            "data_date": api_data.data_date,
            "source": "Kurohudas.lt",
            "city": self.city,
            "station_count": len(rows),
            "cheapest": by_price[0] if by_price else None,
            "cheapest_effective": by_effective[0] if by_effective else None,
            "nearest": by_distance[0] if by_distance else None,
            "top_by_price": by_price[:10],
            "top_by_effective": by_effective[:10],
            "top_by_distance": by_distance[:10],
        }
