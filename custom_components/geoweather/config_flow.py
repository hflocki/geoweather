"""Config Flow for GeoWeather."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ALT_SENSOR,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_UPDATE_INTERVAL,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
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
            min=min_,
            max=max_,
            step=step,
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
            # 1. Numerische Validierung
            if float(user_input.get(CONF_SPEED_THRESHOLD, 0)) < 0:
                errors[CONF_SPEED_THRESHOLD] = "invalid_speed"
            elif int(user_input.get(CONF_MIN_SATELLITES, 1)) < 1:
                errors[CONF_MIN_SATELLITES] = "invalid_satellites"
            else:
                # 2. Sensoren auf Existenz im HA System prüfen
                for key in (CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_SPEED_SENSOR):
                    entity_id = user_input.get(key)
                    if entity_id and self.hass.states.get(entity_id) is None:
                        errors[key] = "entity_not_found"
                
                if not errors:
                    return self.async_create_entry(
                        title="GeoWeather",
                        data=user_input,
                    )

        schema = vol.Schema(
            {
                # ── Required GPS sensors ──────────────────────────────────────
                vol.Required(CONF_LAT_SENSOR): _ENTITY_SELECTOR,
                vol.Required(CONF_LON_SENSOR): _ENTITY_SELECTOR,
                vol.Required(CONF_SPEED_SENSOR): _ENTITY_SELECTOR,
                # ── Optional GPS sensors ──────────────────────────────────────
                vol.Optional(CONF_ALT_SENSOR): _ENTITY_SELECTOR_OPT,
                vol.Optional(CONF_SAT_SENSOR): _ENTITY_SELECTOR_OPT,
                # ── Behaviour ─────────────────────────────────────────────────
                vol.Optional(
                    CONF_SPEED_THRESHOLD, default=DEFAULT_SPEED_THRESHOLD
                ): _number(0, 50, 0.5, "km/h"),
                vol.Optional(
                    CONF_MIN_SATELLITES, default=DEFAULT_MIN_SATELLITES
                ): _number(1, 20, 1, "Satelliten"),
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): _number(0, 1440, 5, "Minuten"),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return GeoWeatherOptionsFlow(config_entry)


class GeoWeatherOptionsFlow(config_entries.OptionsFlow):
    """Allow changing settings after setup."""

    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Daten aus Setup und Optionen zusammenführen, um aktuelle Werte anzuzeigen
        merged = {**self._entry.data, **self._entry.options}

        # Wir erstellen das Schema dynamisch, um "None"-Fehler zu vermeiden
        data_schema = vol.Schema({
            vol.Required(CONF_LAT_SENSOR, default=merged.get(CONF_LAT_SENSOR, "")): _ENTITY_SELECTOR,
            vol.Required(CONF_LON_SENSOR, default=merged.get(CONF_LON_SENSOR, "")): _ENTITY_SELECTOR,
            vol.Required(CONF_SPEED_SENSOR, default=merged.get(CONF_SPEED_SENSOR, "")): _ENTITY_SELECTOR,
            vol.Optional(CONF_ALT_SENSOR, default=merged.get(CONF_ALT_SENSOR, "")): _ENTITY_SELECTOR,
            vol.Optional(CONF_SAT_SENSOR, default=merged.get(CONF_SAT_SENSOR, "")): _ENTITY_SELECTOR,
            
            vol.Optional(CONF_SPEED_THRESHOLD, default=merged.get(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD)): _number(0, 50, 0.5, "km/h"),
            vol.Optional(CONF_MIN_SATELLITES, default=merged.get(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES)): _number(0, 20, 1, "Sats"),
            vol.Optional(CONF_UPDATE_INTERVAL, default=merged.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): _number(0, 1440, 5, "Min"),
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
