"""DataUpdateCoordinator for GeoWeather v2.3.2"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALT_SENSOR,
    CONF_ARRIVAL_DELAY,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ARRIVAL_DELAY,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL,
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
    """Central hub for location, warnings, pollen, wind and radar data - v2.3.1."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        interval_min = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        update_interval = timedelta(minutes=interval_min) if interval_min > 0 else None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.entry = entry

        # --- State Trackers ---
        self.last_skip_reason: str | None = None
        self._radar_etag: str | None = None
        self._radar_bytes: bytes | None = None
        self._pollen_mapping = POLLEN_REGION_MAPPING

        # --- v2.3.0 Pollen Trackers ---
        self.last_pollen_date: date | None = None
        self.last_pollen_pos: tuple[float, float] = (0.0, 0.0)
        self.pollen_cache: dict = {}
        self._last_move_time: datetime = datetime.now(timezone.utc)
        self._force_pollen_update: bool = False

        # --- v2.3.2 Arrived Sensor ---
        # True  = gerade angekommen, Standzeit läuft noch (wartet auf Delay)
        # False = Standzeit abgelaufen, Update darf stattfinden (oder fährt)
        self.arrived_waiting: bool = False

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

                    # Suche nach km/h Angaben im Beschreibungstext
                    desc = warn.get("beschreibung", "")
                    match = re.search(r"(\d+)\s*km/h", desc)
                    if match:
                        wind_data["speed_max"] = int(match.group(1))

        return wind_data

    async def _async_update_data(self) -> dict:
        """Main update cycle - v2.3.1 Intelligence."""
        now = datetime.now(timezone.utc)

        if not self._has_valid_fix():
            self.last_skip_reason = "Kein GPS-Fix (Sats < Min)"
            return self.data or {}

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            return self.data or {}

        is_moving = self._is_moving()
        arrival_delay = self._cfg(CONF_ARRIVAL_DELAY, DEFAULT_ARRIVAL_DELAY)

        current_data = self.data if self.data is not None else {}
        weather_data = current_data.get("location", {})
        radar_data = current_data.get("radar", {})
        warnings_data = current_data.get("warnings", {})

        if is_moving:
            # Fährt → merke Zeitpunkt, kein Update
            weather_data = (self.data or {}).get("location", {})
            self._last_move_time = now
            self.arrived_waiting = False
        else:
            # Steht → prüfe ob Standzeit-Delay abgelaufen
            stand_seconds = (now - self._last_move_time).total_seconds()
            delay_seconds = float(arrival_delay) * 60.0

            if delay_seconds == 0 or stand_seconds >= delay_seconds:
                # Delay erfüllt (oder 0) → Update durchführen
                self.arrived_waiting = False
                try:
                    async with aiohttp.ClientSession() as session:
                        location = await self._fetch_location(session, lat, lon)
                        warnings_data = await self._fetch_warnings(session, lat, lon)
                        radar_data = await self._fetch_radar(session, lat, lon)
                        weather_data = location
                        self.last_skip_reason = None
                except Exception as exc:
                    _LOGGER.error("Fehler beim Wetter-Abruf: %s", exc)
            else:
                # Noch innerhalb der Standzeit → warten
                remaining = int((delay_seconds - stand_seconds) / 60) + 1
                self.last_skip_reason = f"Standzeit-Delay: noch {remaining} min"
                self.arrived_waiting = True
                weather_data = (self.data or {}).get("location", {})
                radar_data = current_data.get("radar", {})
                warnings_data = current_data.get("warnings", {})

        # --- TEIL B: POLLEN ---
        current_pos = (round(lat, 2), round(lon, 2))
        stand_time_min = (now - self._last_move_time).total_seconds() / 60
        delay_min = float(arrival_delay)

        moved = current_pos != self.last_pollen_pos
        is_time_for_daily = now.hour >= 12 and self.last_pollen_date != now.date()
        is_forced = self._force_pollen_update

        pollen_should_update = not is_moving and (
            is_forced or ((moved or is_time_for_daily) and stand_time_min >= delay_min)
        )

        # WICHTIG: Wir holen den Kreisnamen IMMER, damit die Attribute aktuell bleiben
        try:
            async with aiohttp.ClientSession() as session:
                loc_for_pollen = await self._fetch_location(session, lat, lon)
                kreis_name = loc_for_pollen.get("kreis", "Unbekannt")
        except:
            kreis_name = "Unbekannt"

        if pollen_should_update:
            try:
                async with aiohttp.ClientSession() as session:
                    pollen_data = await self._fetch_pollen(session, kreis_name)
                    # Hier speichern wir die neuen Daten
                    self.pollen_cache = pollen_data
                    self.last_pollen_pos = current_pos
                    self.last_pollen_date = now.date()
                    self._force_pollen_update = False
            except Exception as exc:
                _LOGGER.error("Pollen-Abruf fehlgeschlagen: %s", exc)
                pollen_data = self.pollen_cache
        else:
            pollen_data = self.pollen_cache

        # JETZT: Den Kreis GARANTIERT in die Daten schreiben, egal ob Cache oder Neu
        pollen_data["aktueller_kreis"] = kreis_name

        # WIND INFO EXTRAHIEREN
        wind_info = self._extract_wind_info(warnings_data.get("warnungen", []))

        # Niederschlag-Dict aus Radar-Daten aufbauen (einheitliche Schnittstelle fuer sensor.py)
        niederschlag_data = {
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
            "niederschlag": niederschlag_data,
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
                "[Pollen Mapping Assistant] Kein ID-Mapping für Ort '%s' gefunden! "
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
            # BUG-FIX: lat/lon korrekt uebergeben (waren vorher x/y vertauscht)
            current = r.get_current_value(lat, lon)
            next_niederschlag = r.get_next_precipitation(lat, lon)
            forecast_2h = r.get_forecast_2h(lat, lon)
            forecast_map = r.get_forecast_map(lat, lon)
            return {
                # Aktuell
                "aktuell": current,
                # Naechster Niederschlagsabschnitt
                "next_length": next_niederschlag.get("length", 0),
                "next_start": next_niederschlag.get("start"),
                "next_end": next_niederschlag.get("end"),
                "next_max_mmh": next_niederschlag.get("max", 0.0),
                "next_sum_mm": next_niederschlag.get("sum", 0.0),
                # 2h-Vorhersage komplett
                "forecast_2h": forecast_2h,
                # Volle Zeitreihe fuer Attribute
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
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False

    def _has_valid_fix(self) -> bool:
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        min_sats = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= min_sats if sats is not None else True

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        await self.async_refresh()
