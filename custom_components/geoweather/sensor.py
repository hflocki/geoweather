"""Sensors for GeoWeather – Location, Warnings, Pollen, Rain, API-Interval."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_UPDATE_INTERVAL
from .coordinator import GeoWeatherCoordinator

ATTRIBUTION = "Daten bereitgestellt vom Deutschen Wetterdienst (DWD)"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up the sensor platform."""
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        GeoWeatherLocationSensor(coordinator, entry),
        GeoWeatherWarnungsSensor(coordinator, entry),
        GeoWeatherPollenSensor(coordinator, entry),
        GeoWeatherRainSensor(coordinator, entry),
        GeoWeatherIntervalSensor(coordinator, entry), # Der neue Sensor
    ])


class _Base(CoordinatorEntity, SensorEntity):
    """Base class for GeoWeather sensors."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: GeoWeatherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._data = coordinator.data or {}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="GeoWeather",
            manufacturer="DWD / hflocki",
            model="GeoWeather Integration",
        )

    def _handle_coordinator_update(self) -> None:
        """Update data when coordinator has new info."""
        self._data = self.coordinator.data or {}
        self.async_write_ha_state()

# --- Sensor 1: Standort ---
class GeoWeatherLocationSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Standort"
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def native_value(self):
        return self._data.get("location", {}).get("gemeinde", "Warten...")

    @property
    def extra_state_attributes(self):
        l = self._data.get("location", {})
        g = self._data.get("gps", {})
        return {
            "kreis": l.get("kreis"),
            "bundesland": l.get("bundesland"),
            "warncellid": l.get("warncellid"),
            "latitude": g.get("latitude"),
            "longitude": g.get("longitude"),
            "hoehe_m": g.get("altitude_m"),
            "satelliten": g.get("satellites"),
            "aktualisiert": self._data.get("last_updated"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

# --- Sensor 2: Warnungen ---
class GeoWeatherWarnungsSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Warnungen"
        self._attr_unique_id = f"{entry.entry_id}_warnings"
        self._attr_icon = "mdi:alert-outline"

    @property
    def native_value(self):
        return self._data.get("warnings", {}).get("anzahl", 0)

    @property
    def extra_state_attributes(self):
        return {
            "warnungen": self._data.get("warnings", {}).get("warnungen", []),
            "aktualisiert": self._data.get("last_updated"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

# --- Sensor 3: Pollenflug ---
class GeoWeatherPollenSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Pollenflug"
        self._attr_unique_id = f"{entry.entry_id}_pollen"
        self._attr_icon = "mdi:flower"

    @property
    def native_value(self):
        return self._data.get("pollen", {}).get("dwd_region", "Nicht bereit")

    @property
    def extra_state_attributes(self):
        p = self._data.get("pollen", {})
        attrs = {
            "dwd_teilregion": p.get("dwd_teilregion"),
            "region_id": p.get("region_id"),
            "aktualisiert": self._data.get("last_updated"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        for key, val in p.items():
            if any(key.endswith(s) for s in ("_heute", "_morgen", "_uebermorgen")):
                attrs[key] = val
        return attrs

# --- Sensor 4: Regen ---
class GeoWeatherRainSensor(_Base):
    _attr_native_unit_of_measurement = "mm/h"
    _attr_device_class = SensorDeviceClass.PRECIPITATION_INTENSITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Regenvorhersage"
        self._attr_unique_id = f"{entry.entry_id}_rain"
        self._attr_icon = "mdi:weather-pouring"

    @property
    def native_value(self) -> float:
        return self._data.get("regen", {}).get("aktuell", 0.0)

    @property
    def extra_state_attributes(self) -> dict:
        r = self._data.get("regen", {})
        return {
            "forecast": r.get("forecast"),
            "next_start": r.get("next_start"),
            "next_end": r.get("next_end"),
            "next_length": r.get("next_length"),
            "next_max_mmh": r.get("next_max_mmh"),
            "next_sum_mm": r.get("next_sum_mm"),
            "aktualisiert": self._data.get("last_updated"),
        }

# --- Sensor 5: API-Intervall (NEU) ---
class GeoWeatherIntervalSensor(_Base):
    """Shows the currently set update interval."""
    _attr_name = "API Call Intervall"
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-sync"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_interval"

    @property
    def native_value(self):
        val = self._entry.options.get(CONF_UPDATE_INTERVAL, 0)
        return val if val > 0 else "Manuell"
