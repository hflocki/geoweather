"""Sensors for GeoWeather – location, warnings, pollen."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeoWeatherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GeoWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GeoWeatherLocationSensor(coordinator, entry),
        GeoWeatherWarningSensor(coordinator, entry),
        GeoWeatherPollenSensor(coordinator, entry),
    ])


class _GeoWeatherBaseSensor(CoordinatorEntity, SensorEntity):
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


class GeoWeatherLocationSensor(_GeoWeatherBaseSensor):
    """Current Gemeinde / Kreis / Bundesland."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Standort"
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def native_value(self) -> str:
        loc = self._data.get("location", {})
        return loc.get("gemeinde") or loc.get("status", "Warte auf GPS...")

    @property
    def extra_state_attributes(self) -> dict:
        loc = self._data.get("location", {})
        return {
            "gemeinde": loc.get("gemeinde"),
            "kreis": loc.get("kreis"),
            "bundesland": loc.get("bundesland"),
            "warncellid": loc.get("warncellid"),
            "latitude": self._gps.get("latitude"),
            "longitude": self._gps.get("longitude"),
            "hoehe_m": self._gps.get("altitude_m"),
            "satelliten": self._gps.get("satellites"),
            "geschwindigkeit_kmh": self._gps.get("speed_kmh"),
            "zuletzt_aktualisiert": self._data.get("last_updated"),
        }


class GeoWeatherWarningSensor(_GeoWeatherBaseSensor):
    """Active DWD weather warnings."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Warnungen"
        self._attr_unique_id = f"{entry.entry_id}_warnings"
        self._attr_icon = "mdi:weather-lightning"

    @property
    def native_value(self) -> str:
        warn = self._data.get("warnings", {})
        count = warn.get("anzahl")
        if count is None:
            return "Warte auf GPS..."
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
            "zuletzt_aktualisiert": self._data.get("last_updated"),
        }


class GeoWeatherPollenSensor(_GeoWeatherBaseSensor):
    """DWD pollen forecast – today / tomorrow / day-after."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Pollenflug"
        self._attr_unique_id = f"{entry.entry_id}_pollen"
        self._attr_icon = "mdi:flower-pollen"

    @property
    def native_value(self) -> str:
        p = self._data.get("pollen", {})
        status = p.get("status")
        if status and status != "OK":
            return status
        today_vals = [v for k, v in p.items() if k.endswith("_heute") and v is not None]
        return str(max(today_vals)) if today_vals else "Keine Daten"

    @property
    def extra_state_attributes(self) -> dict:
        p = self._data.get("pollen", {})
        attrs: dict = {
            "dwd_region": p.get("dwd_region"),
            "dwd_teilregion": p.get("dwd_teilregion"),
            "zuletzt_aktualisiert": self._data.get("last_updated"),
        }
        for key, val in p.items():
            if any(key.endswith(s) for s in ("_heute", "_morgen", "_uebermorgen")):
                attrs[key] = val
        return attrs
