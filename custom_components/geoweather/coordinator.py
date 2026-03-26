"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
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
from .dwdradar import DWDRadar, NotInAreaError

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Pollen-Daten: DWD aktualisiert nur 1x täglich
_POLLEN_CACHE_HOURS = 12


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}
        self.stopped_at: datetime | None = None
        # Pollen-Cache: (timestamp_utc, raw_json)
        self._pollen_cache: tuple[datetime, dict] | None = None
        # Radar HTTP-Cache
        self._radar_etag: str | None = None
        self._radar_last_modified: str | None = None
        self._radar_bytes: bytes | None = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def async_load_pollen_mapping(self) -> None:
        """Lädt /config/pollen_mapping.yaml asynchron (kein Block im Event-Loop)."""
        path = self.hass.config.path("pollen_mapping.yaml")
        try:
            def _read():
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                return ""
            content = await self.hass.async_add_executor_job(_read)
            if content:
                data = yaml.safe_load(content)
                self._pollen_mapping = data if isinstance(data, dict) else {}
                _LOGGER.debug("pollen_mapping.yaml geladen: %d Einträge", len(self._pollen_mapping))
            else:
                _LOGGER.info("pollen_mapping.yaml nicht gefunden – leeres Mapping")
        except Exception as err:
            _LOGGER.error("Fehler beim Laden von pollen_mapping.yaml: %s", err)

    # ── Service handler ───────────────────────────────────────────────────────

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Prüft Fahrstatus und Mindest-Standzeit bevor ein Refresh ausgelöst wird."""

        # Beim allerersten Aufruf (data=None) sofort holen
        if self.data is None:
            await self.async_refresh()
            return

        # Fahrstatus live vom binary_sensor lesen
        moving_entity = None
        for state in self.hass.states.async_all("binary_sensor"):
            if self.entry.entry_id in state.entity_id and "moving" in state.entity_id:
                moving_entity = state
                break

        is_moving = moving_entity.state == "on" if moving_entity else self._is_moving()

        if is_moving:
            self.stopped_at = None
            self.last_skip_reason = "Fahrzeug fährt – Update übersprungen"
            _LOGGER.debug(self.last_skip_reason)
            return

        # Timer starten
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)

        standing_min = (datetime.now(timezone.utc) - self.stopped_at).total_seconds() / 60
        limit = float(self._cfg(CONF_MIN_STATIONARY_TIME, DEFAULT_MIN_STATIONARY_TIME))

        if limit > 0 and standing_min < limit:
            self.last_skip_reason = (
                f"Standzeit zu kurz ({int(standing_min)}/{int(limit)} Min)"
            )
            _LOGGER.debug(self.last_skip_reason)
            return

        self.last_skip_reason = None
        await self.async_refresh()

    # ── Helpers ───────────────────────────────────────────────────────────────

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
        return speed > threshold if speed is not None else False

    def _has_valid_fix(self) -> bool:
        sat_id = self._cfg(CONF_SAT_SENSOR)
        if not sat_id:
            return True
        sats = self._float_state(sat_id)
        if sats is None:
            return False
        return sats >= float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))

    # ── device_info ───────────────────────────────────────────────────────────

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "GeoWeather",
            "manufacturer": "DWD / hflocki",
            "model": "GeoWeather Integration",
            "entry_type": "service",
        }

    # ── Haupt-Update ──────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict:
        """Wird durch async_refresh() aufgerufen – holt alle DWD-Daten."""

        # Guards: kein Update beim Fahren oder schlechtem GPS-Fix
        if self._is_moving():
            self.stopped_at = None
            _LOGGER.debug("_async_update_data: Fahrzeug fährt – übersprungen")
            return self.data or {}

        if not self._has_valid_fix():
            _LOGGER.debug("_async_update_data: GPS-Fix unzureichend – übersprungen")
            return self.data or {}

        lat_id = self._cfg(CONF_LAT_SENSOR)
        lon_id = self._cfg(CONF_LON_SENSOR)
        lat = self._float_state(lat_id)
        lon = self._float_state(lon_id)

        if lat is None or lon is None:
            lat_val = getattr(self.hass.states.get(lat_id), "state", "nicht gefunden")
            lon_val = getattr(self.hass.states.get(lon_id), "state", "nicht gefunden")
            self.last_skip_reason = f"GPS nicht lesbar – lat='{lat_id}'({lat_val}) lon='{lon_id}'({lon_val})"
            _LOGGER.warning("GeoWeather GPS: lat_sensor='%s'=%s | lon_sensor='%s'=%s", lat_id, lat_val, lon_id, lon_val)
            return self.data or {}

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen   = await self._fetch_pollen(session, location.get("kreis", ""))
                regen    = await self._fetch_radar(session, lat, lon)
        except Exception as exc:
            raise UpdateFailed(f"GeoWeather Update fehlgeschlagen: {exc}") from exc

        return {
            "location":     location,
            "warnings":     warnings,
            "pollen":       pollen,
            "regen":        regen,
            "gps": {
                "latitude":   lat,
                "longitude":  lon,
                "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)),
                "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR)),
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    # ── DWD: Standort / Warnzelle ─────────────────────────────────────────────

    async def _fetch_location(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNCELL.format(
            south=lat - 0.01, west=lon - 0.01,
            north=lat + 0.01, east=lon + 0.01,
        )
        async with session.get(url, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        features = data.get("features", [])
        if not features:
            return {"status": "Keine Region", "gemeinde": "Unbekannt", "kreis": ""}

        p = features[0]["properties"]
        return {
            "status":     "OK",
            "gemeinde":   str(p.get("NAME",       "Unbekannt")),
            "kreis":      str(p.get("KREIS",      "Unbekannt")),
            "bundesland": str(p.get("BUNDESLAND", "Unbekannt")),
            "warncellid": str(p.get("WARNCELLID", "Unbekannt")),
        }

    # ── DWD: Aktive Warnungen ─────────────────────────────────────────────────

    async def _fetch_warnings(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNINGS.format(
            south=lat - 0.05, west=lon - 0.05,
            north=lat + 0.05, east=lon + 0.05,
        )
        async with session.get(url, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            raw_code = p.get("EVENT", 0)
            raw_sev  = p.get("SEVERITY", 0)
            try:
                code = int(raw_code)
            except (ValueError, TypeError):
                code = 0
            try:
                sev = int(raw_sev)
            except (ValueError, TypeError):
                sev = 0

            if code and code in DWD_EVENT_TYPES:
                ereignis = DWD_EVENT_TYPES[code]
            elif isinstance(raw_code, str) and raw_code:
                ereignis = raw_code.capitalize()
            else:
                ereignis = f"Code {raw_code}"

            items.append({
                "ereignis":      ereignis,
                "ereignis_code": raw_code,
                "schwere":       DWD_SEVERITY.get(sev, str(raw_sev)),
                "schwere_level": sev,
                "headline":      str(p.get("HEADLINE",    "")),
                "beschreibung":  str(p.get("DESCRIPTION", "")),
                "beginn":        str(p.get("ONSET",       "")),
                "ende":          str(p.get("EXPIRES",     "")),
            })

        items.sort(key=lambda w: w["schwere_level"], reverse=True)
        return {
            "anzahl":           len(items),
            "hoechste_schwere": items[0]["schwere"] if items else "Keine",
            "warnungen":        items,
        }

    # ── DWD: Pollen (mit 12h-Cache) ───────────────────────────────────────────

    async def _fetch_pollen(self, session, kreis: str) -> dict:
        """Pollen-Abruf mit 12h Cache und Standort-Check."""
        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))
        
        # Prüfen, ob wir Cache-Daten nutzen können
        if self.data and "pollen" in self.data and "gps" in self.data:
            last_pollen_update = self.data.get("last_updated")
            old_gps = self.data.get("gps", {})
            
            if last_pollen_update:
                last_time = datetime.fromisoformat(last_pollen_update)
                time_delta = datetime.now() - last_time
                
                # Check: Standort identisch (bis auf 0.01 Grad) UND Zeit < 12h?
                loc_changed = (
                    abs(old_gps.get("latitude", 0) - (lat or 0)) > 0.01 or
                    abs(old_gps.get("longitude", 0) - (lon or 0)) > 0.01
                )
                
                if not loc_changed and time_delta < timedelta(hours=12):
                    _LOGGER.debug("GeoWeather: Nutze Pollen-Cache (Standort unverändert & < 12h)")
                    return self.data["pollen"]

        # Wenn kein Cache, Standort geändert oder Cache zu alt: Neu abrufen
        _LOGGER.info("GeoWeather: Lade Pollen-Daten frisch vom DWD (Standortwechsel oder Cache abgelaufen)")
        
        try:
            async with session.get(URL_DWD_POLLEN, timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                json_data = await resp.json(content_type=None)

            # Dein Word-Matching
            search_term = self._pollen_mapping.get(kreis, kreis)
            match = None

            for item in json_data.get("content", []):
                rname = str(item.get("region_name", "")).lower()
                pname = str(item.get("partregion_name", "")).lower()
                target = str(search_term).lower()

                if target in rname or target in pname:
                    match = item
                    break

            if not match:
                return {"status": "Region nicht gefunden", "gesucht": search_term}

            p_vals = match.get("Pollen", {})
            res = {
                "status": "OK",
                "dwd_region": match.get("region_name"),
                "dwd_teilregion": match.get("partregion_name"),
            }
            for pt in POLLEN_TYPES:
                d = p_vals.get(pt, {})
                res[f"{pt.lower()}_heute"] = _parse_pollen(d.get("today"))
                res[f"{pt.lower()}_morgen"] = _parse_pollen(d.get("tomorrow"))
                res[f"{pt.lower()}_uebermorgen"] = _parse_pollen(d.get("dayafter_to"))
            
            return res
            
        except Exception as e:
            _LOGGER.error("GeoWeather: Pollen Fehler: %s", e)
            return self.data.get("pollen") if self.data else {"status": "Fehler"}

    # ── DWD: Radar via DWDRadar-Klasse (mit ETag-Cache) ──────────────────────

    async def _fetch_radar(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        _empty = {"aktuell": 0.0, "forecast": {}, "next_start": None, "next_end": None,
                  "next_length": None, "next_max_mmh": None, "next_sum_mm": None}

        # Koordinaten vorab prüfen
        radar = DWDRadar()
        try:
            radar.get_location_index(lat, lon)  # wirft NotInAreaError wenn außerhalb
        except NotInAreaError as exc:
            _LOGGER.warning("Radar: %s", exc)
            return _empty

        # HTTP-Caching
        headers: dict[str, str] = {}
        if self._radar_etag:
            headers["If-None-Match"] = self._radar_etag
        if self._radar_last_modified:
            headers["If-Modified-Since"] = self._radar_last_modified

        async with session.get(URL_DWD_RADAR, timeout=_TIMEOUT, headers=headers) as resp:
            if resp.status == 304 and self._radar_bytes is not None:
                _LOGGER.debug("Radar: 304 Not Modified – Cache genutzt")
                content = self._radar_bytes
            else:
                resp.raise_for_status()
                content = await resp.read()
                self._radar_bytes         = content
                self._radar_etag          = resp.headers.get("ETag")
                self._radar_last_modified = resp.headers.get("Last-Modified")
                _LOGGER.debug("Radar: neu geladen (%d KB)", len(content) // 1024)

        # Verarbeitung im Thread-Pool (blocking numpy/tarfile)
        def _process() -> dict:
            r = DWDRadar()
            r.load_from_bytes(content)
            forecast     = r.get_forecast_map(lat, lon)
            current      = r.get_current_value(lat, lon)
            next_precip  = r.get_next_precipitation(lat, lon)
            return {
                "aktuell":      current,
                "forecast":     forecast,
                "next_start":   next_precip["start"],
                "next_end":     next_precip["end"],
                "next_length":  next_precip["length_min"],
                "next_max_mmh": next_precip["max_mmh"],
                "next_sum_mm":  next_precip["sum_mm"],
            }

        return await self.hass.async_add_executor_job(_process)


# ── Helper ────────────────────────────────────────────────────────────────────

def _parse_pollen(val) -> str:
    """DWD-Pollenwert sicher in String umwandeln. '0' als Fallback."""
    if val is None:
        return "0"
    s = str(val).strip().lower()
    return "0" if s in ("-1", "", "nan", "none") else s
