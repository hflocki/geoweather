"""Sensors for GeoWeather – all backed by the coordinator."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeoWeatherCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GeoWeatherLocationSensor(coordinator, entry),
        GeoWeatherPollenSensor(coordinator, entry),
    ])

# ── Base ──────────────────────────────────────────────────────────────────────

class _GeoWeatherBaseSensor(CoordinatorEntity, SensorEntity):
    """Gemeinsame Basis für alle GeoWeather Sensoren."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GeoWeatherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def _data(self) -> dict:
        """Holt die Daten aus dem Coordinator."""
        return self.coordinator.data if self.coordinator.data else {}

# ── Sensor 1: Standort ────────────────────────────────────────────────────────

class GeoWeatherLocationSensor(_GeoWeatherBaseSensor):
    """Zeigt die aktuelle Gemeinde und den Kreis an."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "GeoWeather Standort"
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def native_value(self) -> str | None:
        loc = self._data.get("location", {})
        return loc.get("gemeinde", "Warte auf Update")

    @property
    def extra_state_attributes(self) -> dict:
        loc = self._data.get("location", {})
        return {
            "gemeinde": loc.get("gemeinde"),
            "kreis": loc.get("kreis"),
            "zuletzt_aktualisiert": self._data.get("last_updated"),
        }

# ── Sensor 2: Pollenflug ──────────────────────────────────────────────────────

class GeoWeatherPollenSensor(_GeoWeatherBaseSensor):
    """Höchste heutige Pollenbelastung."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "GeoWeather Pollenflug"
        self._attr_unique_id = f"{entry.entry_id}_pollen"
        self._attr_icon = "mdi:flower-pollen"

    @property
    def native_value(self) -> int | str:
        p = self._data.get("pollen", {})
        if not p:
            return "Keine Daten"
        
        # Den höchsten Wert aller Pollentypen für heute ermitteln
        vals = [v for v in p.values() if isinstance(v, int)]
        return max(vals) if vals else 0

    @property
    def extra_state_attributes(self) -> dict:
        p = self._data.get("pollen", {})
        attrs = {
            "dwd_region": self._data.get("dwd_region"),
            "zuletzt_aktualisiert": self._data.get("last_updated"),
        }
        # Alle Pollenwerte als einzelne Attribute hinzufügen
        if p:
            attrs.update(p)
        return attrs
