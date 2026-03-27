"""Binary sensor: Is the vehicle currently moving?"""
from __future__ import annotations
from datetime import datetime, timezone
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, CONF_SPEED_SENSOR, CONF_SPEED_THRESHOLD

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GeoWeatherMovingBinarySensor(coordinator, entry)])

class GeoWeatherMovingBinarySensor(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_should_poll = False  # Echtzeit-Reaktion via Event
    _attr_has_entity_name = True
    _attr_name = "Moving"

    def __init__(self, coordinator, entry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_moving"

    async def async_added_to_hass(self) -> None:
        """Abonniere den Speed-Sensor für sofortige Updates."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR) or self._entry.data.get(CONF_SPEED_SENSOR)
        if speed_id:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [speed_id], self._update_callback)
            )

    async def _update_callback(self, event) -> None:
        """Wird bei jeder Änderung am Tacho gerufen."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Prüft den Status direkt am Sensor-Zustand."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR) or self._entry.data.get(CONF_SPEED_SENSOR)
        state = self.hass.states.get(speed_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                threshold = float(self._entry.options.get(CONF_SPEED_THRESHOLD, 5.0))
                return float(state.state.replace(",", ".")) > threshold
            except (ValueError, TypeError):
                return False
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Alle deine ursprünglichen Attribute (Standzeit etc.)."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR) or self._entry.data.get(CONF_SPEED_SENSOR)
        speed_state = self.hass.states.get(speed_id)
        
        standzeit_min = None
        if self._coordinator.stopped_at and not self.is_on:
            standzeit_min = round((datetime.now(timezone.utc) - self._coordinator.stopped_at).total_seconds() / 60, 1)

        return {
            "geschwindigkeit_kmh": speed_state.state if speed_state else 0,
            "standzeit_min": standzeit_min,
            "letzter_skip_grund": getattr(self._coordinator, "last_skip_reason", None)
        }

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}
