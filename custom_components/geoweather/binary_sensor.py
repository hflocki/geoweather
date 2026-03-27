from homeassistant.helpers.event import async_track_state_change_event

class GeoWeatherMovingBinarySensor(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_should_poll = False # Wichtig: Kein Polling mehr!

    async def async_added_to_hass(self) -> None:
        """Abonniere den Speed-Sensor für sofortige Reaktion."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR)
        if speed_id:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [speed_id], self._update_callback)
            )

    async def _update_callback(self, event):
        """Wird sofort gerufen, wenn sich die Geschwindigkeit ändert."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Echtzeit-Vergleich."""
        speed_id = self._entry.options.get(CONF_SPEED_SENSOR)
        state = self.hass.states.get(speed_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                val = float(state.state.replace(",", "."))
                threshold = float(self._entry.options.get(CONF_SPEED_THRESHOLD, 5.0))
                return val > threshold
            except ValueError: return False
        return False
