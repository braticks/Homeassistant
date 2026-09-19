"""Data coordinator for Tuščias bakas."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import LeaApiError, LeaFuelApi, Station, distance_km
from .const import (
    CONF_DISCOUNT_RULES,
    CONF_DISCOUNTS,
    CONF_EXCLUDED_NETWORKS,
    CONF_FUEL_TYPE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    CONF_UPDATE_MINUTES,
    DEFAULT_FUEL_TYPE,
    DEFAULT_RADIUS_KM,
    DEFAULT_UPDATE_MINUTES,
    DEFAULT_VISIBLE_NETWORK_PATTERNS,
    DOMAIN,
    LEA_SITE_URL,
    MAX_RADIUS_KM,
)
from .discounts import parse_discount_rules, rules_from_structured

_LOGGER = logging.getLogger(__name__)
_CACHE_VERSION = 1
_CACHE_MAX_AGE_DAYS = 7


class TusciasBakasCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch official LEA prices and calculate nearby station results."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        options = {**entry.data, **entry.options}
        self.latitude = float(options.get(CONF_LATITUDE, hass.config.latitude))
        self.longitude = float(options.get(CONF_LONGITUDE, hass.config.longitude))
        self.radius_km = min(
            MAX_RADIUS_KM,
            float(options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)),
        )
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
        self.api = LeaFuelApi(async_get_clientsession(hass))

        self._price_store = Store(
            hass,
            _CACHE_VERSION,
            f"{DOMAIN}_last_non_null_prices",
        )
        self._price_cache: dict[str, dict[str, Any]] | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(15, update_minutes)),
        )

    def _network_allowed(self, station: Station) -> bool:
        network_cf = station.network.casefold()
        if self.has_custom_network_filter:
            return not any(
                excluded == network_cf
                or excluded in network_cf
                or network_cf in excluded
                for excluded in self.excluded_networks
            )
        return any(
            pattern in network_cf
            for pattern in DEFAULT_VISIBLE_NETWORK_PATTERNS
        )

    @staticmethod
    def _cache_key(station: Station, fuel_type: str) -> str:
        return "|".join(
            (
                station.company_name.casefold(),
                station.name.casefold(),
                station.address.casefold(),
                fuel_type,
            )
        )

    async def _ensure_cache(self) -> None:
        if self._price_cache is not None:
            return
        loaded = await self._price_store.async_load()
        self._price_cache = loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _cached_price_is_fresh(updated: str | None) -> bool:
        if not updated:
            return False
        try:
            updated_date = date.fromisoformat(updated[:10])
        except ValueError:
            return False
        age = dt_util.now().date() - updated_date
        return timedelta(0) <= age <= timedelta(days=_CACHE_MAX_AGE_DAYS)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            api_data = await self.api.async_get_stations()
        except LeaApiError as err:
            raise UpdateFailed(
                f"Nepavyko gauti LEA degalų kainų: {err}"
            ) from err

        await self._ensure_cache()
        assert self._price_cache is not None

        today = dt_util.now().date()
        cache_changed = False
        rows: list[dict[str, Any]] = []

        for station in api_data.stations:
            if self.fuel_type not in station.available_fuels:
                continue
            if not self._network_allowed(station):
                continue

            dist = distance_km(
                self.latitude,
                self.longitude,
                station.latitude,
                station.longitude,
            )
            if dist > self.radius_km:
                continue

            cache_key = self._cache_key(station, self.fuel_type)
            price = station.prices.get(self.fuel_type)
            updated = station.updated.get(self.fuel_type)
            price_from_cache = False

            if price is not None:
                self._price_cache[cache_key] = {
                    "price": round(price, 3),
                    "updated": updated,
                }
                cache_changed = True
            else:
                cached = self._price_cache.get(cache_key)
                if (
                    isinstance(cached, dict)
                    and self._cached_price_is_fresh(
                        str(cached.get("updated") or "")
                    )
                ):
                    try:
                        price = float(cached["price"])
                    except (KeyError, TypeError, ValueError):
                        price = None
                    if price is not None:
                        updated = str(cached.get("updated") or "")
                        price_from_cache = True

            if price is None:
                continue

            station_text = " ".join(
                filter(
                    None,
                    (
                        station.network,
                        station.company_name,
                        station.name,
                        station.address,
                    ),
                )
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
                    "company_name": station.company_name,
                    "address": station.address,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance_km": round(dist, 2),
                    "price": round(price, 3),
                    "discount_eur_l": discount,
                    "effective_price": effective,
                    "discount_rules": [rule.source for rule in active],
                    "price_updated": updated,
                    "price_from_cache": price_from_cache,
                    "source": "LEA",
                    "logo_url": station.logo_url,
                    "detail_url": LEA_SITE_URL,
                }
            )

        if cache_changed:
            await self._price_store.async_save(self._price_cache)

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
            "source": "LEA",
            "station_count": len(rows),
            "cheapest": by_price[0] if by_price else None,
            "cheapest_effective": by_effective[0] if by_effective else None,
            "nearest": by_distance[0] if by_distance else None,
            "top_by_price": by_price[:10],
            "top_by_effective": by_effective[:10],
            "top_by_distance": by_distance[:10],
        }
