"""Sensors for GeoWeather."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GeoWeatherLocationSensor(coordinator, entry),
        GeoWeatherPollenSensor(coordinator, entry),
    ])

class GeoWeatherLocationSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Standort"
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def native_value(self):
        return self.coordinator.data.get("location", {}).get("gemeinde", "Unbekannt") if self.coordinator.data else "Warte..."

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data: return {}
        loc = self.coordinator.data.get("location", {})
        return {
            "kreis": loc.get("kreis"),
            "aktualisiert": self.coordinator.data.get("last_updated")
        }

class GeoWeatherPollenSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Pollenflug"
        self._attr_unique_id = f"{entry.entry_id}_pollen"
        self._attr_icon = "mdi:flower-pollen"

    @property
    def native_value(self):
        if not self.coordinator.data: return 0
        p = self.coordinator.data.get("pollen", {})
        vals = [v for v in p.values() if isinstance(v, int)]
        return max(vals) if vals else 0

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data: return {}
        attrs = {"region": self.coordinator.data.get("dwd_region")}
        attrs.update(self.coordinator.data.get("pollen", {}))
        return attrs
