"""DataUpdateCoordinator for GeoWeather v2.4.1 - International Safety Edition."""

from __future__ import annotations

import logging
import re
import json
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
    """Central hub for location, warnings, pollen, wind and radar data - v2.4.1."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
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
        self.pollen_cache: dict = {f"{p.lower()}_today": 0.0 for p in POLLEN_TYPES}
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
                if warn.get("schwere_level", 0) > wind_data["level"]:
                    wind_data["level"] = warn["schwere_level"]
                    wind_data["type"] = warn.get("ereignis", "Windwarnung")
                    wind_data["description"] = warn.get("headline", "")

                    desc = warn.get("beschreibung", "")
                    match = re.search(r"(\d+)\s*km/h", desc)
                    if match:
                        wind_data["speed_max"] = int(match.group(1))

        return wind_data

    async def _async_update_data(self) -> dict:
        now = datetime.now(timezone.utc)

        if not self._has_valid_fix():
            self.last_skip_reason = "Kein GPS-Fix (Sats < Min)"
            return self.data or {}

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            self.last_skip_reason = "Keine gültigen GPS-Koordinaten"
            return self.data or {}

        # --- Auslands-Check (DWD funktioniert nur in DE) ---
        # Grobe Box für Deutschland
        is_in_germany = (47.2 <= lat <= 55.1) and (5.8 <= lon <= 15.1)

        _LOGGER.debug("GeoWeather: Update für %.5f, %.5f (In DE: %s)", lat, lon, is_in_germany)

        # Standard-Werte initialisieren
        location_data = {"gemeinde": "Ausland", "kreis": "Ausland", "warncellid": None}
        warnings_data = {"anzahl": 0, "warnungen": []}
        radar_data = {"aktuell": 0.0, "next_length": 0}
        pollen_data = self.pollen_cache

        if not is_in_germany:
            self.last_skip_reason = "Außerhalb DWD-Bereich (Ausland)"
            # Wir geben die Basis-Struktur zurück, um Fehler in Sensoren zu vermeiden
            return {
                "location": location_data,
                "radar": radar_data,
                "regen": {"aktuell": 0.0, "next_length": 0},
                "warnings": warnings_data,
                "pollen": pollen_data,
                "wind": self._extract_wind_info([]),
                "gps": {"latitude": lat, "longitude": lon},
                "last_updated": now.isoformat(),
            }

        # --- DWD Datenabruf (Nur in DE) ---
        try:
            async with aiohttp.ClientSession() as session:
                location_data = await self._fetch_location(session, lat, lon)
                warnings_data = await self._fetch_warnings(session, lat, lon)
                radar_data = await self._fetch_radar(session, lat, lon)
                
                # Pollen-Check
                current_pos = (round(lat, 2), round(lon, 2))
                moved = current_pos != self.last_pollen_pos
                is_time_for_daily = now.hour >= 12 and self.last_pollen_date != now.date()
                if self._force_pollen_update or moved or is_time_for_daily:
                    pollen_data = await self._fetch_pollen(session, location_data.get("kreis", "Unbekannt"))
                    self.pollen_cache = pollen_data
                    self.last_pollen_pos = current_pos
                    self.last_pollen_date = now.date()
                    self._force_pollen_update = False
                else:
                    pollen_data = self.pollen_cache

                self.last_skip_reason = None
        except Exception as exc:
            _LOGGER.error("GeoWeather: Fehler beim DWD-Abruf: %s", exc)

        pollen_data["aktueller_kreis"] = location_data.get("kreis", "Unbekannt")
        wind_info = self._extract_wind_info(warnings_data.get("warnungen", []))

        return {
            "location": location_data,
            "radar": radar_data,
            "regen": {
                "aktuell": radar_data.get("aktuell", 0.0),
                "next_start": radar_data.get("next_start"),
                "next_end": radar_data.get("next_end"),
                "next_length": radar_data.get("next_length", 0),
                "next_max_mmh": radar_data.get("next_max_mmh", 0.0),
                "next_sum_mm": radar_data.get("next_sum_mm", 0.0),
                "forecast_2h": radar_data.get("forecast_2h", {}),
                "forecast": radar_data.get("forecast", {}),
            },
            "warnings": warnings_data,
            "pollen": pollen_data,
            "wind": wind_info,
            "gps": {"latitude": lat, "longitude": lon},
            "last_updated": now.isoformat(),
        }

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str) -> dict:
        target_id = self._pollen_mapping.get(str(kreis).strip())
        if target_id is None:
            return {f"{p.lower()}_today": 0.0 for p in POLLEN_TYPES}

        try:
            async with session.get(URL_DWD_POLLEN) as resp:
                if resp.status != 200: return {"dwd_teilregion": "Server-Fehler"}
                data = await resp.json(content_type=None)
        except Exception as e:
            _LOGGER.error("Pollen-Abruf fehlgeschlagen: %s", e)
            return {"dwd_teilregion": "Abruffehler"}

        res = {"dwd_teilregion": "Unbekannt", "dwd_region_id": target_id}
        all_today_values = []

        def _convert(val):
            mapping = {"0": 0.0, "0-1": 1.0, "1": 2.0, "1-2": 3.0, "2": 4.0, "2-3": 5.0, "3": 6.0}
            return mapping.get(str(val).strip(), 0.0)

        found_entry = next((e for e in data.get("content", []) if str(target_id) in [str(e.get("partregion_id")), str(e.get("region_id"))]), None)

        if found_entry:
            res["dwd_teilregion"] = found_entry.get("partregion_name") or found_entry.get("region_name")
            pdata = found_entry.get("Pollen") or found_entry.get("pollen") or {}
            for p_type in POLLEN_TYPES:
                ct = str(p_type).lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
                val_t, val_tm = 0.0, 0.0
                for dk, dc in pdata.items():
                    if ct == dk.lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"):
                        val_t, val_tm = _convert(dc.get("today")), _convert(dc.get("tomorrow"))
                        break
                res[f"{ct}_today"] = val_t
                res[f"{ct}_tomorrow"] = val_tm
                all_today_values.append(val_t)
            res["pollen_max_today"] = max(all_today_values) if all_today_values else 0.0
        return res

    async def _fetch_location(self, session, lat, lon) -> dict:
        import time
        url = URL_DWD_WARNCELL.format(south=lat-0.005, west=lon-0.005, north=lat+0.005, east=lon+0.005) + f"&_={int(time.time())}"
        async with session.get(url) as resp:
            if resp.status != 200: return {"gemeinde": "Fehler", "kreis": "Unbekannt"}
            data = await resp.json(content_type=None)
        if not data.get("features"): return {"gemeinde": "Unbekannt", "kreis": "Unbekannt"}
        p = data["features"][0]["properties"]
        return {"gemeinde": p.get("NAME"), "kreis": p.get("KREIS"), "warncellid": p.get("WARNCELLID")}

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        import time
        t = int(time.time())
        urls = [URL_DWD_WARNINGS_GEMEINDE.format(south=lat-0.005, west=lon-0.005, north=lat+0.005, east=lon+0.005) + f"&_={t}",
                URL_DWD_WARNINGS_KREIS.format(south=lat-0.005, west=lon-0.005, north=lat+0.005, east=lon+0.005) + f"&_={t}"]
        all_features = []
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        all_features.extend(data.get("features", []))
            except: pass
        items = []
        seen = set()
        sev_map = {"Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}
        for feat in all_features:
            p = feat.get("properties", {})
            uid = f"{p.get('EVENT')}_{p.get('HEADLINE')}"
            if uid in seen: continue
            seen.add(uid)
            raw = p.get("EVENT", 0)
            ereignis = raw.capitalize() if isinstance(raw, str) and not raw.isdigit() else DWD_EVENT_TYPES.get(int(raw or 0), str(raw))
            sl = sev_map.get(p.get("SEVERITY", "Minor"), 1)
            items.append({"ereignis": ereignis, "schwere": DWD_SEVERITY.get(sl, "Unbekannt"), "schwere_level": sl, "headline": p.get("HEADLINE", ""), "beschreibung": p.get("DESCRIPTION", ""), "beginn": p.get("ONSET"), "ende": p.get("EXPIRES")})
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_radar(self, session, lat, lon) -> dict:
        headers = {"If-None-Match": self._radar_etag} if self._radar_etag else {}
        try:
            async with session.get(URL_DWD_RADAR, headers=headers) as resp:
                if resp.status == 200:
                    self._radar_bytes = await resp.read()
                    self._radar_etag = resp.headers.get("ETag")
                elif resp.status != 304: return {"aktuell": 0.0, "next_length": 0}
        except: return {"aktuell": 0.0, "next_length": 0}
        if not self._radar_bytes: return {"aktuell": 0.0, "next_length": 0}
        def _process():
            r = DWDRadar()
            r.load_from_bytes(self._radar_bytes)
            return {"aktuell": r.get_current_value(lat, lon), "next_length": r.get_next_precipitation(lat, lon).get("length", 0), "next_start": r.get_next_precipitation(lat, lon).get("start"), "next_end": r.get_next_precipitation(lat, lon).get("end"), "next_max_mmh": r.get_next_precipitation(lat, lon).get("max", 0.0), "next_sum_mm": r.get_next_precipitation(lat, lon).get("sum", 0.0), "forecast_2h": r.get_forecast_2h(lat, lon), "forecast": r.get_forecast_map(lat, lon)}
        return await self.hass.async_add_executor_job(_process)

    def _cfg(self, key, default=None): return {**self.entry.data, **self.entry.options}.get(key, default)
    def _float_state(self, eid):
        s = self.hass.states.get(eid)
        if not s or s.state in ("unknown", "unavailable", ""): return None
        try: return float(str(s.state).replace(",", "."))
        except: return None
    def _has_valid_fix(self):
        s = self._float_state(self._cfg(CONF_SAT_SENSOR))
        return s >= float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES)) if s is not None else True
    async def async_service_update(self, call: ServiceCall | None = None) -> None: await self.async_refresh()
