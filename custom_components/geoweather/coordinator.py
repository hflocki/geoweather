"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO

import aiohttp
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
    CONF_UPDATE_INTERVAL,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_MIN_STATIONARY_TIME,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    DWD_EVENT_TYPES,
    DWD_SEVERITY,
    POLLEN_TYPES,
    URL_DWD_POLLEN,
    URL_DWD_RADAR,
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS,
)
from .dwdradar import DWDRadar, NotInAreaError

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Pollen-Daten: DWD aktualisiert nur 1x täglich
_POLLEN_CACHE_HOURS = 12


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        # Intervall aus Optionen laden (0 = Deaktiviert, sonst Minuten)
        interval_min = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        update_interval = timedelta(minutes=interval_min) if interval_min > 0 else None

        super().__init__(
            hass, 
            _LOGGER, 
            name=DOMAIN, 
            update_interval=update_interval
        )
        
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}
        self.stopped_at: datetime | None = None
        
        # Radar Cache / ETag Logik (Original erhalten)
        self._radar_etag: str | None = None
        self._radar_last_modified: str | None = None
        self._radar_bytes: bytes | None = None

    async def async_load_pollen_mapping(self):
        """Lädt das Mapping für DWD-Pollenregionen (Original erhalten)."""
        path = self.hass.config.path("pollen_mapping.yaml")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml.example")
        
        try:
            def _load():
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            self._pollen_mapping = await self.hass.async_add_executor_job(_load)
            _LOGGER.debug("Pollen-Mapping geladen: %d Einträge", len(self._pollen_mapping))
        except Exception as e:
            _LOGGER.error("Fehler beim Laden des Pollen-Mappings: %s", e)
            self._pollen_mapping = {}

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Manueller Refresh-Dienst (Original erhalten)."""
        if self.data is None:
            await self.async_refresh()
            return

        if self._is_moving():
            self.last_skip_reason = "Fahrzeug bewegt sich - Update blockiert"
            _LOGGER.debug(self.last_skip_reason)
            return

        # Standzeit-Check
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)

        standing_min = (datetime.now(timezone.utc) - self.stopped_at).total_seconds() / 60
        limit = float(self._cfg(CONF_MIN_STATIONARY_TIME, DEFAULT_MIN_STATIONARY_TIME))

        if limit > 0 and standing_min < limit:
            self.last_skip_reason = f"Standzeit zu kurz ({int(standing_min)}/{int(limit)} min)"
            _LOGGER.debug(self.last_skip_reason)
            return

        self.last_skip_reason = None
        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Zentrale Methode zum Datenabruf (Original erhalten)."""
        
        # Sicherheits-Check: Während der Fahrt NIEMALS pollen
        if self._is_moving():
            self.stopped_at = None
            self.last_skip_reason = "Fahrt aktiv"
            _LOGGER.debug("_async_update_data: Fahrzeug fährt – übersprungen")
            return self.data or {}

        # GPS-Fix Check
        if not self._has_valid_fix():
            self.last_skip_reason = "Unzureichender GPS-Fix (Satelliten)"
            _LOGGER.debug("_async_update_data: %s", self.last_skip_reason)
            return self.data or {}

        # Wenn wir hier ankommen, stehen wir
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            _LOGGER.warning("GPS-Koordinaten fehlen – Abruf abgebrochen")
            return self.data or {}

        self.last_skip_reason = None

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen   = await self._fetch_pollen(session, location.get("kreis", ""))
                regen    = await self._fetch_radar(session, lat, lon)
        except Exception as exc:
            _LOGGER.error("DWD-Abruf fehlgeschlagen: %s", exc)
            raise UpdateFailed(f"DWD-Abruf fehlgeschlagen: {exc}") from exc

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
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    # ── Fetch-Methoden ────────────────────────────────────────────────────────────

    async def _fetch_location(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        """Ermittelt Warncell-ID und Ortsnamen (Original erhalten)."""
        url = URL_DWD_WARNCELL.format(lat=lat, lon=lon)
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)
        
        if not data.get("features"):
            return {"gemeinde": "Unbekannt", "kreis": "Unbekannt", "warncellid": None}
            
        p = data["features"][0]["properties"]
        return {
            "gemeinde": p.get("NAME"),
            "kreis": p.get("KREIS"),
            "bundesland": p.get("BUNDESLAND"),
            "warncellid": p.get("WARNCELLID")
        }

    async def _fetch_warnings(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        """Wetterwarnungen vom DWD (Inklusive FROST-Fix)."""
        url = URL_DWD_WARNINGS.format(
            south=lat-0.05, west=lon-0.05, north=lat+0.05, east=lon+0.05
        )
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)

        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            raw_event = p.get("EVENT", "Unbekannt")
            raw_sev = p.get("SEVERITY", 0)

            # NEU: Fix für "FROST" und andere Text-Events
            if isinstance(raw_event, str) and not raw_event.isdigit():
                ereignis = raw_event.capitalize()
            else:
                try:
                    code = int(raw_event)
                    ereignis = DWD_EVENT_TYPES.get(code, f"Code {code}")
                except (ValueError, TypeError):
                    ereignis = str(raw_event)

            try:
                sev_level = int(raw_sev)
            except (ValueError, TypeError):
                sev_level = 0

            items.append({
                "ereignis": ereignis,
                "schwere": DWD_SEVERITY.get(sev_level, str(raw_sev)),
                "schwere_level": sev_level,
                "headline": p.get("HEADLINE", ""),
                "beschreibung": p.get("DESCRIPTION", ""),
                "beginn": p.get("ONSET"),
                "ende": p.get("EXPIRES"),
            })
        
        # Nach Schweregrad sortieren
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str) -> dict:
        """Pollenflug-Daten (Original erhalten)."""
        search_term = self._pollen_mapping.get(kreis, kreis)
        
        async with session.get(URL_DWD_POLLEN) as resp:
            data = await resp.json(content_type=None)
        
        res = {"dwd_region": "Nicht gefunden"}
        for entry in data.get("content", []):
            rname = entry.get("region_name", "")
            pname = entry.get("partregion_name", "")
            
            if search_term.lower() in rname.lower() or search_term.lower() in pname.lower():
                res["dwd_region"] = rname
                res["dwd_teilregion"] = pname
                res["region_id"] = entry.get("partregion_id")
                
                pdata = entry.get("pollen", {})
                for p_type in POLLEN_TYPES:
                    val = pdata.get(p_type, {})
                    res[f"{p_type}_heute"] = _parse_pollen(val.get("today"))
                    res[f"{p_type}_morgen"] = _parse_pollen(val.get("tomorrow"))
                    res[f"{p_type}_uebermorgen"] = _parse_pollen(val.get("dayafter_to"))
                break
        return res

    async def _fetch_radar(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        """Niederschlagsradar mit ETag-Cache (Original erhalten + Minuten-Fix)."""
        _empty = {"aktuell": 0.0, "next_length": None}
        
        try:
            headers = {}
            if self._radar_etag:
                headers["If-None-Match"] = self._radar_etag
            if self._radar_last_modified:
                headers["If-Modified-Since"] = self._radar_last_modified

            async with session.get(URL_DWD_RADAR, headers=headers) as resp:
                if resp.status == 304:
                    content = self._radar_bytes
                    _LOGGER.debug("Radar: Keine Änderung (304 Cache)")
                elif resp.status == 200:
                    content = await resp.read()
                    self._radar_bytes = content
                    self._radar_etag = resp.headers.get("ETag")
                    self._radar_last_modified = resp.headers.get("Last-Modified")
                    _LOGGER.debug("Radar: neu geladen (%d KB)", len(content) // 1024)
                else:
                    return _empty

            def _process() -> dict:
                r = DWDRadar()
                r.load_from_bytes(content)
                forecast     = r.get_forecast_map(lat, lon)
                current      = r.get_current_value(lat, lon)
                next_precip  = r.get_next_precipitation(lat, lon)
                
                # NEU: Fix für 'None Minuten' im Radar
                length_min = None
                if next_precip.get("length_min") is not None:
                    length_min = int(next_precip["length_min"])
                elif next_precip.get("length"):
                    length_min = int(next_precip["length"].total_seconds() / 60)

                return {
                    "aktuell":      current,
                    "forecast":      forecast,
                    "next_start":    next_precip.get("start"),
                    "next_end":      next_precip.get("end"),
                    "next_length":   length_min, 
                    "next_max_mmh":  next_precip.get("max"),
                    "next_sum_mm":   next_precip.get("sum"),
                }

            return await self.hass.async_add_executor_job(_process)
        except Exception as e:
            _LOGGER.error("Radar-Fehler: %s", e)
            return _empty

    # ── Hilfsmethoden (Alle Original erhalten) ────────────────────────────────────

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id: return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""): return None
        try:
            return float(state.state.replace(",", "."))
        except (ValueError, TypeError): return None

    def _is_moving(self) -> bool:
        """Prüft die Geschwindigkeit direkt am Tacho."""
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False

    def _has_valid_fix(self) -> bool:
        """GPS-Fix Prüfung."""
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        limit = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= limit if sats is not None else True

def _parse_pollen(val) -> str:
    """DWD-Pollenwert sicher in String umwandeln (Original erhalten)."""
    if val is None:
        return "0"
    s = str(val).strip().lower()
    return "0" if s in ("-1", "null", "none", "") else s
