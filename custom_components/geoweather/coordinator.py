"""Config Flow for GeoWeather."""

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
    CONF_UPDATE_INTERVAL,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

# Selector für Breitengrad (Latitude)
_LAT_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor", "device_tracker"], device_class="latitude"
    )
)

# Selector für Längengrad (Longitude)
_LON_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor", "device_tracker"], device_class="longitude"
    )
)

# Optionaler Selector für Geschwindigkeit (Speed)
_SPEED_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="speed")
)

# Falls ein Sensor keine Device Class hat (wie oft bei Satelliten),
# nehmen wir einen breiteren Filter:
_GENERIC_SENSOR = selector.EntitySelector(
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
        # Numerische Validierung (Logik-Check bleibt!)
        if float(user_input.get(CONF_SPEED_THRESHOLD, 0)) < 0:
            errors[CONF_SPEED_THRESHOLD] = "invalid_speed"
        elif int(user_input.get(CONF_MIN_SATELLITES, 1)) < 1:
            errors[CONF_MIN_SATELLITES] = "invalid_satellites"
        else:
            # Sensoren auf Existenz in HA  prüfen
            for key in (CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_SPEED_SENSOR):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "entity_not_found"

            if not errors:
                return self.async_create_entry(
                    title="GeoWeather",
                    data=user_input,
                )

    # neue Selectoren einbinden
    schema = vol.Schema(
        {
            # -- Required GPS sensors (spezifischen Filter) --
            vol.Required(CONF_LAT_SENSOR): _LAT_SELECTOR,
            vol.Required(CONF_LON_SENSOR): _LON_SELECTOR,
            vol.Required(CONF_SPEED_SENSOR): _SPEED_SELECTOR,

            # -- Optional GPS sensors (generischen Sensor-Filter) --
            vol.Optional(CONF_ALT_SENSOR): _GENERIC_SENSOR,
            vol.Optional(CONF_SAT_SENSOR): _GENERIC_SENSOR,

            # -- Behaviour ( praktischen Schieberegler/Zahlenfelder) --
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

        merged = {**self._entry.data, **self._entry.options}

        # Hilfsfunktion: Gibt den Wert zurück oder vol.UNDEFINED, wenn leer
        def get_val(key):
            val = merged.get(key)
            return val if val and val not in ("None", "") else vol.UNDEFINED

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # Pflichtfelder
                    vol.Required(
                        CONF_LAT_SENSOR, default=get_val(CONF_LAT_SENSOR)
                    ): _ENTITY_SELECTOR,
                    vol.Required(
                        CONF_LON_SENSOR, default=get_val(CONF_LON_SENSOR)
                    ): _ENTITY_SELECTOR,
                    vol.Required(
                        CONF_SPEED_SENSOR, default=get_val(CONF_SPEED_SENSOR)
                    ): _ENTITY_SELECTOR,
                    # Optionale Felder (jetzt sicher gegen UUID-Fehler)
                    vol.Optional(
                        CONF_ALT_SENSOR, default=get_val(CONF_ALT_SENSOR)
                    ): _ENTITY_SELECTOR,
                    vol.Optional(
                        CONF_SAT_SENSOR, default=get_val(CONF_SAT_SENSOR)
                    ): _ENTITY_SELECTOR,
                    # Einstellungen
                    vol.Optional(
                        CONF_SPEED_THRESHOLD,
                        default=merged.get(
                            CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD
                        ),
                    ): _number(0, 50, 0.5, "km/h"),
                    vol.Optional(
                        CONF_MIN_SATELLITES,
                        default=merged.get(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES),
                    ): _number(0, 20, 1, "Sats"),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=merged.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): _number(0, 1440, 5, "Min"),
                }
            ),
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
