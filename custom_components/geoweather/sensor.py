"""Sensors for GeoWeather – Location, Warnings, Pollen, Rain."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeoWeatherCoordinator


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    """Setup sensors from a config entry."""
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            GeoWeatherLocationSensor(coordinator, entry),
            GeoWeatherWarnungsSensor(coordinator, entry),
            GeoWeatherPollenSensor(coordinator, entry),
            GeoWeatherRainSensor(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity, SensorEntity):
    """Basis-Klasse für alle GeoWeather Sensoren."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GeoWeatherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

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
    def native_value(self) -> str:
        loc = self._data.get("location", {})
        return loc.get("gemeinde") or loc.get("status", "Unbekannt")

    @property
    def extra_state_attributes(self) -> dict:
        loc = self._data.get("location", {})
        return {
            "kreis": loc.get("kreis"),
            "bundesland": loc.get("bundesland"),
            "warncellid": loc.get("warncellid"),
            "latitude": self._gps.get("latitude"),
            "longitude": self._gps.get("longitude"),
            "hoehe_m": self._gps.get("altitude_m"),
            "satelliten": self._gps.get("satellites"),
            "aktualisiert": self._data.get("last_updated"),
        }


# ── Sensor 2: Warnungen ───────────────────────────────────────────────────────


class GeoWeatherWarnungsSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Warnungen"
        self._attr_unique_id = f"{entry.entry_id}_warnings"
        self._attr_icon = "mdi:alert-rhombus"

    @property
    def native_value(self) -> str:
        warn = self._data.get("warnings", {})
        count = warn.get("anzahl")
        if count is None:
            return "Unbekannt"
        return "Keine Warnungen" if count == 0 else f"{count} Warnung(en)"

    @property
    def extra_state_attributes(self) -> dict:
        warn = self._data.get("warnings", {})
        return {
            "anzahl_warnungen": warn.get("anzahl"),
            "hoechste_schwere": warn.get("hoechste_schwere"),
            "warnungen": warn.get("warnungen", []),
            "latitude": self._gps.get("latitude"),
            "longitude": self._gps.get("longitude"),
            "aktualisiert": self._data.get("last_updated"),
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

        # Den höchsten Belastungswert von heute ermitteln
        today_vals = [v for k, v in p.items() if k.endswith("_heute") and v is not None]
        try:
            return str(max(today_vals)) if today_vals else "0"
        except (ValueError, TypeError):
            return "0"

    @property
    def extra_state_attributes(self) -> dict:
        p = self._data.get("pollen", {})
        attrs = {
            "dwd_region": p.get("dwd_region"),
            "dwd_teilregion": p.get("dwd_teilregion"),
            "aktualisiert": self._data.get("last_updated"),
        }
        # Alle Pollenwerte (heute, morgen, übermorgen) in die Attribute packen
        for key, val in p.items():
            if any(key.endswith(s) for s in ("_heute", "_morgen", "_uebermorgen")):
                attrs[key] = val
        return attrs


# ── Sensor 4: Regenvorhersage ──────────────────────────────────────────────────


class GeoWeatherRainSensor(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Regenvorhersage"
        self._attr_unique_id = f"{entry.entry_id}_rain"
        self._attr_icon = "mdi:weather-pouring"
        self._attr_native_unit_of_measurement = "mm/h"
        self._attr_device_class = SensorDeviceClass.PRECIPITATION_INTENSITY
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        regen_data = self._data.get("regen", {})
        return regen_data.get("aktuell", 0.0)

    @property
    def extra_state_attributes(self) -> dict:
        regen_data = self._data.get("regen", {})
        return {
            "forecast": regen_data.get("forecast"),
            "next_start": regen_data.get("next_start"),
            "next_end": regen_data.get("next_end"),
            "next_length": regen_data.get("next_length"),
            "attribution": "Data provided by DWD",
        }
