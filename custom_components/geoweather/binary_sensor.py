"""Binary sensor: Is the vehicle currently moving?"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_SPEED_SENSOR,
    CONF_ALT_SENSOR,
    CONF_SAT_SENSOR,
    CONF_SPEED_THRESHOLD,
    CONF_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
)
from .coordinator import GeoWeatherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GeoWeatherMovingBinarySensor(coordinator, entry)])


class GeoWeatherMovingBinarySensor(BinarySensorEntity):
    """
    ON  = vehicle is moving  → DWD updates are skipped
    OFF = vehicle is stationary → DWD updates are active
    """

    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, coordinator: GeoWeatherCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_name = "GeoWeather fährt"
        self._attr_unique_id = f"{entry.entry_id}_moving"

    @property
    def icon(self) -> str:
        return "mdi:rv-truck" if self._attr_is_on else "mdi:parking"

    def _cfg(self, key, default=None):
        merged = {**self._entry.data, **self._entry.options}
        return merged.get(key, default)

    def _float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state.replace(",", "."))
        except ValueError:
            return None

    @property
    def is_on(self) -> bool:
        speed = self._float(self._cfg(CONF_SPEED_SENSOR))
        if speed is None:
            return False
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold

    @property
    def extra_state_attributes(self) -> dict:
        speed      = self._float(self._cfg(CONF_SPEED_SENSOR))
        altitude   = self._float(self._cfg(CONF_ALT_SENSOR))
        satellites = self._float(self._cfg(CONF_SAT_SENSOR))
        threshold  = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        min_sats   = float(self._cfg(CONF_MIN_SATELLITES,  DEFAULT_MIN_SATELLITES))

        return {
            "geschwindigkeit_kmh":  speed,
            "schwellenwert_kmh":    threshold,
            "hoehe_m":              altitude,
            "satelliten":           satellites,
            "min_satelliten":       min_sats,
            "gps_fix_ok":           (satellites is not None and satellites >= min_sats)
                                    if satellites is not None else None,
            "letzter_skip_grund":   self._coordinator.last_skip_reason,
        }

    async def async_update(self) -> None:
        """State is computed live from sensor – nothing to fetch."""
