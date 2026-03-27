"""Sensors for GeoWeather – Location, Warnings, Pollen, Rain."""
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

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .coordinator import GeoWeatherCoordinator

ATTRIBUTION = "Daten bereitgestellt vom Deutschen Wetterdienst (DWD)"


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GeoWeatherLocationSensor(coordinator, entry),
        GeoWeatherWarnungsSensor(coordinator, entry),
        GeoWeatherPollenSensor(coordinator, entry),
        GeoWeatherRainSensor(coordinator, entry),
        GeoWeatherIntervalSensor(coordinator, entry),
    ])


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GeoWeatherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="GeoWeather",
            manufacturer="DWD / hflocki",
            model="GeoWeather Integration",
            entry_type="service",
        )

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _gps(self) -> dict:
        return self._data.get("gps", {})


# ── Sensor 1: Standort ────────────────────────────────────────────────────────

class GeoWeatherLocationSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Standort"
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def native_value(self):
        # Muss eine Zahl zurückgeben (0 statt "Manuell"), da Einheit 'min' gesetzt ist
        val = self._cfg(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0
            
    @property
    def extra_state_attributes(self) -> dict:
        loc = self._data.get("location", {})
        return {
            "kreis":          loc.get("kreis"),
            "bundesland":     loc.get("bundesland"),
            "warncellid":     loc.get("warncellid"),
            "latitude":       self._gps.get("latitude"),
            "longitude":      self._gps.get("longitude"),
            "hoehe_m":        self._gps.get("altitude_m"),
            "satelliten":     self._gps.get("satellites"),
            "aktualisiert":   self._data.get("last_updated"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


# ── Sensor 2: Warnungen ───────────────────────────────────────────────────────

class GeoWeatherWarnungsSensor(_Base):
    # Integer-State → Automationen können direkt state > 0 prüfen
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:alert-rhombus"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Warnungen"
        self._attr_unique_id = f"{entry.entry_id}_warnings"

    @property
    def native_value(self) -> int:
        return self._data.get("warnings", {}).get("anzahl", 0) or 0

    @property
    def extra_state_attributes(self) -> dict:
        warn = self._data.get("warnings", {})
        return {
            "hoechste_schwere": warn.get("hoechste_schwere"),
            "warnungen":        warn.get("warnungen", []),
            "latitude":         self._gps.get("latitude"),
            "longitude":        self._gps.get("longitude"),
            "aktualisiert":     self._data.get("last_updated"),
            ATTR_ATTRIBUTION:   ATTRIBUTION,
        }


# ── Sensor 3: Pollenflug ──────────────────────────────────────────────────────

class GeoWeatherPollenSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Pollenflug"
        self._attr_unique_id = f"{entry.entry_id}_pollen"
        self._attr_icon = "mdi:flower-pollen"

    @property
    def native_value(self) -> str:
        p = self._data.get("pollen", {})
        if p.get("status") and p["status"] != "OK":
            return p["status"]
        # Höchsten Heute-Wert numerisch bestimmen (Strings wie "1-2" → 2)
        def _to_num(v):
            try:
                s = str(v).strip()
                return float(s.split("-")[-1]) if "-" in s else float(s)
            except (ValueError, TypeError):
                return 0.0
        today_vals = [v for k, v in p.items() if k.endswith("_heute") and v not in (None, "0")]
        return str(max(today_vals, key=_to_num)) if today_vals else "0"

    @property
    def extra_state_attributes(self) -> dict:
        p = self._data.get("pollen", {})
        attrs: dict = {
            "dwd_region":     p.get("dwd_region"),
            "dwd_teilregion": p.get("dwd_teilregion"),
            "region_id":      p.get("region_id"),
            "aktualisiert":   self._data.get("last_updated"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        for key, val in p.items():
            if any(key.endswith(s) for s in ("_heute", "_morgen", "_uebermorgen")):
                attrs[key] = val
        return attrs


# ── Sensor 4: Regenvorhersage ──────────────────────────────────────────────────

class GeoWeatherRainSensor(_Base):
    _attr_native_unit_of_measurement = "mm/h"
    _attr_device_class = SensorDeviceClass.PRECIPITATION_INTENSITY
    _attr_state_class  = SensorStateClass.MEASUREMENT

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
            "forecast":       r.get("forecast"),
            "next_start":     r.get("next_start"),
            "next_end":       r.get("next_end"),
            "next_length_min":r.get("next_length"),
            "next_max_mmh":   r.get("next_max_mmh"),
            "next_sum_mm":    r.get("next_sum_mm"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


# ── Sensor 5: API-Intervall ────────────────────────────────────────────────────

class GeoWeatherIntervalSensor(_Base):
    """Zeigt das konfigurierte Auto-Poll-Intervall an."""
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-sync"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "API Call Intervall"
        self._attr_unique_id = f"{entry.entry_id}_interval"

    @property
    def _cfg(self, key, default=None):
        return {**self._entry.data, **self._entry.options}.get(key, default)

    @property
    def extra_state_attributes(self) -> dict:
        val = self.native_value
        return {
            "modus": "Automatisch" if val > 0 else "Manuell (nur Service/Button)",
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def _cfg(self, key, default=None):
        return {**self._entry.data, **self._entry.options}.get(key, default)
