"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import aiohttp
import yaml
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS,
)

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Fetches DWD location, warnings and pollen data on service call."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}

    async def async_load_pollen_mapping(self) -> None:
        """Lädt die pollen_mapping.yaml aus dem HA /config/ Verzeichnis."""
        # Nutzt den offiziellen HA-Pfad zum /config/ Ordner
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
                _LOGGER.debug("pollen_mapping.yaml erfolgreich aus /config/ geladen")
            else:
                _LOGGER.info(
                    "pollen_mapping.yaml nicht in /config/ gefunden. Nutze leeres Mapping."
                )
                self._pollen_mapping = {}
        except Exception as err:
            _LOGGER.error(
                "Fehler beim Laden der pollen_mapping.yaml unter %s: %s", path, err
            )
            self._pollen_mapping = {}

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
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
        if speed is None:
            return False
        return speed > float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))

    def _has_valid_fix(self) -> bool:
        sat_id = self._cfg(CONF_SAT_SENSOR)
        if not sat_id:
            return True
        sats = self._float_state(sat_id)
        if sats is None:
            return False
        return sats >= float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))

    async def _async_update_data(self) -> dict:
        if self._is_moving():
            speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
            self.last_skip_reason = f"Fahrzeug faehrt ({speed} km/h)"
            _LOGGER.debug(self.last_skip_reason)
            return self.data or {}

        if not self._has_valid_fix():
            sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
            self.last_skip_reason = f"GPS-Fix unzureichend ({sats} Satelliten)"
            _LOGGER.debug(self.last_skip_reason)
            return self.data or {}

        lat_id = self._cfg(CONF_LAT_SENSOR)
        lon_id = self._cfg(CONF_LON_SENSOR)
        lat = self._float_state(lat_id)
        lon = self._float_state(lon_id)

        if lat is None or lon is None:
            lat_state = self.hass.states.get(lat_id)
            lon_state = self.hass.states.get(lon_id)
            lat_val = lat_state.state if lat_state else "Entitaet nicht gefunden"
            lon_val = lon_state.state if lon_state else "Entitaet nicht gefunden"
            self.last_skip_reason = (
                f"GPS nicht verfuegbar – "
                f"lat_sensor='{lat_id}' ({lat_val}), "
                f"lon_sensor='{lon_id}' ({lon_val})"
            )
            _LOGGER.warning(
                "GeoWeather: GPS-Koordinaten nicht lesbar. "
                "lat_sensor='%s' Wert='%s' | lon_sensor='%s' Wert='%s'. "
                "Bitte pruefen ob die Sensor-Entity-IDs korrekt konfiguriert sind.",
                lat_id,
                lat_val,
                lon_id,
                lon_val,
            )
            return self.data or {}

        self.last_skip_reason = None

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen = await self._fetch_pollen(session, location.get("kreis", ""))
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Netzwerkfehler: {exc}") from exc

        return {
            "location": location,
            "warnings": warnings,
            "pollen": pollen,
            "gps": {
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": self._float_state(self._cfg(CONF_SPEED_SENSOR)),
                "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)),
                "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR)),
            },
            "last_updated": datetime.now().isoformat(),
        }

    async def _fetch_location(self, session, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNCELL.format(
            south=lat - 0.01,
            west=lon - 0.01,
            north=lat + 0.01,
            east=lon + 0.01,
        )
        async with session.get(url, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        features = data.get("features", [])
        if not features:
            return {"status": "Keine DWD Region", "gemeinde": "Unbekannt", "kreis": ""}

        p = features[0]["properties"]
        return {
            "status": "OK",
            "gemeinde": str(p.get("NAME", "Unbekannt")),
            "kreis": str(p.get("KREIS", "Unbekannt")),
            "bundesland": str(p.get("BUNDESLAND", "Unbekannt")),
            "warncellid": str(p.get("WARNCELLID", "Unbekannt")),
        }

    async def _fetch_warnings(self, session, lat: float, lon: float) -> dict:
        url = URL_DWD_WARNINGS.format(
            south=lat - 0.05,
            west=lon - 0.05,
            north=lat + 0.05,
            east=lon + 0.05,
        )
        async with session.get(url, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            # EVENT kann int oder String sein (z.B. "FROST") – sicher parsen
            raw_code = p.get("EVENT", 0)
            try:
                code = int(raw_code)
            except (ValueError, TypeError):
                code = 0
            raw_sev = p.get("SEVERITY", 0)
            try:
                severity = int(raw_sev)
            except (ValueError, TypeError):
                severity = 0
            # Ereignisname: zuerst Lookup per Code, dann direkt den String nutzen
            if code and code in DWD_EVENT_TYPES:
                ereignis = DWD_EVENT_TYPES[code]
            elif isinstance(raw_code, str) and raw_code:
                ereignis = raw_code.capitalize()
            else:
                ereignis = f"Code {raw_code}"
            items.append(
                {
                    "ereignis": ereignis,
                    "ereignis_code": raw_code,
                    "schwere": DWD_SEVERITY.get(severity, str(p.get("SEVERITY", ""))),
                    "schwere_level": severity,
                    "headline": str(p.get("HEADLINE", "")),
                    "beschreibung": str(p.get("DESCRIPTION", "")),
                    "gebiet": str(p.get("AREANAME", "")),
                    "beginn": str(p.get("ONSET", "")),
                    "ende": str(p.get("EXPIRES", "")),
                }
            )

        items.sort(key=lambda w: w["schwere_level"], reverse=True)
        return {
            "anzahl": len(items),
            "hoechste_schwere": items[0]["schwere"] if items else "Keine",
            "warnungen": items,
        }

    async def _fetch_pollen(self, session, kreis: str) -> dict:
        async with session.get(URL_DWD_POLLEN, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            pollen_json = await resp.json(content_type=None)

        search = self._pollen_mapping.get(kreis, kreis)
        match = next(
            (
                item
                for item in pollen_json.get("content", [])
                if search.lower() in str(item.get("region_name", "")).lower()
                or search.lower() in str(item.get("partregion_name", "")).lower()
            ),
            None,
        )

        if not match:
            return {
                "status": "Region nicht gefunden",
                "kreis": kreis,
                "gesuchte_region": search,
            }

        p_vals = match.get("Pollen", {})
        result = {
            "status": "OK",
            "dwd_region": str(match.get("region_name", "Unbekannt")),
            "dwd_teilregion": str(match.get("partregion_name", "")),
        }
        for pollen in POLLEN_TYPES:
            d = p_vals.get(pollen, {})
            key = pollen.lower()
            result[f"{key}_heute"] = _parse_pollen(d.get("today"))
            result[f"{key}_morgen"] = _parse_pollen(d.get("tomorrow"))
            result[f"{key}_uebermorgen"] = _parse_pollen(d.get("dayafter_to"))

        return result


def _parse_pollen(val):
    if val is None:
        return "0"

    s = str(val).strip().lower()

    # Ungültige Werte abfangen
    if s in ("-1", "", "nan", "none"):
        return "0"

    # Wir geben den Original-String zurück (z.B. "1-2"),
    # damit die Button-Card die volle Information zur Anzeige hat.
    return s
