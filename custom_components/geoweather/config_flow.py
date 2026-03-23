"""Config Flow for GeoWeather."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_ALT_SENSOR,
    CONF_SAT_SENSOR,
    CONF_SPEED_THRESHOLD,
    CONF_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
)

_ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)
_ENTITY_SELECTOR_OPT = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)


def _number(min_, max_, step, unit):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_, max=max_, step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class GeoWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict = {}

        if user_input is not None:
            if float(user_input.get(CONF_SPEED_THRESHOLD, 0)) < 0:
                errors[CONF_SPEED_THRESHOLD] = "invalid_speed"
            elif int(user_input.get(CONF_MIN_SATELLITES, 1)) < 1:
                errors[CONF_MIN_SATELLITES] = "invalid_satellites"
            else:
                return self.async_create_entry(
                    title="GeoWeather",
                    data=user_input,
                )

        schema = vol.Schema({
            # ── Required GPS sensors ──────────────────────────────────────
            vol.Required(CONF_LAT_SENSOR):  _ENTITY_SELECTOR,
            vol.Required(CONF_LON_SENSOR):  _ENTITY_SELECTOR,
            vol.Required(CONF_SPEED_SENSOR): _ENTITY_SELECTOR,
            # ── Optional GPS sensors ──────────────────────────────────────
            vol.Optional(CONF_ALT_SENSOR):  _ENTITY_SELECTOR_OPT,
            vol.Optional(CONF_SAT_SENSOR):  _ENTITY_SELECTOR_OPT,
            # ── Behaviour ─────────────────────────────────────────────────
            vol.Optional(CONF_SPEED_THRESHOLD, default=DEFAULT_SPEED_THRESHOLD):
                _number(0, 50, 0.5, "km/h"),
            vol.Optional(CONF_MIN_SATELLITES, default=DEFAULT_MIN_SATELLITES):
                _number(1, 20, 1, "Satelliten"),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return GeoWeatherOptionsFlow(config_entry)


class GeoWeatherOptionsFlow(config_entries.OptionsFlow):
    """Allow changing speed threshold / min satellites after setup."""

    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        errors: dict = {}
        merged = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            if float(user_input.get(CONF_SPEED_THRESHOLD, 0)) < 0:
                errors[CONF_SPEED_THRESHOLD] = "invalid_speed"
            elif int(user_input.get(CONF_MIN_SATELLITES, 1)) < 1:
                errors[CONF_MIN_SATELLITES] = "invalid_satellites"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(
                CONF_SPEED_THRESHOLD,
                default=merged.get(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD),
            ): _number(0, 50, 0.5, "km/h"),
            vol.Optional(
                CONF_MIN_SATELLITES,
                default=merged.get(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES),
            ): _number(1, 20, 1, "Satelliten"),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
