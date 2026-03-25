"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
import math
import os
import tarfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import aiohttp
import numpy as np
import yaml
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALT_SENSOR,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_MIN_SATELLITES,
    CONF_MIN_STATIONARY_TIME,
    CONF_SAT_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_MIN_STATIONARY_TIME,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
    DWD_EVENT_TYPES,
    DWD_SEVERITY,
    POLLEN_TYPES,
    URL_DWD_POLLEN,
    URL_DWD_RADAR,
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS,
)

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}
        self.stopped_at: datetime | None = None

    async def async_load_pollen_mapping(self) -> None:
        """Lädt Mapping für Pollen-Regionen."""
        path = self.hass.config.path("pollen_mapping.yaml")
        try:
            def _read_file():
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                return ""
            content = await self.hass.async_add_executor_job(_read_file)
            if content:
                data = yaml.safe_load(content)
                self._pollen_mapping = data if isinstance(data, dict) else {}
                _LOGGER.info("GeoWeather: pollen_mapping.yaml erfolgreich geladen")
        except Exception as err:
            _LOGGER.error("GeoWeather: Fehler beim Laden von pollen_mapping.yaml: %s", err)

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Wird vom Service geoweather.update aufgerufen."""
        _LOGGER.debug("GeoWeather: Manueller Update-Aufruf empfangen")
        
        # Check Fahrt
        if self._is_moving():
            self.stopped_at = None
            self.last_skip_reason = "Fahrzeug fährt (Geschwindigkeit > Schwellenwert)"
            _LOGGER.info("GeoWeather: Update übersprungen: %s", self.last_skip_reason)
            return

        # Zeitstempel für Stillstand setzen
        if self.stopped_at is None:
            self.stopped_at = datetime.now()
            _LOGGER.debug("GeoWeather: Fahrzeug steht seit jetzt")

        # Standzeit prüfen
        standing_min = (datetime.now() - self.stopped_at).total_seconds() / 60
        limit = float(self._cfg(CONF_MIN_STATIONARY_TIME, DEFAULT_MIN_STATIONARY_TIME))

        if standing_min < limit:
            self.last_skip_reason = f"Standzeit zu kurz ({int(standing_min)}/{int(limit)} Min)"
            _LOGGER.info("GeoWeather: Update übersprungen: %s", self.last_skip_reason)
            return

        # GPS Fix prüfen
        if not self._has_valid_fix():
            self.last_skip_reason = "GPS Fix unzureichend (zu wenige Satelliten)"
            _LOGGER.info("GeoWeather: Update übersprungen: %s", self.last_skip_reason)
            return

        _LOGGER.info("GeoWeather: Alle Bedingungen erfüllt, starte Datenabruf...")
        await self.async_refresh()

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state.replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _is_moving(self) -> bool:
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        if speed is None:
            return False
        return speed > threshold

    def _has_valid_fix(self) -> bool:
        sat_id = self._cfg(CONF_SAT_SENSOR)
        if not sat_id:
            return True
        sats = self._float_state(sat_id)
        limit = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        if sats is None:
            return False
        return sats >= limit

    def _get_radar_coords(self, lat, lon):
        """Umrechnung GPS -> DWD Radar Gitter (DE1200)."""
        phi_0, lambda_0 = 60.0 * math.pi / 180.0, 10.0 * math.pi / 180.0
        r_earth = 6370.04
        phi, lamb = lat * math.pi / 180.0, lon * math.pi / 180.0
        m = (1.0 + math.sin(phi_0)) / (1.0 + math.sin(phi))
        x = m * r_earth * math.cos(phi) * math.sin(lamb - lambda_0)
        y = m * r_earth * math.cos(phi) * math.cos(lamb - lambda_0)
        x_grid = int(round(x + 542.362))
        y_grid = int(round(y + 3590.442))
        
        if not (0 <= x_grid < 1100 and 0 <= y_grid < 1200):
            return None, None
        return x_grid, 1200 - y_grid

    async def _async_update_data(self) -> dict:
        """Zentraler Datenabruf."""
        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))
        
        if lat is None or lon is None:
            _LOGGER.error("GeoWeather: Breitengrad oder Längengrad Sensor liefert keine Daten")
            return self.data or {}

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen = await self._fetch_pollen(session, location.get("kreis", ""))
                regen = await self._fetch_radar(session, lat, lon)
                
                self.last_skip_reason = None # Reset nach Erfolg
                
                return {
                    "location": location,
                    "warnings": warnings,
                    "pollen": pollen,
                    "regen": regen,
                    "gps": {
                        "latitude": lat,
                        "longitude": lon,
                        "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)),
                        "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR)),
                    },
                    "last_updated": datetime.now().isoformat(),
                }
        except Exception as exc:
            _LOGGER.error("GeoWeather: Fehler beim Datenabruf: %s", exc)
            raise UpdateFailed(f"GeoWeather Update fehlgeschlagen: {exc}")

    async def _fetch_radar(self, session, lat, lon) -> dict:
        """Radar-Archiv auswerten."""
        x, y = self._get_radar_coords(lat, lon)
        if x is None:
            return {"aktuell": 0, "forecast": {}}

        try:
            async with session.get(URL_DWD_RADAR, timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                content = await resp.read()

            def _process_radar():
                data_map = {}
                with tarfile.open(fileobj=BytesIO(content)) as tar:
                    for member in sorted(tar.getmembers(), key=lambda m: m.name):
                        f = tar.extractfile(member)
                        # DWD RV Header-Skip Logik
                        raw_content = f.read()
                        if b"\x03" not in raw_content: continue
                        raw = raw_content.split(b"\x03", 1)[1]
                        
                        grid = np.frombuffer(raw, dtype="uint16").reshape(1200, 1100)
                        val = float(grid[y, x]) * 0.1
                        
                        time_str = member.name[-14:-4]
                        base = datetime.strptime(time_str, "%y%m%d%H%M").replace(tzinfo=timezone.utc)
                        forecast_time = base + timedelta(minutes=int(member.name[-3:]))
                        data_map[forecast_time.isoformat()] = round(val, 2)
                return data_map

            forecast = await self.hass.async_add_executor_job(_process_radar)
            vals = list(forecast.values())
            next_start = next((t for t, v in forecast.items() if v > 0), None)
            
            return {
                "aktuell": vals[0] if vals else 0,
                "forecast": forecast,
                "next_start": next_start,
                "next_length": sum(1 for v in vals if v > 0) * 5
            }
        except Exception as err:
            _LOGGER.warning("GeoWeather: Radar-Daten konnten nicht verarbeitet werden: %s", err)
            return {"aktuell": 0, "forecast": {}}

    async def _fetch_location(self, session, lat, lon) -> dict:
        url = URL_DWD_WARNCELL.format(south=lat-0.01, west=lon-0.01, north=lat+0.01, east=lon+0.01)
        async with session.get(url, timeout=_TIMEOUT) as resp:
            data = await resp.json(content_type=None)
        feat = data.get("features", [])
        if not feat:
            return {"status": "Keine Region", "gemeinde": "Unbekannt", "kreis": ""}
        p = feat[0]["properties"]
        return {
            "status": "OK",
            "gemeinde": p.get("NAME"),
            "kreis": p.get("KREIS"),
            "bundesland": p.get("BUNDESLAND"),
            "warncellid": p.get("WARNCELLID")
        }

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        url = URL_DWD_WARNINGS.format(south=lat-0.05, west=lon-0.05, north=lat+0.05, east=lon+0.05)
        async with session.get(url, timeout=_TIMEOUT) as resp:
            data = await resp.json(content_type=None)
        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            code, sev = int(p.get("EVENT", 0)), int(p.get("SEVERITY", 0))
            items.append({
                "ereignis": DWD_EVENT_TYPES.get(code, f"Code {code}"),
                "schwere": DWD_SEVERITY.get(sev, "Unbekannt"),
                "schwere_level": sev,
                "headline": p.get("HEADLINE", ""),
                "beschreibung": p.get("DESCRIPTION", ""),
                "beginn": p.get("ONSET", ""),
                "ende": p.get("EXPIRES", ""),
            })
        items.sort(key=lambda w: w["schwere_level"], reverse=True)
        return {"anzahl": len(items), "hoechste_schwere": items[0]["schwere"] if items else "Keine", "warnungen": items}

    async def _fetch_pollen(self, session, kreis: str) -> dict:
        async with session.get(URL_DWD_POLLEN, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            json_data = await resp.json(content_type=None)

        search_val = self._pollen_mapping.get(kreis, kreis)
        match = None
        for item in json_data.get("content", []):
            rid = item.get("region_id")
            rname = str(item.get("region_name", "")).lower()
            pname = str(item.get("partregion_name", "")).lower()

            if str(rid) == str(search_val):
                match = item
                break
            if str(search_val).lower() in rname or str(search_val).lower() in pname:
                match = item
                break

        if not match:
            return {"status": "Region nicht gefunden"}
        p_vals = match.get("Pollen", {})
        res = {
            "status": "OK",
            "dwd_region": match.get("region_name"),
            "dwd_teilregion": match.get("partregion_name"),
            "region_id": match.get("region_id"),
        }
        for pt in POLLEN_TYPES:
            d = p_vals.get(pt, {})
            res[f"{pt.lower()}_heute"] = _parse_pollen(d.get("today"))
            res[f"{pt.lower()}_morgen"] = _parse_pollen(d.get("tomorrow"))
            res[f"{pt.lower()}_uebermorgen"] = _parse_pollen(d.get("dayafter_to"))
        return res

def _parse_pollen(val):
    if val is None: return "0"
    s = str(val).strip().lower()
    return "0" if s in ("-1", "", "nan", "none") else s
