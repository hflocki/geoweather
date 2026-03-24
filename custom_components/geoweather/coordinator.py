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
)

_LOGGER = logging.getLogger(__name__)
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Fetches DWD location, warnings and pollen data on service call."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict | None = None

    async def _get_pollen_mapping(self) -> dict:
        """Load pollen_mapping.yaml asynchronously (once)."""
        if self._pollen_mapping is not None:
            return self._pollen_mapping

        path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml")

        def _load():
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}

        try:
            self._pollen_mapping = await self.hass.async_add_executor_job(_load)
        except Exception as err:
            _LOGGER.error("Fehler beim Laden der pollen_mapping.yaml: %s", err)
            self._pollen_mapping = {}

        return self._pollen_mapping

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id:
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

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        if self._is_moving():
            speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
            self.last_skip_reason = f"Fahrzeug fährt ({speed} km/h)"
            _LOGGER.debug(self.last_skip_reason)
            return self.data or {}

        if not self._has_valid_fix():
            sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
            self.last_skip_reason = f"GPS-Fix unzureichend ({sats} Satelliten)"
            _LOGGER.debug(self.last_skip_reason)
            return self.data or {}

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))

        if lat is None or lon is None:
            raise UpdateFailed("GPS-Koordinaten nicht verfügbar")

        self.last_skip_reason = None
        mapping = await self._get_pollen_mapping()

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen = await self._fetch_pollen(session, location.get("kreis", ""), mapping)
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unerwarteter Fehler: {err}") from err

        return {
            "gps": {
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": self._float_state(self._cfg(CONF_SPEED_SENSOR)),
                "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)),
                "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR)),
            },
            "location": location,
            "warnings": warnings,
            "pollen": pollen,
            "last_updated": datetime.now().isoformat(),
        }

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
            raise UpdateFailed(f"DWD Warnzelle fehlgeschlagen: {exc}") from exc

        features = data.get("features", [])
        if not features:
            return {"status": "Keine DWD Region", "gemeinde": "Unbekannt", "kreis": "Unbekannt"}

        p = features[0].get("properties", {})
        return {
            "status": "OK",
            "gemeinde": str(p.get("NAME", "Unbekannt")),
            "kreis": str(p.get("KREIS", "Unbekannt")),
            "bundesland": str(p.get("BUNDESLAND", "Unbekannt")),
            "warncellid": str(p.get("WARNCELLID", "Unbekannt")),
        }

    async def _fetch_warnings(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        """Fetch ACTIVE DWD weather warnings for the current position."""
        url = URL_DWD_WARNINGS.format(
            south=lat - 0.05, west=lon - 0.05,
            north=lat + 0.05, east=lon + 0.05,
        )
        try:
            async with session.get(url, timeout=_HTTP_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"DWD Warnungen fehlgeschlagen: {exc}") from exc

        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            code = int(p.get("EVENT", 0))
            severity = int(p.get("SEVERITY", 0))
            items.append({
                "ereignis": DWD_EVENT_TYPES.get(code, f"Code {code}"),
                "ereignis_code": code,
                "schwere": DWD_SEVERITY.get(severity, f"Level {severity}"),
                "schwere_level": severity,
                "headline": str(p.get("HEADLINE", "")),
                "beschreibung": str(p.get("DESCRIPTION", "")),
                "gebiet": str(p.get("AREANAME", "")),
                "beginn": str(p.get("ONSET", "")),
                "ende": str(p.get("EXPIRES", "")),
            })

        items.sort(key=lambda w: w["schwere_level"], reverse=True)

        return {
            "anzahl": len(items),
            "hoechste_schwere": items[0]["schwere"] if items else "Keine",
            "warnungen": items,
        }

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str, mapping: dict) -> dict:
        try:
            async with session.get(URL_DWD_POLLEN, timeout=_HTTP_TIMEOUT) as resp:
                resp.raise_for_status()
                pollen_json = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"DWD Pollen fehlgeschlagen: {exc}") from exc

        search = mapping.get(kreis, kreis)
        match = next(
            (
                item for item in pollen_json.get("content", [])
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
        result: dict = {
            "status": "OK",
            "dwd_region": str(match.get("region_name", "Unbekannt")),
            "dwd_teilregion": str(match.get("partregion_name", "")),
        }

        for pollen in POLLEN_TYPES:
            data = p_vals.get(pollen, {})
            key = pollen.lower()
            result[f"{key}_heute"] = _parse_pollen(data.get("today"))
            result[f"{key}_morgen"] = _parse_pollen(data.get("tomorrow"))
            result[f"{key}_uebermorgen"] = _parse_pollen(data.get("dayafter_to"))

        return result


def _parse_pollen(val) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if s in ("-1", "", "nan"):
        return None
    try:
        return int(s.split("-")[-1])
    except (ValueError, TypeError):
        return None
