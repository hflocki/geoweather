"""DataUpdateCoordinator for GeoWeather v2.4.0."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALT_SENSOR,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
    DWD_EVENT_TYPES,
    DWD_SEVERITY,
    POLLEN_TYPES,
    URL_DWD_POLLEN,
    URL_DWD_RADAR,
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS_GEMEINDE,
    URL_DWD_WARNINGS_KREIS,
)
from .dwdradar import DWDRadar
from .mapping import POLLEN_REGION_MAPPING

_LOGGER = logging.getLogger(__name__)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Central hub for location, warnings, pollen, wind and radar data - v2.4.0.

    Kein internes Update-Intervall, kein Arrival-Delay.
    Alle Updates werden ausschließlich per Automation / Service-Call gesteuert.

    Empfohlene Automations in Home Assistant:
    ──────────────────────────────────────────
    1. Steht-Update mit Verzögerung:
       Trigger: state → speed_sensor wechselt auf ≤ Schwellwert
       Bedingung: speed_sensor bleibt ≤ Schwellwert für X Minuten (for: "00:10:00")
       Aktion: service: geoweather.update

    2. Sofort-Update (z.B. bei Ankunft zu Hause):
       Trigger: zone → person betritt Zone „home"
       Aktion: service: geoweather.update

    3. Periodisches Steht-Update (z.B. alle 30 Minuten wenn nicht bewegt):
       Trigger: time_pattern → minutes: "/30"
       Bedingung: speed_sensor ≤ Schwellwert
       Aktion: service: geoweather.update

    Wenn man fährt: KEINE der Automations soll feuern (Bedingung prüfen!).
    """

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator – kein automatischer Timer."""
        # update_interval=None → HA löst NIEMALS selbst einen Refresh aus
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry

        # --- State Trackers ---
        self.last_skip_reason: str | None = None
        self._radar_etag: str | None = None
        self._radar_bytes: bytes | None = None
        self._pollen_mapping = POLLEN_REGION_MAPPING

        # --- Pollen Trackers ---
        self.last_pollen_date: date | None = None
        self.last_pollen_pos: tuple[float, float] = (0.0, 0.0)
        self.pollen_cache: dict = {}
        self._force_pollen_update: bool = False

    def _extract_wind_info(self, warnings):
        """Extrahiert Wind-Level und km/h aus den DWD-Warnungen."""
        wind_data = {
            "level": 0,
            "speed_max": 0,
            "type": "Normal",
            "description": "Keine Windwarnung",
        }

        for warn in warnings:
            ereignis = warn.get("ereignis", "").lower()
            if any(word in ereignis for word in ["wind", "sturm", "böen", "orkan"]):
                if warn["schwere_level"] > wind_data["level"]:
                    wind_data["level"] = warn["schwere_level"]
                    wind_data["type"] = warn.get("ereignis", "Windwarnung")
                    wind_data["description"] = warn.get("headline", "")

                    desc = warn.get("beschreibung", "")
                    match = re.search(r"(\d+)\s*km/h", desc)
                    if match:
                        wind_data["speed_max"] = int(match.group(1))

        return wind_data

    async def _async_update_data(self) -> dict:
        """Führt genau einen vollständigen Datenabruf durch.

        Diese Methode wird NUR aufgerufen wenn:
        - async_config_entry_first_refresh() beim HA-Start aufgerufen wird
        - Eine Automation / ein Service-Call async_refresh() auslöst

        Es gibt hier keine Bewegungs- oder Delay-Logik mehr – das ist
        vollständig Aufgabe der Automations in Home Assistant.
        """
        now = datetime.now(timezone.utc)

        if not self._has_valid_fix():
            self.last_skip_reason = "Kein GPS-Fix (Sats < Min)"
            _LOGGER.debug("GeoWeather: Update übersprungen – %s", self.last_skip_reason)
            return self.data or {}

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            self.last_skip_reason = "Keine gültigen GPS-Koordinaten"
            return self.data or {}

        _LOGGER.debug("GeoWeather: Starte Datenabruf für %.5f, %.5f", lat, lon)

        current_data = self.data if self.data is not None else {}
        warnings_data = current_data.get("warnings", {})
        radar_data = current_data.get("radar", {})

        # --- Wetter-, Warnungs- und Radardaten abrufen ---
        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings_data = await self._fetch_warnings(session, lat, lon)
                radar_data = await self._fetch_radar(session, lat, lon)
                weather_data = location
                self.last_skip_reason = None
        except Exception as exc:
            _LOGGER.error("GeoWeather: Fehler beim Datenabruf: %s", exc)
            weather_data = current_data.get("location", {})

        # --- Pollen-Daten ---
        current_pos = (round(lat, 2), round(lon, 2))
        moved = current_pos != self.last_pollen_pos
        is_time_for_daily = now.hour >= 12 and self.last_pollen_date != now.date()
        is_forced = self._force_pollen_update

        pollen_should_update = is_forced or moved or is_time_for_daily

        # Kreisnamen immer aktuell halten
        try:
            async with aiohttp.ClientSession() as session:
                loc_for_pollen = await self._fetch_location(session, lat, lon)
                kreis_name = loc_for_pollen.get("kreis", "Unbekannt")
        except Exception:
            kreis_name = "Unbekannt"

        if pollen_should_update:
            try:
                async with aiohttp.ClientSession() as session:
                    pollen_data = await self._fetch_pollen(session, kreis_name)
                    self.pollen_cache = pollen_data
                    self.last_pollen_pos = current_pos
                    self.last_pollen_date = now.date()
                    self._force_pollen_update = False
            except Exception as exc:
                _LOGGER.error("GeoWeather: Pollen-Abruf fehlgeschlagen: %s", exc)
                pollen_data = self.pollen_cache
        else:
            pollen_data = self.pollen_cache

        pollen_data["aktueller_kreis"] = kreis_name

        # --- Wind aus Warnungen ---
        wind_info = self._extract_wind_info(warnings_data.get("warnungen", []))

        # --- Regen-Dict ---
        regen_data = {
            "aktuell": radar_data.get("aktuell", 0.0),
            "next_start": radar_data.get("next_start"),
            "next_end": radar_data.get("next_end"),
            "next_length": radar_data.get("next_length", 0),
            "next_max_mmh": radar_data.get("next_max_mmh", 0.0),
            "next_sum_mm": radar_data.get("next_sum_mm", 0.0),
            "forecast_2h": radar_data.get("forecast_2h", {}),
            "forecast": radar_data.get("forecast", {}),
        }

        return {
            "location": weather_data,
            "radar": radar_data,
            "regen": regen_data,
            "warnings": warnings_data,
            "pollen": pollen_data,
            "wind": wind_info,
            "gps": {"latitude": lat, "longitude": lon},
            "last_updated": now.isoformat(),
        }

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str) -> dict:
        """Sucht die Region-ID und ruft DWD Daten ab."""
        suche_ort = str(kreis).strip()
        target_id = self._pollen_mapping.get(suche_ort)

        if target_id is None:
            _LOGGER.warning(
                "[Pollen Mapping] Kein ID-Mapping für Ort '%s' gefunden! "
                "Bitte in der mapping.py ergänzen.",
                suche_ort,
            )
            return {f"{p.lower()}_today": 0.0 for p in POLLEN_TYPES}

        try:
            async with session.get(URL_DWD_POLLEN) as resp:
                if resp.status != 200:
                    return {"dwd_teilregion": "Server-Fehler"}
                data = await resp.json(content_type=None)
        except Exception as e:
            _LOGGER.error("Pollen-Abruf fehlgeschlagen: %s", e)
            return {"dwd_teilregion": "Abruffehler"}

        res = {"dwd_teilregion": "Unbekannt", "dwd_region_id": target_id}
        all_today_values = []

        def _convert_to_index(val):
            v = str(val).strip()
            mapping = {
                "0": 0.0,
                "0-1": 1.0,
                "1": 2.0,
                "1-2": 3.0,
                "2": 4.0,
                "2-3": 5.0,
                "3": 6.0,
            }
            return mapping.get(v, 0.0)

        def _clean(text):
            return (
                str(text)
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
            )

        found_entry = None
        for entry in data.get("content", []):
            t_str = str(target_id)
            if t_str == str(entry.get("partregion_id")) or t_str == str(
                entry.get("region_id")
            ):
                found_entry = entry
                break

        if found_entry:
            res["dwd_teilregion"] = found_entry.get(
                "partregion_name"
            ) or found_entry.get("region_name")
            pdata = found_entry.get("Pollen") or found_entry.get("pollen") or {}

            for p_type in POLLEN_TYPES:
                clean_type = _clean(p_type)
                val_today, val_tomorrow = 0.0, 0.0

                for dwd_key, dwd_content in pdata.items():
                    if clean_type == _clean(dwd_key):
                        val_today = _convert_to_index(dwd_content.get("today"))
                        val_tomorrow = _convert_to_index(dwd_content.get("tomorrow"))
                        break

                res[f"{clean_type}_today"] = val_today
                res[f"{clean_type}_tomorrow"] = val_tomorrow
                res[f"pollen_{clean_type}"] = val_today
                all_today_values.append(val_today)

            res["pollen_max_today"] = max(all_today_values) if all_today_values else 0.0
        return res

    async def _fetch_location(self, session, lat, lon) -> dict:
        import time

        t = int(time.time())
        url = (
            URL_DWD_WARNCELL.format(
                south=lat - 0.005, west=lon - 0.005, north=lat + 0.005, east=lon + 0.005
            )
            + f"&_={t}"
        )
        async with session.get(url) as resp:
            if resp.status != 200:
                return {"gemeinde": "Fehler", "kreis": "Unbekannt"}
            data = await resp.json(content_type=None)
        if not data.get("features"):
            return {"gemeinde": "Unbekannt", "kreis": "Unbekannt"}
        p = data["features"][0]["properties"]
        return {
            "gemeinde": p.get("NAME"),
            "kreis": p.get("KREIS"),
            "warncellid": p.get("WARNCELLID"),
        }

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        import time

        t = int(time.time())
        urls = [
            URL_DWD_WARNINGS_GEMEINDE.format(
                south=lat - 0.005, west=lon - 0.005, north=lat + 0.005, east=lon + 0.005
            )
            + f"&_={t}",
            URL_DWD_WARNINGS_KREIS.format(
                south=lat - 0.005, west=lon - 0.005, north=lat + 0.005, east=lon + 0.005
            )
            + f"&_={t}",
        ]
        all_features = []
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        all_features.extend(data.get("features", []))
            except Exception as e:
                _LOGGER.error("Warnungs-Fehler: %s", e)

        items = []
        seen_ids = set()
        sev_map = {"Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}
        for feat in all_features:
            p = feat.get("properties", {})
            unique_id = f"{p.get('EVENT')}_{p.get('HEADLINE')}"
            if unique_id in seen_ids:
                continue
            seen_ids.add(unique_id)
            raw_event = p.get("EVENT", "Unbekannt")
            ereignis = (
                raw_event.capitalize()
                if isinstance(raw_event, str) and not raw_event.isdigit()
                else DWD_EVENT_TYPES.get(int(raw_event or 0), str(raw_event))
            )
            sev_level = sev_map.get(p.get("SEVERITY", "Minor"), 1)
            items.append(
                {
                    "ereignis": ereignis,
                    "schwere": DWD_SEVERITY.get(sev_level, "Unbekannt"),
                    "schwere_level": sev_level,
                    "headline": p.get("HEADLINE", ""),
                    "beschreibung": p.get("DESCRIPTION", ""),
                    "beginn": p.get("ONSET"),
                    "ende": p.get("EXPIRES"),
                }
            )
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_radar(self, session, lat, lon) -> dict:
        headers = {"If-None-Match": self._radar_etag} if self._radar_etag else {}
        async with session.get(URL_DWD_RADAR, headers=headers) as resp:
            if resp.status == 200:
                self._radar_bytes = await resp.read()
                self._radar_etag = resp.headers.get("ETag")
            elif resp.status != 304:
                return {"aktuell": 0.0, "next_length": 0}
        if not self._radar_bytes:
            return {"aktuell": 0.0, "next_length": 0}

        def _process():
            r = DWDRadar()
            r.load_from_bytes(self._radar_bytes)
            current = r.get_current_value(lat, lon)
            next_rain = r.get_next_precipitation(lat, lon)
            forecast_2h = r.get_forecast_2h(lat, lon)
            forecast_map = r.get_forecast_map(lat, lon)
            return {
                "aktuell": current,
                "next_length": next_rain.get("length", 0),
                "next_start": next_rain.get("start"),
                "next_end": next_rain.get("end"),
                "next_max_mmh": next_rain.get("max", 0.0),
                "next_sum_mm": next_rain.get("sum", 0.0),
                "forecast_2h": forecast_2h,
                "forecast": forecast_map,
            }

        return await self.hass.async_add_executor_job(_process)

    # --- Hilfsfunktionen ---

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id or not isinstance(entity_id, str):
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(str(state.state).replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _is_moving(self) -> bool:
        """Hilfsmethode – kann von Automations/Templates genutzt werden."""
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False

    def _has_valid_fix(self) -> bool:
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        min_sats = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= min_sats if sats is not None else True

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Service-Handler: geoweather.update – von Automations aufgerufen."""
        await self.async_refresh()
