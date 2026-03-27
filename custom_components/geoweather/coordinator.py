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
_POLLEN_CACHE_HOURS = 12

class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        # Intervall aus Optionen laden (0 = Deaktiviert)
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
        
        # Radar Cache
        self._radar_etag: str | None = None
        self._radar_last_modified: str | None = None
        self._radar_bytes: bytes | None = None

    async def async_load_pollen_mapping(self):
        """Lädt das Mapping für DWD-Pollenregionen."""
        path = self.hass.config.path("pollen_mapping.yaml")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml.example")
        
        try:
            def _load():
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            self._pollen_mapping = await self.hass.async_add_executor_job(_load)
        except Exception as e:
            _LOGGER.error("Fehler beim Laden des Pollen-Mappings: %s", e)
            self._pollen_mapping = {}

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Manueller Refresh-Dienst."""
        if self.data is None:
            await self.async_refresh()
            return

        if self._is_moving():
            self.last_skip_reason = "Fahrt aktiv - Update blockiert"
            return

        # Standzeit-Check
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)

        standing_min = (datetime.now(timezone.utc) - self.stopped_at).total_seconds() / 60
        limit = float(self._cfg(CONF_MIN_STATIONARY_TIME, DEFAULT_MIN_STATIONARY_TIME))

        if limit > 0 and standing_min < limit:
            self.last_skip_reason = f"Standzeit zu kurz ({int(standing_min)}/{int(limit)} min)"
            return

        self.last_skip_reason = None
        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Zentrale Methode zum Datenabruf."""
        if self._is_moving():
            self.stopped_at = None
            _LOGGER.debug("Update übersprungen: Fahrzeug fährt")
            return self.data or {}

        if not self._has_valid_fix():
            self.last_skip_reason = "Kein ausreichender GPS-Fix"
            return self.data or {}

        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            return self.data or {}

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen   = await self._fetch_pollen(session, location.get("kreis", ""))
                regen    = await self._fetch_radar(session, lat, lon)
        except Exception as exc:
            raise UpdateFailed(f"GeoWeather Update fehlgeschlagen: {exc}") from exc

        return {
            "location": location,
            "warnings": warnings,
            "pollen": pollen,
            "regen": regen,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    # ── Fetch-Methoden ────────────────────────────────────────────────────────────

    async def _fetch_location(self, session, lat, lon) -> dict:
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

    async def _fetch_warnings(self, session, lat, lon) -> dict:
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

            # FIX: „FROST“ Fehler abfangen (Prüfen ob String oder Zahl)
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
        
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_pollen(self, session, kreis) -> dict:
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

    async def _fetch_radar(self, session, lat, lon) -> dict:
        _empty = {"aktuell": 0.0, "next_length": None}
        try:
            headers = {}
            if self._radar_etag: headers["If-None-Match"] = self._radar_etag
            if self._radar_last_modified: headers["If-Modified-Since"] = self._radar_last_modified

            async with session.get(URL_DWD_RADAR, headers=headers) as resp:
                if resp.status == 304:
                    content = self._radar_bytes
                elif resp.status == 200:
                    content = await resp.read()
                    self._radar_bytes = content
                    self._radar_etag = resp.headers.get("ETag")
                    self._radar_last_modified = resp.headers.get("Last-Modified")
                else:
                    return _empty

            def _process() -> dict:
                r = DWDRadar()
                r.load_from_bytes(content)
                res = r.get_next_precipitation(lat, lon)
                
                # FIX: Timedelta sicher in Ganzzahl (Minuten) wandeln
                l_min = None
                if res.get("length_min") is not None:
                    l_min = int(res["length_min"])
                elif res.get("length"):
                    l_min = int(res["length"].total_seconds() / 60)

                return {
                    "aktuell": r.get_current_value(lat, lon),
                    "forecast": r.get_forecast_map(lat, lon),
                    "next_start": res.get("start"),
                    "next_end": res.get("end"),
                    "next_length": l_min, 
                    "next_max_mmh": res.get("max_mmh"),
                    "next_sum_mm": res.get("sum_mm"),
                }

            return await self.hass.async_add_executor_job(_process)
        except Exception as e:
            _LOGGER.error("Radar-Fehler: %s", e)
            return _empty

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────────

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
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        limit = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= limit if sats is not None else True

def _parse_pollen(val) -> str:
    if val is None: return "0"
    s = str(val).strip().lower()
    return "0" if s in ("-1", "null", "none", "") else s
