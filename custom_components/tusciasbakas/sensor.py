"""Sensors for Tuščias bakas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, FUEL_TYPES
from .coordinator import TusciasBakasCoordinator


@dataclass(frozen=True, kw_only=True)
class TusciasBakasSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]]


def _top_attrs(key: str, station_key: str):
    def inner(data: dict[str, Any]) -> dict[str, Any]:
        return {"top_10": data.get(key, []), "station": data.get(station_key)}
    return inner


SENSORS = (
    TusciasBakasSensorDescription(
        key="cheapest_price",
        translation_key="cheapest_price",
        native_unit_of_measurement="€/L",
        icon="mdi:gas-station",
        value_fn=lambda d: d["cheapest"]["price"] if d.get("cheapest") else None,
        attrs_fn=_top_attrs("top_by_price", "cheapest"),
    ),
    TusciasBakasSensorDescription(
        key="cheapest_effective_price",
        translation_key="cheapest_effective_price",
        native_unit_of_measurement="€/L",
        icon="mdi:tag-minus",
        value_fn=lambda d: d["cheapest_effective"]["effective_price"] if d.get("cheapest_effective") else None,
        attrs_fn=_top_attrs("top_by_effective", "cheapest_effective"),
    ),
    TusciasBakasSensorDescription(
        key="nearest_station",
        translation_key="nearest_station",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:map-marker-distance",
        value_fn=lambda d: d["nearest"]["distance_km"] if d.get("nearest") else None,
        attrs_fn=_top_attrs("top_by_distance", "nearest"),
    ),
    TusciasBakasSensorDescription(
        key="station_count",
        translation_key="station_count",
        icon="mdi:counter",
        value_fn=lambda d: d.get("station_count", 0),
        attrs_fn=lambda d: {},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TusciasBakasCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TusciasBakasSensor(coordinator, entry, description) for description in SENSORS)


class TusciasBakasSensor(CoordinatorEntity[TusciasBakasCoordinator], SensorEntity):
    """A Tuščias bakas sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TusciasBakasCoordinator,
        entry: ConfigEntry,
        description: TusciasBakasSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Tuščias bakas",
            "manufacturer": "tusciasbakas.lt",
            "model": "LEA fuel prices",
            "configuration_url": "https://tusciasbakas.lt/",
        }

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value = self.entity_description.attrs_fn(self.coordinator.data)
        attrs = {
            "attribution": ATTRIBUTION,
            "fuel_type": FUEL_TYPES.get(self.coordinator.fuel_type, self.coordinator.fuel_type),
            "radius_km": self.coordinator.radius_km,
            "data_date": self.coordinator.data.get("data_date"),
        }
        attrs.update(value)
        return attrs
