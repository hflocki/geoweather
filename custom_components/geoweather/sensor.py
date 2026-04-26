"""Sensor platform for GeoWeather v2.4.1 - International Safety Edition."""

from __future__ import annotations
from datetime import datetime
from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

POLLEN_TYPES = [
    ("birke", "Pollen Birke"), ("graeser", "Pollen Graeser"), ("roggen", "Pollen Roggen"),
    ("erle", "Pollen Erle"), ("hasel", "Pollen Hasel"), ("esche", "Pollen Esche"),
    ("beifuss", "Pollen Beifuss"), ("ambrosia", "Pollen Ambrosia"), ("eiche", "Pollen Eiche"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Sensoren definieren
    keys = [
        ("niederschlag_aktuell", "Niederschlag aktuell", "mm/h", SensorDeviceClass.PRECIPITATION_INTENSITY, "mdi:weather-pouring"),
        ("regen_vorhersage_2h", "Regen Vorhersage 2h", None, None, "mdi:weather-rainy"),
        ("wind_aktuell", "Wind aktuell", None, None, "mdi:weather-windy"),
        ("wind_vorhersage", "Wind Vorhersage", None, None, "mdi:weather-windy-variant"),
        ("standort", "Aktueller Standort", None, None, "mdi:map-marker-radius"),
        ("warnungen_anzahl", "Wetterwarnungen Anzahl", None, None, "mdi:alert-decagram"),
        ("warn_region", "DWD Warnregion", None, None, "mdi:map-check"),
        ("regenvorhersage", "Regenvorhersage (legacy)", None, None, "mdi:weather-clock"),
        ("wind_status", "Wind Warnstatus", None, None, "mdi:weather-windy"),
        ("pollen_gesamt", "Pollenbelastung Gesamt", None, None, "mdi:flower"),
        ("letztes_update", "Letztes Update", None, SensorDeviceClass.TIMESTAMP, "mdi:update"),
    ]

    for key, name, unit, dev_class, icon in keys:
        entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
            key=key, name=name, native_unit_of_measurement=unit, device_class=dev_class, 
            state_class=SensorStateClass.MEASUREMENT if unit else None, icon=icon
        )))

    for key, name in POLLEN_TYPES:
        entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(key=f"pollen_{key}", name=name, icon="mdi:sprout")))

    async_add_entities(entities)

class GeoWeatherSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="GeoWeather", manufacturer="GeoWeather", model="Camper Weather Terminal")

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data: return None
        key = self.entity_description.key
        
        # Sicherer Zugriff mit .get()
        regen = data.get("regen", {})
        wind = data.get("wind", {})
        loc = data.get("location", {})
        warns = data.get("warnings", {})
        pollen = data.get("pollen", {})

        if key == "niederschlag_aktuell": return regen.get("aktuell", 0.0)
        if key == "regen_vorhersage_2h":
            f2h = regen.get("forecast_2h", {})
            if not f2h: return "Keine Daten"
            if f2h.get("raining_now"): return "Regen jetzt"
            if f2h.get("rain_expected"): return f"Regen in {f2h.get('next_rain_in_min', 0)} min"
            return "Kein Regen (2h)"
        if key == "wind_aktuell" or key == "wind_status": return wind.get("type", "Normal")
        if key == "wind_vorhersage":
            wind_warns = [w for w in warns.get("warnungen", []) if any(x in w.get("ereignis", "").lower() for x in ["wind","sturm","boen","orkan"])]
            return sorted(wind_warns, key=lambda x: x.get("schwere_level", 0), reverse=True)[0].get("ereignis") if wind_warns else "Keine Windwarnung"
        if key == "regenvorhersage": return regen.get("next_start") or "Kein Regen"
        if key == "standort": return loc.get("gemeinde") or loc.get("kreis") or "Unbekannt"
        if key == "warn_region": return loc.get("kreis") or "Unbekannt"
        if key == "warnungen_anzahl": return warns.get("anzahl", 0)
        if key == "pollen_gesamt":
            vals = [v for k, v in pollen.items() if k.endswith("_today") and isinstance(v, (int, float))]
            return max(vals) if vals else 0.0
        if key.startswith("pollen_"): return pollen.get(f"{key.replace('pollen_', '')}_today", 0.0)
        if key == "letztes_update":
            val = data.get("last_updated")
            return datetime.fromisoformat(val) if val else None
        return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data: return None
        key = self.entity_description.key
        regen = data.get("regen", {})
        wind = data.get("wind", {})
        pollen = data.get("pollen", {})

        if key == "niederschlag_aktuell": return {"forecast": regen.get("forecast", {}), "raining_now": (regen.get("aktuell", 0.0) or 0.0) > 0}
        if key == "regen_vorhersage_2h": return regen.get("forecast_2h", {})
        if key == "wind_aktuell" or key == "wind_status": return {"speed_max_kmh": wind.get("speed_max", 0), "level": wind.get("level", 0), "description": wind.get("description", "")}
        if key == "warnungen_anzahl": return {"aktive_warnungen": data.get("warnings", {}).get("warnungen", [])}
        if key == "standort": return {"kreis": data.get("location", {}).get("kreis"), "warncellid": data.get("location", {}).get("warncellid")}
        if key == "pollen_gesamt": return {"dwd_region_id": pollen.get("dwd_region_id"), "dwd_teilregion": pollen.get("dwd_teilregion"), "kreis": pollen.get("aktueller_kreis")}
        if key.startswith("pollen_"):
            p_key = key.replace("pollen_", "")
            return {"today": pollen.get(f"{p_key}_today", 0.0), "tomorrow": pollen.get(f"{p_key}_tomorrow", 0.0), "dayafter_to": pollen.get(f"{p_key}_dayafter_to", 0.0)}
        return None
