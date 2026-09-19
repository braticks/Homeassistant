"""Config and options flow for Tuščias bakas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import TusciasBakasApi, TusciasBakasApiError
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
    FUEL_TYPES,
)
from .discounts import structured_from_legacy, structured_rule_label

FALLBACK_NETWORKS = [
    "Circle K",
    "Neste",
    "Viada",
    "ORLEN",
    "Baltic Petroleum",
    "Jozita",
    "EMSI",
    "Saurida",
]

WEEKDAY_OPTIONS = [
    SelectOptionDict(value="0", label="Pirmadienis"),
    SelectOptionDict(value="1", label="Antradienis"),
    SelectOptionDict(value="2", label="Trečiadienis"),
    SelectOptionDict(value="3", label="Ketvirtadienis"),
    SelectOptionDict(value="4", label="Penktadienis"),
    SelectOptionDict(value="5", label="Šeštadienis"),
    SelectOptionDict(value="6", label="Sekmadienis"),
]


def _general_schema(defaults: dict[str, Any]) -> vol.Schema:
    """General settings schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_LATITUDE,
                default=float(defaults.get(CONF_LATITUDE, 0)),
            ): vol.All(vol.Coerce(float), vol.Range(min=-90, max=90)),
            vol.Required(
                CONF_LONGITUDE,
                default=float(defaults.get(CONF_LONGITUDE, 0)),
            ): vol.All(vol.Coerce(float), vol.Range(min=-180, max=180)),
            vol.Required(
                CONF_RADIUS_KM,
                default=float(defaults.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)),
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=50)),
            vol.Required(
                CONF_FUEL_TYPE,
                default=str(defaults.get(CONF_FUEL_TYPE, DEFAULT_FUEL_TYPE)),
            ): vol.In(FUEL_TYPES),
            vol.Required(
                CONF_UPDATE_MINUTES,
                default=int(defaults.get(CONF_UPDATE_MINUTES, DEFAULT_UPDATE_MINUTES)),
            ): vol.All(vol.Coerce(int), vol.Range(min=15, max=360)),
        }
    )


async def _async_network_names(hass) -> list[str]:
    """Return unique fuel network names from current API data."""
    api = TusciasBakasApi(async_get_clientsession(hass))
    try:
        data = await api.async_get_stations()
    except TusciasBakasApiError:
        return FALLBACK_NETWORKS

    names = {
        (station.network or station.name or "").strip()
        for station in data.stations
        if (station.network or station.name or "").strip()
    }
    if not names:
        return FALLBACK_NETWORKS
    return sorted(names, key=str.casefold)


class TusciasBakasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Set up the integration."""
        if user_input is not None:
            await self.async_set_unique_id("main")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Tuščias bakas",
                data=user_input,
            )

        defaults = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_RADIUS_KM: DEFAULT_RADIUS_KM,
            CONF_FUEL_TYPE: DEFAULT_FUEL_TYPE,
            CONF_UPDATE_MINUTES: DEFAULT_UPDATE_MINUTES,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_general_schema(defaults),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return options flow."""
        return TusciasBakasOptionsFlow()


class TusciasBakasOptionsFlow(OptionsFlowWithReload):
    """Manage settings, network filters and discounts."""

    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    def _save(self, updates: dict[str, Any]):
        data = dict(self.config_entry.options)
        data.update(updates)
        return self.async_create_entry(title="", data=data)

    def _current_discounts(self) -> list[dict[str, Any]]:
        if getattr(self, "_discounts_working", None) is not None:
            return self._discounts_working

        current = self._current()
        if CONF_DISCOUNTS in self.config_entry.options:
            items = list(self.config_entry.options.get(CONF_DISCOUNTS, []))
        elif CONF_DISCOUNTS in self.config_entry.data:
            items = list(self.config_entry.data.get(CONF_DISCOUNTS, []))
        else:
            items = structured_from_legacy(
                str(current.get(CONF_DISCOUNT_RULES, ""))
            )
        self._discounts_working = items
        return items

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show settings menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "general": "Bendri nustatymai",
                "networks": "Rodomi degalinių tinklai",
                "discounts": "Nuolaidos",
            },
        )

    async def async_step_general(self, user_input: dict[str, Any] | None = None):
        """Edit location, radius, fuel and refresh interval."""
        current = self._current()
        if user_input is not None:
            return self._save(user_input)

        return self.async_show_form(
            step_id="general",
            data_schema=_general_schema(current),
        )

    async def async_step_networks(self, user_input: dict[str, Any] | None = None):
        """Choose networks that should be hidden."""
        current = self._current()

        if user_input is not None:
            excluded = list(user_input.get(CONF_EXCLUDED_NETWORKS, []))
            return self._save({CONF_EXCLUDED_NETWORKS: excluded})

        networks = await _async_network_names(self.hass)

        if CONF_EXCLUDED_NETWORKS in current:
            selected = list(current.get(CONF_EXCLUDED_NETWORKS, []))
        else:
            selected = [
                network
                for network in networks
                if not any(
                    pattern in network.casefold()
                    for pattern in DEFAULT_VISIBLE_NETWORK_PATTERNS
                )
            ]

        all_options = sorted(
            set(networks) | set(selected),
            key=str.casefold,
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXCLUDED_NETWORKS,
                    default=selected,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=all_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="networks",
            data_schema=schema,
        )

    async def async_step_discounts(self, user_input: dict[str, Any] | None = None):
        """Manage discounts using a guided UI."""
        items = self._current_discounts()
        existing = "\n".join(
            f"• {structured_rule_label(item)}"
            for item in items
        ) or "Nuolaidų nėra."

        menu = {
            "add_discount": "Pridėti nuolaidą",
        }
        if items:
            menu["remove_discount"] = "Pašalinti nuolaidą"
        menu["save_discounts"] = "Išsaugoti"

        return self.async_show_menu(
            step_id="discounts",
            menu_options=menu,
            description_placeholders={"existing": existing},
        )

    async def async_step_add_discount(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Add one structured discount rule."""
        if user_input is not None:
            self._current_discounts().append(
                {
                    "network": str(user_input["network"]),
                    "weekdays": [
                        int(day)
                        for day in user_input["weekdays"]
                    ],
                    "amount": float(user_input["amount"]),
                }
            )
            return await self.async_step_discounts()

        networks = await _async_network_names(self.hass)
        schema = vol.Schema(
            {
                vol.Required("network"): SelectSelector(
                    SelectSelectorConfig(
                        options=networks,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("weekdays"): SelectSelector(
                    SelectSelectorConfig(
                        options=WEEKDAY_OPTIONS,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("amount", default=0.05): NumberSelector(
                    NumberSelectorConfig(
                        min=0.01,
                        max=1.00,
                        step=0.01,
                        unit_of_measurement="€/l",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="add_discount",
            data_schema=schema,
        )

    async def async_step_remove_discount(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Remove one configured discount."""
        items = self._current_discounts()
        if not items:
            return await self.async_step_discounts()

        if user_input is not None:
            index = int(user_input["discount_index"])
            if 0 <= index < len(items):
                items.pop(index)
            return await self.async_step_discounts()

        options = [
            SelectOptionDict(
                value=str(index),
                label=structured_rule_label(item),
            )
            for index, item in enumerate(items)
        ]
        return self.async_show_form(
            step_id="remove_discount",
            data_schema=vol.Schema(
                {
                    vol.Required("discount_index"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_save_discounts(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Persist discount changes."""
        return self._save(
            {CONF_DISCOUNTS: list(self._current_discounts())}
        )
