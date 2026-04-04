from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

POLLEN_TYPES = [
    ("birke", "Pollen Birke"),
    ("graeser", "Pollen Graeser"),
    ("roggen", "Pollen Roggen"),
    ("erle", "Pollen Erle"),
    ("hasel", "Pollen Hasel"),
    ("esche", "Pollen Esche"),
    ("beifuss", "Pollen Beifuss"),
    ("ambrosia", "Pollen Ambrosia"),
    ("eiche", "Pollen Eiche"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # ── 1. REGEN: Aktuell ────────────────────────────────────────────────────
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

    # ── 2. REGEN: Vorhersage naechste 2 Stunden ──────────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="regen_vorhersage_2h",
                name="Regen Vorhersage 2h",
                icon="mdi:weather-rainy",
            ),
        )
    )

    # ── 3. WIND: Aktuell (aus DWD-Warnungen) ─────────────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="wind_aktuell",
                name="Wind aktuell",
                icon="mdi:weather-windy",
            ),
        )
    )

    # ── 4. WIND: Vorhersage (naechste aktive Windwarnung) ────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="wind_vorhersage",
                name="Wind Vorhersage",
                icon="mdi:weather-windy-variant",
            ),
        )
    )

    # ── 5. Standort & Warnungen ──────────────────────────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="standort",
                name="Aktueller Standort",
                icon="mdi:map-marker-radius",
            ),
        )
    )
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="warnungen_anzahl",
                name="Wetterwarnungen Anzahl",
                icon="mdi:alert-decagram",
            ),
        )
    )
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="warn_region",
                name="DWD Warnregion",
                icon="mdi:map-check",
            ),
        )
    )

    # ── 6. Legacy-Sensor (Rueckwaertskompatibilitaet) ────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="regenvorhersage",
                name="Regenvorhersage (legacy)",
                icon="mdi:weather-clock",
            ),
        )
    )
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="wind_status",
                name="Wind Warnstatus",
                icon="mdi:weather-windy",
            ),
        )
    )

    # ── 7. Pollen ────────────────────────────────────────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="pollen_gesamt",
                name="Pollenbelastung Gesamt",
                icon="mdi:flower",
            ),
        )
    )
    for key, name in POLLEN_TYPES:
        entities.append(
            GeoWeatherSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"pollen_{key}",
                    name=name,
                    icon="mdi:sprout",
                ),
            )
        )

    # ── 8. Technik ───────────────────────────────────────────────────────────
    entities.append(
        GeoWeatherSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="letztes_update",
                name="Letztes Update",
                device_class=SensorDeviceClass.TIMESTAMP,
                icon="mdi:update",
            ),
        )
    )

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
        if not data:
            return None
        key = self.entity_description.key

        # ── REGEN aktuell ───────────────────────────────────────────────────
        regen = data.get("regen", {})
        if key == "niederschlag_aktuell":
            return regen.get("aktuell", 0.0)

        # ── REGEN Vorhersage 2h ─────────────────────────────────────────────
        if key == "regen_vorhersage_2h":
            f2h = regen.get("forecast_2h", {})
            if not f2h:
                return "Keine Daten"
            if f2h.get("raining_now"):
                return "Regen jetzt"
            if f2h.get("rain_expected"):
                mins = f2h.get("next_rain_in_min", 0)
                return f"Regen in {mins} min"
            return "Kein Regen (2h)"

        # ── WIND aktuell ────────────────────────────────────────────────────
        if key == "wind_aktuell":
            wind = data.get("wind", {})
            return wind.get("type", "Normal")

        # ── WIND Vorhersage ─────────────────────────────────────────────────
        if key == "wind_vorhersage":
            warnings = data.get("warnings", {}).get("warnungen", [])
            wind_warns = [
                w
                for w in warnings
                if any(
                    word in w.get("ereignis", "").lower()
                    for word in ["wind", "sturm", "boen", "orkan"]
                )
            ]
            if not wind_warns:
                return "Keine Windwarnung"
            # Schlimmste aktive Warnung
            worst = sorted(
                wind_warns, key=lambda x: x.get("schwere_level", 0), reverse=True
            )[0]
            return worst.get("ereignis", "Windwarnung")

        # ── Legacy / Compat ─────────────────────────────────────────────────
        if key == "regenvorhersage":
            val = regen.get("next_start")
            return val if val is not None else "Kein Regen"

        if key == "wind_status":
            return data.get("wind", {}).get("type", "Normal")

        # ── Standort & Warnungen ────────────────────────────────────────────
        loc = data.get("location", {})
        if key == "standort":
            return loc.get("gemeinde") or loc.get("kreis") or "Unbekannt"
        if key == "warn_region":
            return loc.get("warn_region_name") or loc.get("kreis") or "Unbekannt"
        if key == "warnungen_anzahl":
            return data.get("warnings", {}).get("anzahl", 0)

        # ── Pollen ──────────────────────────────────────────────────────────
        pollen = data.get("pollen", {})
        if key == "pollen_gesamt":
            vals = [
                v
                for k, v in pollen.items()
                if k.endswith("_today") and isinstance(v, (int, float))
            ]
            return max(vals) if vals else 0.0
        if key.startswith("pollen_"):
            p_key = key.replace("pollen_", "")
            return pollen.get(f"{p_key}_today", 0.0)

        # ── Technik ─────────────────────────────────────────────────────────
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
        regen = data.get("regen", {})
        pollen = data.get("pollen", {})

        # ── REGEN aktuell: Attribute ─────────────────────────────────────────
        if key == "niederschlag_aktuell":
            return {
                "forecast": regen.get("forecast", {}),
                "raining_now": (regen.get("aktuell", 0.0) or 0.0) > 0,
            }

        # ── REGEN Vorhersage 2h: Attribute ──────────────────────────────────
        if key == "regen_vorhersage_2h":
            f2h = regen.get("forecast_2h", {})
            return {
                "raining_now": f2h.get("raining_now", False),
                "rain_expected": f2h.get("rain_expected", False),
                "next_rain_start": f2h.get("next_rain_start"),
                "next_rain_end": f2h.get("next_rain_end"),
                "next_rain_in_min": f2h.get("next_rain_in_min"),
                "duration_min": f2h.get("duration_min", 0),
                "max_intensity_mmh": f2h.get("max_intensity_mmh", 0.0),
                "total_mm": f2h.get("total_mm", 0.0),
                "forecast_steps": f2h.get("forecast_steps", {}),
            }

        # ── WIND aktuell: Attribute ──────────────────────────────────────────
        if key == "wind_aktuell":
            wind = data.get("wind", {})
            return {
                "speed_max_kmh": wind.get("speed_max", 0),
                "level": wind.get("level", 0),
                "description": wind.get("description", ""),
                "unit": "km/h",
            }

        # ── WIND Vorhersage: Attribute ───────────────────────────────────────
        if key == "wind_vorhersage":
            warnings = data.get("warnings", {}).get("warnungen", [])
            wind_warns = [
                w
                for w in warnings
                if any(
                    word in w.get("ereignis", "").lower()
                    for word in ["wind", "sturm", "boen", "orkan"]
                )
            ]
            wind_warns_sorted = sorted(
                wind_warns, key=lambda x: x.get("schwere_level", 0), reverse=True
            )
            attrs = {
                "anzahl_windwarnungen": len(wind_warns),
                "warnungen": [
                    {
                        "ereignis": w.get("ereignis"),
                        "schwere": w.get("schwere"),
                        "headline": w.get("headline"),
                        "beginn": w.get("beginn"),
                        "ende": w.get("ende"),
                        "speed_kmh": w.get("speed_kmh", 0),
                    }
                    for w in wind_warns_sorted
                ],
            }
            if wind_warns_sorted:
                worst = wind_warns_sorted[0]
                attrs.update(
                    {
                        "naechste_warnung_beginn": worst.get("beginn"),
                        "naechste_warnung_ende": worst.get("ende"),
                        "naechste_warnung_schwere": worst.get("schwere"),
                        "beschreibung": worst.get("beschreibung", ""),
                    }
                )
            return attrs

        # ── Legacy regen ─────────────────────────────────────────────────────
        if key == "regenvorhersage":
            return {
                "next_end": regen.get("next_end"),
                "next_length_min": regen.get("next_length"),
                "next_max_mmh": regen.get("next_max_mmh"),
                "next_sum_mm": regen.get("next_sum_mm"),
            }

        # ── Warnungen ────────────────────────────────────────────────────────
        if key == "warnungen_anzahl":
            return {"aktive_warnungen": data.get("warnings", {}).get("warnungen", [])}

        # ── Standort ─────────────────────────────────────────────────────────
        if key == "standort":
            loc = data.get("location", {})
            return {
                "kreis": loc.get("kreis"),
                "warncellid": loc.get("warncellid"),
            }

        # ── Pollen gesamt ────────────────────────────────────────────────────
        if key == "pollen_gesamt":
            return {
                "dwd_region_id": pollen.get("dwd_region_id"),
                "dwd_teilregion": pollen.get("dwd_teilregion"),
                "kreis": pollen.get("aktueller_kreis"),
            }

        # ── Pollen einzeln ───────────────────────────────────────────────────
        if key.startswith("pollen_") and key != "pollen_gesamt":
            p_key = key.replace("pollen_", "")
            return {
                "today": pollen.get(f"{p_key}_today", 0.0),
                "tomorrow": pollen.get(f"{p_key}_tomorrow", 0.0),
                "dayafter_to": pollen.get(f"{p_key}_dayafter_to", 0.0),
            }

        # ── Wind legacy ──────────────────────────────────────────────────────
        if key == "wind_status":
            wind = data.get("wind", {})
            return {
                "speed_max": wind.get("speed_max", 0),
                "level": wind.get("level", 0),
                "description": wind.get("description", ""),
                "unit": "km/h",
            }

        return None
