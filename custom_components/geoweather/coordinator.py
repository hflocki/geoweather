"""
DataUpdateCoordinator for GeoWeather.

Data is NOT fetched on a timer. Instead the integration registers a
HA service  ``geoweather.update``  that triggers a fresh fetch.
Call it from an Automation whenever you want (e.g. on GPS position change,
every 30 min while stationary, etc.).

The coordinator also enforces:
  - Skip when vehicle is moving  (speed > threshold)
  - Skip when GPS fix is bad    (satellites < min_satellites)
"""
from __future__ import annotations

import logging
from datetime import datetime

import aiohttp

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_ALT_SENSOR,
    CONF_SAT_SENSOR,
    CONF_SPEED_THRESHOLD,
    CONF_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_MIN_SATELLITES,
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS,
    URL_DWD_POLLEN,
    DWD_SEVERITY,
    DWD_EVENT_TYPES,
    POLLEN_TYPES,
    POLLEN_REGION_MAPPING,
    SERVICE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

# Timeout for individual HTTP requests
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Manages all DWD data for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # No update_interval – updates are service-triggered only
        )
        self._entry = entry
        self.entry_id = entry.entry_id
        self._config: dict = {**entry.data, **entry.options}

        # Expose last-updated timestamp as attribute
        self.last_updated: datetime | None = None
        self.last_skip_reason: str | None = None

    # ── Config helpers ────────────────────────────────────────────────────────

    def _refresh_config(self) -> None:
        """Merge entry data + options (options override data after reconfigure)."""
        self._config = {**self._entry.data, **self._entry.options}

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state.replace(",", "."))
        except ValueError:
            return None

    # ── Guard checks ──────────────────────────────────────────────────────────

    def _get_coordinates(self) -> tuple[float, float] | None:
        lat = self._float_state(self._config.get(CONF_LAT_SENSOR))
        lon = self._float_state(self._config.get(CONF_LON_SENSOR))
        if lat is None or lon is None:
            return None
        return lat, lon

    def _is_moving(self) -> bool:
        speed = self._float_state(self._config.get(CONF_SPEED_SENSOR))
        if speed is None:
            return False  # sensor unavailable → assume stationary
        threshold = float(self._config.get(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold

    def _has_valid_fix(self) -> bool:
        sat_id = self._config.get(CONF_SAT_SENSOR)
        if not sat_id:
            return True  # no satellite sensor configured → always assume valid
        sats = self._float_state(sat_id)
        if sats is None:
            return False
        min_sats = float(self._config.get(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= min_sats

    # ── GPS snapshot (for sensor attributes) ─────────────────────────────────

    def _gps_snapshot(self) -> dict:
        return {
            "latitude":      self._float_state(self._config.get(CONF_LAT_SENSOR)),
            "longitude":     self._float_state(self._config.get(CONF_LON_SENSOR)),
            "speed_kmh":     self._float_state(self._config.get(CONF_SPEED_SENSOR)),
            "altitude_m":    self._float_state(self._config.get(CONF_ALT_SENSOR)),
            "satellites":    self._float_state(self._config.get(CONF_SAT_SENSOR)),
        }

    # ── Service handler ───────────────────────────────────────────────────────

    async def async_service_update(self, call: ServiceCall) -> None:  # noqa: ARG002
        """Called by the  geoweather.update  service."""
        await self.async_request_refresh()

    # ── Main fetch ────────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict:
        """Fetch all DWD data. Raises UpdateFailed on error."""
        self._refresh_config()

        # ── Guard: moving? ────────────────────────────────────────────────────
        if self._is_moving():
            speed = self._float_state(self._config.get(CONF_SPEED_SENSOR))
            self.last_skip_reason = f"GeoWeather fährt ({speed} km/h) – Update übersprungen"
            _LOGGER.debug(self.last_skip_reason)
            # Return previous data unchanged so sensors don't reset
            return self.data or {}

        # ── Guard: GPS fix? ───────────────────────────────────────────────────
        if not self._has_valid_fix():
            sats = self._float_state(self._config.get(CONF_SAT_SENSOR))
            self.last_skip_reason = f"GPS-Fix unzureichend ({sats} Satelliten)"
            _LOGGER.debug(self.last_skip_reason)
            return self.data or {}

        # ── Guard: coordinates available? ─────────────────────────────────────
        coords = self._get_coordinates()
        if coords is None:
            raise UpdateFailed("GPS-Koordinaten nicht verfügbar (sensor unavailable)")

        self.last_skip_reason = None
        lat, lon = coords
        gps = self._gps_snapshot()

        async with aiohttp.ClientSession() as session:
            location   = await self._fetch_location(session, lat, lon)
            warnings   = await self._fetch_warnings(session, lat, lon)
            pollen     = await self._fetch_pollen(session, location.get("kreis", ""))

        self.last_updated = datetime.now()

        return {
            "gps":       gps,
            "location":  location,
            "warnings":  warnings,
            "pollen":    pollen,
            "last_updated": self.last_updated.isoformat(),
        }

    # ── DWD: Location (Warnzelle / Gemeinde / Kreis) ──────────────────────────

    async def _fetch_location(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNCELL.format(
            south=lat - 0.01, west=lon - 0.01,
            north=lat + 0.01, east=lon + 0.01,
        )
        try:
            async with session.get(url, timeout=_HTTP_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"DWD Warnzellen-Abfrage fehlgeschlagen: {exc}") from exc

        features = data.get("features", [])
        if not features:
            return {"status": "Keine DWD Region gefunden"}

        p = features[0]["properties"]
        return {
            "status":     "OK",
            "gemeinde":   str(p.get("NAME",       "Unbekannt")),
            "kreis":      str(p.get("KREIS",      "Unbekannt")),
            "bundesland": str(p.get("BUNDESLAND", "Unbekannt")),
            "warncellid": str(p.get("WARNCELLID", "Unbekannt")),
        }

    # ── DWD: Active weather warnings ─────────────────────────────────────────

    async def _fetch_warnings(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNINGS.format(
            south=lat - 0.05, west=lon - 0.05,
            north=lat + 0.05, east=lon + 0.05,
        )
        try:
            async with session.get(url, timeout=_HTTP_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"DWD Warnungen-Abfrage fehlgeschlagen: {exc}") from exc

        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            code     = int(p.get("EVENT",    0))
            severity = int(p.get("SEVERITY", 0))
            items.append({
                "ereignis":      DWD_EVENT_TYPES.get(code, f"Code {code}"),
                "ereignis_code": code,
                "schwere":       DWD_SEVERITY.get(severity, f"Level {severity}"),
                "schwere_level": severity,
                "headline":      str(p.get("HEADLINE",    "")),
                "beschreibung":  str(p.get("DESCRIPTION", "")),
                "gebiet":        str(p.get("AREANAME",    "")),
                "beginn":        str(p.get("ONSET",       "")),
                "ende":          str(p.get("EXPIRES",     "")),
                "warncellid":    str(p.get("WARNCELLID",  "")),
            })

        items.sort(key=lambda w: w["schwere_level"], reverse=True)
        return {
            "anzahl":         len(items),
            "hoechste_schwere": items[0]["schwere"] if items else "Keine",
            "warnungen":      items,
        }

    # ── DWD: Pollen forecast ──────────────────────────────────────────────────

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str) -> dict:
        try:
            async with session.get(URL_DWD_POLLEN, timeout=_HTTP_TIMEOUT) as resp:
                resp.raise_for_status()
                pollen_json = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"DWD Pollen-Abfrage fehlgeschlagen: {exc}") from exc

        search = POLLEN_REGION_MAPPING.get(kreis, kreis)
        match = next(
            (
                item for item in pollen_json.get("content", [])
                if search.lower() in str(item.get("region_name",    "")).lower()
                or search.lower() in str(item.get("partregion_name","")).lower()
            ),
            None,
        )

        if not match:
            return {
                "status":          "Region nicht gefunden",
                "kreis":           kreis,
                "gesuchte_region": search,
            }

        p_vals = match.get("Pollen", {})
        result: dict = {
            "status":        "OK",
            "dwd_region":    str(match.get("region_name",    "Unbekannt")),
            "dwd_teilregion":str(match.get("partregion_name","")),
        }

        for pollen in POLLEN_TYPES:
            data = p_vals.get(pollen, {})
            key  = pollen.lower()
            result[f"{key}_heute"]       = _parse_pollen(data.get("today"))
            result[f"{key}_morgen"]      = _parse_pollen(data.get("tomorrow"))
            result[f"{key}_uebermorgen"] = _parse_pollen(data.get("dayafter_to"))

        return result


# ── Helper ────────────────────────────────────────────────────────────────────

def _parse_pollen(val) -> int:
    """Wandelt DWD-Werte wie '0-1' sicher in Zahlen um. Verhindert JSON-Fehler."""
    if val is None:
        return 0
    
    # In String umwandeln und säubern
    s = str(val).strip().lower()
    
    # Ungültige Texte abfangen
    if s in ("-1", "", "nan", "keine daten", "null", "none", "unknown"):
        return 0
        
    try:
        # Falls es ein Bereich ist (z.B. 0-1), nimm die hintere Zahl
        if '-' in s:
            return int(s.split('-')[-1])
        # Falls es eine Kommazahl ist, erst zu float, dann zu int
        return int(float(s))
    except (ValueError, TypeError):
        return 0
