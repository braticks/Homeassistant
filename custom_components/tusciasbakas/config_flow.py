"""Config flow for Tuščias bakas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlowWithReload
from homeassistant.core import callback

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

RULE_FIELDS = tuple(f"discount_rule_{idx}" for idx in range(1, 11))


def _form_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    """Expand stored multiline discounts into separate form fields."""
    result = dict(defaults)
    existing = [
        line.strip()
        for line in str(result.get(CONF_DISCOUNT_RULES, "")).splitlines()
        if line.strip()
    ]
    for idx, field in enumerate(RULE_FIELDS):
        result.setdefault(field, existing[idx] if idx < len(existing) else "")
    return result


def _rules_text(values: dict[str, Any]) -> str:
    """Collect separate discount inputs into stored multiline format."""
    lines = []
    for field in RULE_FIELDS:
        value = str(values.get(field, "")).strip()
        if value:
            lines.append(value)
    return "\n".join(lines)


def _normalize(values: dict[str, Any]) -> dict[str, Any]:
    """Remove form-only fields and store discounts in one canonical key."""
    result = dict(values)
    result[CONF_DISCOUNT_RULES] = _rules_text(result)
    for field in RULE_FIELDS:
        result.pop(field, None)
    return result


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build config schema."""
    defaults = _form_defaults(defaults)
    schema: dict[Any, Any] = {
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

    for field in RULE_FIELDS:
        schema[vol.Optional(field, default=str(defaults.get(field, "")))] = str

    return vol.Schema(schema)


class TusciasBakasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            rules_text = _rules_text(user_input)
            _, rule_errors = parse_discount_rules(rules_text)
            if rule_errors:
                errors["base"] = "invalid_discount_rules"
            else:
                await self.async_set_unique_id("main")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tuščias bakas",
                    data=_normalize(user_input),
                )

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

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return options flow."""
        return TusciasBakasOptionsFlow()


class TusciasBakasOptionsFlow(OptionsFlowWithReload):
    """Edit radius, fuel type, location and discounts."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle options."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            rules_text = _rules_text(user_input)
            _, rule_errors = parse_discount_rules(rules_text)
            if rule_errors:
                errors["base"] = "invalid_discount_rules"
                current.update(user_input)
            else:
                return self.async_create_entry(
                    title="",
                    data=_normalize(user_input),
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current),
            errors=errors,
        )
