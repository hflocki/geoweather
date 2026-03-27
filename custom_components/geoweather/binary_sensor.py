"""Binary sensor for GeoWeather - Moving status."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, CONF_SPEED_SENSOR, CONF_SPEED_THRESHOLD

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    # Wir brauchen den Coordinator hier eigentlich nicht für den Status, 
    # da wir direkt auf den Speed-Sensor hören.
    async_add_entities([GeoWeatherMovingBinarySensor(entry)])


class GeoWeatherMovingBinarySensor(BinarySensorEntity):
    """Binary sensor that responds immediately to speed changes."""

    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_should_poll = False  # Wir nutzen Events für Echtzeit-Reaktion
    _attr_has_entity_name = True
    _attr_name = "Moving"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_moving"

    async def async_added_to_hass(self) -> None:
        """Subscribe to speed sensor changes when added to hass."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR) or self._entry.data.get(CONF_SPEED_SENSOR)
        
        if speed_id:
            # Jedes Mal, wenn der Tacho-Sensor einen neuen Wert sendet, 
            # triggern wir diesen Sensor hier an.
            self.async_on_remove(
                async_track_state_change_event(self.hass, [speed_id], self._update_callback)
            )

    async def _update_callback(self, event) -> None:
        """Update the state immediately."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if the vehicle is moving."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR) or self._entry.data.get(CONF_SPEED_SENSOR)
        if not speed_id:
            return False

        state = self.hass.states.get(speed_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                # Schwellenwert aus Optionen (Standard 5.0)
                threshold = float(self._entry.options.get(CONF_SPEED_THRESHOLD, 5.0))
                # Aktuelle Geschwindigkeit vom Tacho
                current_speed = float(state.state.replace(",", "."))
                return current_speed > threshold
            except (ValueError, TypeError):
                return False
        return False

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}
