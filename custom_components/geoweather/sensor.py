from __future__ import annotations
from datetime import datetime
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

POLLEN_TYPES = [
    ("birke", "Pollen Birke"), ("graeser", "Pollen Gräser"), ("roggen", "Pollen Roggen"),
    ("erle", "Pollen Erle"), ("hasel", "Pollen Hasel"), ("esche", "Pollen Esche"),
    ("beifuss", "Pollen Beifuß"), ("ambrosia", "Pollen Ambrosia"), ("eiche", "Pollen Eiche"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # 1. Regen- & Wetter-Sensoren
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="niederschlag_aktuell", name="Niederschlag aktuell",
        native_unit_of_measurement="mm/h", device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:weather-pouring"
    )))
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="regenvorhersage", name="Regenvorhersage", icon="mdi:weather-clock"
    )))

    # 2. Standort & Warnungen
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="standort", name="Aktueller Standort", icon="mdi:map-marker-radius"
    )))
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="warnungen_anzahl", name="Wetterwarnungen Anzahl", icon="mdi:alert-decagram"
    )))

    # 3. Pollen-Sensoren
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="pollen_gesamt", name="Pollenbelastung Gesamt", icon="mdi:flower"
    )))
    for key, name in POLLEN_TYPES:
        entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
            key=f"pollen_{key}", name=name, icon="mdi:sprout"
        )))

    # 4. Technik-Sensoren
    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="letztes_update", name="Letztes Update", 
        device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:update"
    )))

    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="warn_region", name="DWD Warnregion", icon="mdi:map-check"
    )))

    entities.append(GeoWeatherSensor(coordinator, entry, SensorEntityDescription(
        key="wind_status", name="Wind Warnstatus", icon="mdi:weather-windy"
    )))

    async_add_entities(entities)

class GeoWeatherSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_name = description.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="GeoWeather",
            manufacturer="GeoWeather",
            model="Camper Weather Terminal",
        )

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data: return None
        key = self.entity_description.key

        # 1. Radar & Regen
        regen = data.get("regen", {})
        if key == "niederschlag_aktuell": return regen.get("aktuell", 0.0)
        
        if key == "regenvorhersage": 
            val = regen.get("next_start")
            # Falls kein Regen kommt, geben wir einen Text zurück, damit das Icon bleibt
            return val if val is not None else "Kein Regen"

        # 2. Standort & Warnungen
        loc = data.get("location", {})
        if key == "standort": return loc.get("gemeinde") or loc.get("kreis") or "Unbekannt"
        
        if key == "warn_region": 
            return loc.get("warn_region_name") or loc.get("kreis") or "Unbekannt"
            
        if key == "warnungen_anzahl": 
            return data.get("warnings", {}).get("anzahl", 0)

        # 3. Pollen
        pollen = data.get("pollen", {})
        if key == "pollen_gesamt":
            # Berechnet das Maximum aller Pollenarten für heute
            vals = [v for k, v in pollen.items() if k.endswith("_today") and isinstance(v, (int, float))]
            return max(vals) if vals else 0.0

        if key.startswith("pollen_"):
            p_key = key.replace("pollen_", "")
            # Holt den Wert für heute (z.B. birke_today)
            return pollen.get(f"{p_key}_today", 0.0)

        if key == "wind_status":
            return data.get("wind", {}).get("type", "Normal")
        
        # 4. Technik
        if key == "letztes_update":
            val = data.get("last_updated")
            return datetime.fromisoformat(val) if val else None

        return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data: 
            return None
        
        key = self.entity_description.key
        pollen = data.get("pollen", {})

        # 1. Radar Attribute
        if key == "niederschlag_aktuell":
            return {"forecast": data.get("regen", {}).get("forecast", {})}
        
        if key == "regenvorhersage":
            regen = data.get("regen", {})
            return {
                "next_end": regen.get("next_end"),
                "next_length_min": regen.get("next_length"),
                "next_max_mmh": regen.get("next_max_mmh"),
                "next_sum_mm": regen.get("next_sum_mm")
            }
            
        # 2. Warnungs Attribute
        if key == "warnungen_anzahl":
            return {"aktive_warnungen": data.get("warnings", {}).get("warnungen", [])}
        
        # 3. Standort Attribute
        if key == "standort":
            loc = data.get("location", {})
            return {
                "kreis": loc.get("kreis"),
                "warncellid": loc.get("warncellid")
            }

        # 4. Pollen Attribute für den Gesamt-Sensor
        if key == "pollen_gesamt":
            return {
                "dwd_region_id": pollen.get("dwd_region_id"),
                "dwd_teilregion": pollen.get("dwd_teilregion"),
                "kreis": pollen.get("aktueller_kreis")
            }

        # 5. Vorhersage-Attribute für die einzelnen Pollen-Sensoren
        if key.startswith("pollen_") and key != "pollen_gesamt":
            p_key = key.replace("pollen_", "")
            return {
                "today": pollen.get(f"{p_key}_today", 0.0),
                "tomorrow": pollen.get(f"{p_key}_tomorrow", 0.0),
                "dayafter_to": pollen.get(f"{p_key}_dayafter_to", 0.0),
            }
            
        # 6. Wind Attribute
        if key == "wind_status":
            wind = data.get("wind", {})
            return {
                "speed_max": wind.get("speed_max", 0),
                "level": wind.get("level", 0),
                "description": wind.get("description", ""),
                "unit": "km/h"
            }

        return None
