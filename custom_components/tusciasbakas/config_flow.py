"""Config flow for Tuščias bakas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DISCOUNT_RULES,
    CONF_FUEL_TYPE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    CONF_UPDATE_MINUTES,
    DEFAULT_FUEL_TYPE,
    DEFAULT_RADIUS_KM,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    FUEL_TYPES,
)
from .discounts import parse_discount_rules


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE, default=defaults.get(CONF_LATITUDE)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-90, max=90, step=0.000001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LONGITUDE, default=defaults.get(CONF_LONGITUDE)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-180, max=180, step=0.000001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_RADIUS_KM, default=defaults.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=50, step=1, unit_of_measurement="km", mode=selector.NumberSelectorMode.SLIDER)
            ),
            vol.Required(CONF_FUEL_TYPE, default=defaults.get(CONF_FUEL_TYPE, DEFAULT_FUEL_TYPE)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_DISCOUNT_RULES, default=defaults.get(CONF_DISCOUNT_RULES, "")): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            vol.Required(CONF_UPDATE_MINUTES, default=defaults.get(CONF_UPDATE_MINUTES, DEFAULT_UPDATE_MINUTES)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=360, step=15, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )


class TusciasBakasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            _, rule_errors = parse_discount_rules(str(user_input.get(CONF_DISCOUNT_RULES, "")))
            if rule_errors:
                errors[CONF_DISCOUNT_RULES] = "invalid_discount_rules"
            else:
                await self.async_set_unique_id("main")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Tuščias bakas", data=user_input)

        defaults = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_RADIUS_KM: DEFAULT_RADIUS_KM,
            CONF_FUEL_TYPE: DEFAULT_FUEL_TYPE,
            CONF_DISCOUNT_RULES: "",
            CONF_UPDATE_MINUTES: DEFAULT_UPDATE_MINUTES,
        }
        if user_input:
            defaults.update(user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(defaults), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TusciasBakasOptionsFlow()


class TusciasBakasOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit radius, fuel type, location and discounts."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            _, rule_errors = parse_discount_rules(str(user_input.get(CONF_DISCOUNT_RULES, "")))
            if rule_errors:
                errors[CONF_DISCOUNT_RULES] = "invalid_discount_rules"
            else:
                return self.async_create_entry(title="", data=user_input)
            current.update(user_input)

        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
