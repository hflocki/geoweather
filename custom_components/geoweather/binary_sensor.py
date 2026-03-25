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
    CONF_ALT_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
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
        self._attr_name = "Fährt"
        self._attr_unique_id = f"{entry.entry_id}_moving"

    @property
    def icon(self) -> str:
        return "mdi:rv-truck" if self.is_on else "mdi:parking"

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
            return float(str(state.state).replace(",", "."))
        except (ValueError, TypeError):
            return None

    @property
    def is_on(self) -> bool:
        """ON wenn Fahrzeug fährt (Speed > Schwellenwert)."""
        speed_entity = self._entry.data.get(CONF_SPEED_SENSOR)
        state = self.hass.states.get(speed_entity)

        try:
            if state and state.state not in ("unknown", "unavailable"):
                speed = float(str(state.state).replace(",", "."))
            else:
                speed = 0
        except (ValueError, TypeError):
            speed = 0

        # Schwellenwert aus Optionen oder Data (Standard 5.0)
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, 5.0))
        return speed > threshold

    @property
    def extra_state_attributes(self) -> dict:
        speed = self._float(self._cfg(CONF_SPEED_SENSOR))
        altitude = self._float(self._cfg(CONF_ALT_SENSOR))
        satellites = self._float(self._cfg(CONF_SAT_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        min_sats = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))

        stopped_at = getattr(self._coordinator, "stopped_at", None)
        from datetime import datetime

        standzeit_min = None
        if stopped_at is not None and not self.is_on:
            standzeit_min = round((datetime.now() - stopped_at).total_seconds() / 60, 1)

        return {
            "geschwindigkeit_kmh": speed,
            "schwellenwert_kmh": threshold,
            "hoehe_m": altitude,
            "satelliten": satellites,
            "min_satelliten": min_sats,
            "gps_fix_ok": (satellites >= min_sats) if satellites is not None else None,
            "letzter_skip_grund": getattr(self._coordinator, "last_skip_reason", None),
            "standzeit_minuten": standzeit_min,
        }

    async def async_update(self) -> None:
        """State is computed live from sensor – nothing to fetch."""
        pass
