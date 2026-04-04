"""Config Flow for GeoWeather v2.4.0."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ALT_SENSOR,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
)

# --- Selectors ---

_LAT_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number", "device_tracker"])
)
_LON_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number", "device_tracker"])
)
_SPEED_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)
_GENERIC_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)


def _number(min_, max_, step, unit):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=float(min_),
            max=float(max_),
            step=float(step),
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class GeoWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow for first installation."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict = {}

        if user_input is not None:
            for key in (CONF_LAT_SENSOR, CONF_LON_SENSOR):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "entity_not_found"

            if not errors:
                return self.async_create_entry(title="GeoWeather", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_LAT_SENSOR): _LAT_SELECTOR,
                vol.Required(CONF_LON_SENSOR): _LON_SELECTOR,
                vol.Required(CONF_SPEED_SENSOR): _SPEED_SELECTOR,
                vol.Optional(CONF_ALT_SENSOR): _GENERIC_SENSOR,
                vol.Optional(CONF_SAT_SENSOR): _GENERIC_SENSOR,
                vol.Optional(
                    CONF_SPEED_THRESHOLD, default=DEFAULT_SPEED_THRESHOLD
                ): _number(0, 50, 0.5, "km/h"),
                vol.Optional(
                    CONF_MIN_SATELLITES, default=DEFAULT_MIN_SATELLITES
                ): _number(1, 20, 1, "Satelliten"),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return GeoWeatherOptionsFlow(config_entry)


class GeoWeatherOptionsFlow(config_entries.OptionsFlow):
    """Einstellungen nach der Installation ändern."""

    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        merged = {**self._entry.data, **self._entry.options}

        def get_val(key):
            val = merged.get(key)
            return val if val and val not in ("None", "") else vol.UNDEFINED

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LAT_SENSOR, default=get_val(CONF_LAT_SENSOR)
                ): _LAT_SELECTOR,
                vol.Required(
                    CONF_LON_SENSOR, default=get_val(CONF_LON_SENSOR)
                ): _LON_SELECTOR,
                vol.Required(
                    CONF_SPEED_SENSOR, default=get_val(CONF_SPEED_SENSOR)
                ): _SPEED_SELECTOR,
                vol.Optional(
                    CONF_ALT_SENSOR, default=get_val(CONF_ALT_SENSOR)
                ): _GENERIC_SENSOR,
                vol.Optional(
                    CONF_SAT_SENSOR, default=get_val(CONF_SAT_SENSOR)
                ): _GENERIC_SENSOR,
                vol.Optional(
                    CONF_SPEED_THRESHOLD,
                    default=merged.get(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD),
                ): _number(0, 50, 0.5, "km/h"),
                vol.Optional(
                    CONF_MIN_SATELLITES,
                    default=merged.get(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES),
                ): _number(1, 20, 1, "Sats"),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
