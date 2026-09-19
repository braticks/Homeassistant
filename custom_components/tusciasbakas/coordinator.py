"""Data coordinator for Tuščias bakas."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import TusciasBakasApi, TusciasBakasApiError, distance_km
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
)
from .discounts import parse_discount_rules, rules_from_structured

_LOGGER = logging.getLogger(__name__)


class TusciasBakasCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and calculate nearby fuel station results."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        options = {**entry.data, **entry.options}
        self.latitude = float(options.get(CONF_LATITUDE, hass.config.latitude))
        self.longitude = float(options.get(CONF_LONGITUDE, hass.config.longitude))
        self.radius_km = float(options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM))
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
        self.api = TusciasBakasApi(async_get_clientsession(hass))

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(15, update_minutes)),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            api_data = await self.api.async_get_stations()
        except TusciasBakasApiError as err:
            raise UpdateFailed(
                f"Nepavyko gauti Tuščias bakas duomenų: {err}"
            ) from err

        today = dt_util.now().date()
        rows: list[dict[str, Any]] = []

        for station in api_data.stations:
            price = station.prices.get(self.fuel_type)
            if price is None:
                continue

            network_name = (station.network or station.name or "").strip()
            network_cf = network_name.casefold()

            if self.has_custom_network_filter:
                if network_cf in self.excluded_networks:
                    continue
            elif not any(
                pattern in network_cf
                for pattern in DEFAULT_VISIBLE_NETWORK_PATTERNS
            ):
                continue

            dist = distance_km(
                self.latitude,
                self.longitude,
                station.latitude,
                station.longitude,
            )
            if dist > self.radius_km:
                continue

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
            "station_count": len(rows),
            "cheapest": by_price[0] if by_price else None,
            "cheapest_effective": by_effective[0] if by_effective else None,
            "nearest": by_distance[0] if by_distance else None,
            "top_by_price": by_price[:10],
            "top_by_effective": by_effective[:10],
            "top_by_distance": by_distance[:10],
        }
