from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

# Pollenarten für die dynamische Erstellung
POLLEN_TYPES = [
    ("birke", "Pollen Birke"),
    ("graeser", "Pollen Gräser"),
    ("roggen", "Pollen Roggen"),
    ("erle", "Pollen Erle"),
    ("hasel", "Pollen Hasel"),
    ("esche", "Pollen Esche"),
    ("beifuss", "Pollen Beifuß"),
    ("ambrosia", "Pollen Ambrosia"),
    ("eiche", "Pollen Eiche"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Setzt alle GeoWeather Sensoren auf einmal auf."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # 1. Regen-Sensoren
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="niederschlag_aktuell",
                name="Niederschlag aktuell",
                native_unit_of_measurement="mm/h",
                device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
                state_class=SensorStateClass.MEASUREMENT,
                icon="mdi:weather-pouring",
            ),
        )
    )
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="regenvorhersage",
                name="Regenvorhersage",
                device_class=SensorDeviceClass.TIMESTAMP,
                icon="mdi:weather-clock",
            ),
        )
    )

    # 2. Standort & Warnungen
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="standort", name="Aktueller Standort", icon="mdi:map-marker-radius"
            ),
        )
    )
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="warnungen_anzahl",
                name="Wetterwarnungen",
                icon="mdi:alert-decagram",
            ),
        )
    )

    # 3. Pollen-Sensoren (General + Einzeln)
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="pollen_gesamt", name="Pollenbelastung Gesamt", icon="mdi:flower"
            ),
        )
    )
    for key, name in POLLEN_TYPES:
        entities.append(
            GeoWeatherSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"pollen_{key}", name=name, icon="mdi:sprout"
                ),
            )
        )

    async_add_entities(entities)


class GeoWeatherSensor(CoordinatorEntity, SensorEntity):
    """Repräsentiert einen GeoWeather Sensor."""

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        # Eindeutige ID und Name mit Präfix
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"GeoWeather {description.name}"

        # Zuordnung zum gleichen Gerät
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "GeoWeather",
            "manufacturer": "GeoWeather",
            "model": "Camper Weather Terminal",
        }

    @property
    def native_value(self):
        """Bestimmt den Status basierend auf dem Key."""
        data = self.coordinator.data
        key = self.entity_description.key

        # Regen-Logik
        radar = data.get("radar", {})
        if key == "niederschlag_aktuell":
            return radar.get("aktuell", 0.0)
        if key == "regenvorhersage":
            return radar.get("next_start")

        # Standort & Warnungen
        if key == "standort":
            return data.get("location", {}).get("name", "Unbekannt")
        if key == "warnungen_anzahl":
            return len(data.get("warnings", []))

        # Pollen-Logik
        pollen = data.get("pollen", {})
        if key == "pollen_gesamt":
            # Höchsten Wert aller 'heute' Pollen finden
            vals = [
                v
                for k, v in pollen.items()
                if "_heute" in k and isinstance(v, (int, float))
            ]
            return max(vals) if vals else 0.0

        if key.startswith("pollen_"):
            p_key = key.replace("pollen_", "")
            return pollen.get(f"{p_key}_heute", 0.0)

        return None

    @property
    def extra_state_attributes(self):
        """Fügt hilfreiche Attribute hinzu."""
        data = self.coordinator.data
        key = self.entity_description.key

        if key == "niederschlag_aktuell":
            return {"forecast": data.get("radar", {}).get("forecast", {})}

        if key == "regenvorhersage":
            radar = data.get("radar", {})
            return {
                "next_end": radar.get("next_end"),
                "next_length": radar.get("next_length"),
                "next_max": radar.get("next_max_mmh"),
                "next_sum": radar.get("next_sum_mm"),
            }

        if key == "warnungen_anzahl":
            return {"aktive_warnungen": data.get("warnings", [])}

        return None
