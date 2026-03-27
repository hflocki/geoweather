"""DataUpdateCoordinator for GeoWeather."""
from __future__ import annotations
import logging, os, aiohttp, yaml
from datetime import datetime, timedelta, timezone
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    CONF_ALT_SENSOR, CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_MIN_SATELLITES,
    CONF_MIN_STATIONARY_TIME, CONF_SAT_SENSOR, CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD, CONF_UPDATE_INTERVAL, DEFAULT_MIN_SATELLITES,
    DEFAULT_MIN_STATIONARY_TIME, DEFAULT_SPEED_THRESHOLD, DEFAULT_UPDATE_INTERVAL,
    DOMAIN, DWD_EVENT_TYPES, DWD_SEVERITY, POLLEN_TYPES, URL_DWD_POLLEN,
    URL_DWD_RADAR, URL_DWD_WARNCELL, URL_DWD_WARNINGS
)
from .dwdradar import DWDRadar

_LOGGER = logging.getLogger(__name__)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        interval_min = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        update_interval = timedelta(minutes=interval_min) if interval_min > 0 else None
        
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.entry = entry
        self.stopped_at = None
        self.last_skip_reason = None
        self._pollen_mapping = {}
        self._radar_etag = None
        self._radar_last_modified = None
        self._radar_bytes = None

    async def async_load_pollen_mapping(self):
        """Lädt das Mapping für DWD-Pollenregionen ohne das System zu blockieren."""
        path = self.hass.config.path("pollen_mapping.yaml")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml.example")
        
        def _load():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                _LOGGER.error("Fehler beim Lesen der Pollen-Datei: %s", e)
                return {}

        self._pollen_mapping = await self.hass.async_add_executor_job(_load)
        _LOGGER.debug("Pollen-Mapping geladen: %d Einträge", len(self._pollen_mapping))

    async def _async_update_data(self) -> dict:
        if self._is_moving():
            self.stopped_at = None
            return self.data or {}
        
        if not self._has_valid_fix(): return self.data or {}
        if self.stopped_at is None: self.stopped_at = datetime.now(timezone.utc)

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))
        if lat is None or lon is None: return self.data or {}

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                pollen = await self._fetch_pollen(session, location.get("kreis", ""))
                regen = await self._fetch_radar(session, lat, lon)
        except Exception as exc:
            raise UpdateFailed(f"DWD-Abruf fehlgeschlagen: {exc}")

        return {
            "location": location, "warnings": warnings, "pollen": pollen, "regen": regen,
            "gps": {"latitude": lat, "longitude": lon, "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)), "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR))},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        url = URL_DWD_WARNINGS.format(south=lat-0.05, west=lon-0.05, north=lat+0.05, east=lon+0.05)
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)
        items = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            raw_event = p.get("EVENT", "Unbekannt")
            # FIX: FROST (Text) statt Code abfangen
            ereignis = raw_event.capitalize() if isinstance(raw_event, str) and not raw_event.isdigit() else DWD_EVENT_TYPES.get(int(raw_event), f"Code {raw_event}")
            items.append({
                "ereignis": ereignis, "schwere": DWD_SEVERITY.get(int(p.get("SEVERITY", 0)), "Gering"),
                "schwere_level": int(p.get("SEVERITY", 0)), "headline": p.get("HEADLINE", ""),
                "beschreibung": p.get("DESCRIPTION", ""), "beginn": p.get("ONSET"), "ende": p.get("EXPIRES")
            })
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_radar(self, session, lat, lon) -> dict:
        headers = {"If-None-Match": self._radar_etag} if self._radar_etag else {}
        async with session.get(URL_DWD_RADAR, headers=headers) as resp:
            if resp.status == 200:
                self._radar_bytes = await resp.read()
                self._radar_etag = resp.headers.get("ETag")
            elif resp.status != 304: return {"aktuell": 0, "next_length": None}

        def _process():
            r = DWDRadar()
            r.load_from_bytes(self._radar_bytes)
            res = r.get_next_precipitation(lat, lon)
            l_min = int(res["length"].total_seconds()/60) if res.get("length") else 0
            return {"aktuell": r.get_current_value(lat, lon), "forecast": r.get_forecast_map(lat, lon), "next_length": l_min, "next_start": res.get("start"), "next_sum_mm": res.get("sum_mm")}
        return await self.hass.async_add_executor_job(_process)

    async def _fetch_pollen(self, session, kreis) -> dict:
        search_term = self._pollen_mapping.get(kreis, kreis)
        async with session.get(URL_DWD_POLLEN) as resp:
            data = await resp.json(content_type=None)
        res = {"dwd_region": "Unbekannt"}
        for entry in data.get("content", []):
            if search_term.lower() in entry.get("region_name", "").lower() or search_term.lower() in entry.get("partregion_name", "").lower():
                res["dwd_region"] = entry.get("region_name")
                pdata = entry.get("pollen", {})
                for p_type in POLLEN_TYPES:
                    res[f"{p_type}_heute"] = str(pdata.get(p_type, {}).get("today", "0"))
                    res[f"{p_type}_morgen"] = str(pdata.get(p_type, {}).get("tomorrow", "0"))
                break
        return res

    async def _fetch_location(self, session, lat, lon) -> dict:
        url = URL_DWD_WARNCELL.format(lat=lat, lon=lon)
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)
        if not data.get("features"): return {"gemeinde": "Unbekannt", "kreis": "Unbekannt"}
        p = data["features"][0]["properties"]
        return {"gemeinde": p.get("NAME"), "kreis": p.get("KREIS"), "warncellid": p.get("WARNCELLID")}

    async def async_service_update(self, call=None):
        if not self._is_moving(): await self.async_refresh()

    def _cfg(self, k): return {**self.entry.data, **self.entry.options}.get(k)
    def _float_state(self, eid):
        s = self.hass.states.get(eid)
        try: return float(s.state.replace(",",".")) if s else None
        except: return None
    def _is_moving(self):
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        return speed > float(self._cfg(CONF_SPEED_THRESHOLD, 5.0)) if speed is not None else False
    def _has_valid_fix(self):
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        return sats >= float(self._cfg(CONF_MIN_SATELLITES, 4)) if sats is not None else True
