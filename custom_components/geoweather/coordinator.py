"""DataUpdateCoordinator for GeoWeather."""
from __future__ import annotations
import logging, os, aiohttp, yaml
from datetime import datetime, timedelta, timezone
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALT_SENSOR, CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_MIN_SATELLITES,
    CONF_SAT_SENSOR, CONF_SPEED_SENSOR, CONF_SPEED_THRESHOLD, CONF_UPDATE_INTERVAL, 
    DEFAULT_MIN_SATELLITES, DEFAULT_SPEED_THRESHOLD, DEFAULT_UPDATE_INTERVAL,
    DOMAIN, DWD_EVENT_TYPES, DWD_SEVERITY, POLLEN_TYPES, URL_DWD_POLLEN,
    URL_DWD_RADAR, URL_DWD_WARNCELL, URL_DWD_WARNINGS
)
from .dwdradar import DWDRadar

_LOGGER = logging.getLogger(__name__)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        interval_min = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        update_interval = timedelta(minutes=interval_min) if interval_min > 0 else None

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=update_interval
        )
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}
        self._radar_etag: str | None = None
        self._radar_bytes: bytes | None = None

    async def async_load_pollen_mapping(self):
        """Lädt Pollen-Mapping Datei."""
        path = self.hass.config.path("pollen_mapping.yaml")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml.example")
        
        def _load():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        self._pollen_mapping = await self.hass.async_add_executor_job(_load)

    async def _async_update_data(self) -> dict:
        """Zentrale Update-Logik."""
        if self._is_moving():
            self.last_skip_reason = "Fahrt aktiv"
            return self.data or {}

        if not self._has_valid_fix():
            self.last_skip_reason = "Kein GPS-Fix"
            return self.data or {}

        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))
        
        if lat is None or lon is None:
            self.last_skip_reason = "Koordinaten fehlen (Sensoren prüfen)"
            return self.data or {}

        self.last_skip_reason = None

        try:
            async with aiohttp.ClientSession() as session:
                location = await self._fetch_location(session, lat, lon)
                warnings = await self._fetch_warnings(session, lat, lon)
                
                kreis_name = location.get("kreis")
                if kreis_name and kreis_name != "Unbekannt":
                    pollen = await self._fetch_pollen(session, kreis_name)
                else:
                    pollen = {"dwd_teilregion": "Warte auf Standort..."}
                    
                regen = await self._fetch_radar(session, lat, lon)
        except Exception as exc:
            _LOGGER.error("Fehler beim DWD-Abruf: %s", exc)
            raise UpdateFailed(f"DWD-Abruf fehlgeschlagen: {exc}")

        return {
            "location": location,
            "warnings": warnings,
            "pollen": pollen,
            "regen": regen,
            "gps": {
                "latitude": lat, "longitude": lon, 
                "altitude_m": self._float_state(self._cfg(CONF_ALT_SENSOR)), 
                "satellites": self._float_state(self._cfg(CONF_SAT_SENSOR))
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_warnings(self, session: aiohttp.ClientSession, lat: float, lon: float) -> dict:
        """Wetterwarnungen abrufen mit BBOX."""
        import time
        t = int(time.time())
        
        # Wir erstellen die Box (identisch zum Standort-Check)
        south, north = lat - 0.005, lat + 0.005
        west, east = lon - 0.005, lon + 0.005
        
        url = URL_DWD_WARNINGS.format(
            south=south, west=west, north=north, east=east
        ) + f"&_={t}"

        async with session.get(url) as resp:
            if resp.status != 200:
                return {"anzahl": 0, "warnungen": []}
            data = await resp.json(content_type=None)

        items = []
        # Mapping für Schweregrade (DWD nutzt oft Texte statt Zahlen)
        sev_map = {"Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}

        for feat in data.get("features", []):
            p = feat.get("properties", {})
            
            # Event-Name (z.B. WINDBÖEN)
            raw_event = p.get("EVENT", "Unbekannt")
            ereignis = raw_event.capitalize() if isinstance(raw_event, str) and not raw_event.isdigit() else DWD_EVENT_TYPES.get(int(raw_event or 0), str(raw_event))

            # Schweregrad ermitteln
            raw_sev = p.get("SEVERITY", 0)
            sev_level = sev_map.get(raw_sev, 0) if isinstance(raw_sev, str) else int(raw_sev or 0)

            items.append({
                "ereignis": ereignis,
                "schwere": DWD_SEVERITY.get(sev_level, "Unbekannt"),
                "schwere_level": sev_level,
                "headline": p.get("HEADLINE", ""),
                "beschreibung": p.get("DESCRIPTION", ""),
                "beginn": p.get("ONSET"),
                "ende": p.get("EXPIRES"),
            })
        
        # Sortierung: Die schlimmste Warnung nach oben
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_radar(self, session, lat, lon) -> dict:
        """Radar/Regendaten abrufen."""
        headers = {"If-None-Match": self._radar_etag} if self._radar_etag else {}
        async with session.get(URL_DWD_RADAR, headers=headers) as resp:
            if resp.status == 200:
                self._radar_bytes = await resp.read()
                self._radar_etag = resp.headers.get("ETag")
            elif resp.status != 304: 
                return {"aktuell": 0, "next_length": 0}

        if not self._radar_bytes: return {"aktuell": 0, "next_length": 0}

        def _process():
            r = DWDRadar()
            r.load_from_bytes(self._radar_bytes)
            res = r.get_next_precipitation(lat, lon)
            l_min = int(res["length"].total_seconds()/60) if res.get("length") else 0
            return {
                "aktuell": r.get_current_value(lat, lon), 
                "forecast": r.get_forecast_map(lat, lon), 
                "next_length": l_min, "next_start": res.get("start"), "next_sum_mm": res.get("sum_mm")
            }
        return await self.hass.async_add_executor_job(_process)

    async def _fetch_pollen(self, session, kreis) -> dict:
        """Pollendaten abrufen und Werte in Zahlen umwandeln."""
        search_term = self._pollen_mapping.get(kreis, kreis)
        async with session.get(URL_DWD_POLLEN) as resp:
            data = await resp.json(content_type=None)
            
        res = {"dwd_teilregion": "Unbekannt"}

        def _convert_pollen_value(val):
            """Wandelt DWD-Werte (0, 1-2, 2-3, 3) in Floats (0.0, 1.5, 2.5, 3.0) um."""
            if val is None or val == "-1": return 0.0
            val = str(val)
            if "-" in val:
                try:
                    low, high = val.split("-")
                    return float(low) + 0.5
                except ValueError: return 0.0
            try:
                return float(val)
            except ValueError: return 0.0

        for entry in data.get("content", []):
            # Wir holen uns alle Namen, die diese Region beschreiben
            r_name = entry.get("region_name", "") or ""
            pr_name = entry.get("partregion_name", "") or ""
            
            # Suche im Mapping oder direkt nach dem Kreisnamen
            if search_term.lower() in r_name.lower() or search_term.lower() in pr_name.lower():
                res["dwd_teilregion"] = pr_name or r_name
                pdata = entry.get("pollen", {})
                
                for p_type in POLLEN_TYPES:
                    p_val, p_val_morgen = 0.0, 0.0
                    # Wir gehen alle Pollen-Keys im DWD-JSON durch
                    for dwd_pollen_key, dwd_pollen_data in pdata.items():
                        # Wenn unser Typ (z.B. Birke) im DWD-Key vorkommt
                        if p_type.lower() in dwd_pollen_key.lower():
                            p_val = _convert_pollen_value(dwd_pollen_data.get("today"))
                            p_val_morgen = _convert_pollen_value(dwd_pollen_data.get("tomorrow"))
                            break
                    
                    res[f"{p_type.lower()}_heute"] = p_val
                    res[f"{p_type.lower()}_morgen"] = p_val_morgen
                break
        return res

    async def _fetch_location(self, session, lat, lon) -> dict:
        """WarnCell ermitteln über BBOX-Verfahren (stabilste Methode)."""
        import time
        t = int(time.time())
        
        # Wir erstellen eine winzige Box um deine GPS-Position (+/- 0.005 Grad)
        # Das entspricht etwa einem 500m Radius - perfekt für Gemeinden
        south, north = lat - 0.005, lat + 0.005
        west, east = lon - 0.005, lon + 0.005
        
        # Wir füllen die BBOX-Parameter in die URL
        url = URL_DWD_WARNCELL.format(
            south=south, west=west, north=north, east=east
        ) + f"&_={t}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                _LOGGER.error("DWD Standort-Server Fehler: %s", resp.status)
                return {"gemeinde": "DWD Fehler", "kreis": "Unbekannt"}
            
            try:
                data = await resp.json(content_type=None)
            except Exception:
                return {"gemeinde": "Datenfehler", "kreis": "Unbekannt"}

        if not data.get("features"):
            _LOGGER.warning("Kein Standort für Box %s/%s gefunden", lat, lon)
            return {"gemeinde": "Unbekannt", "kreis": "Unbekannt", "warncellid": None}
            
        # Wir nehmen das erste gefundene Feature
        p = data["features"][0]["properties"]
        return {
            "gemeinde": p.get("NAME"), 
            "kreis": p.get("KREIS"), 
            "warncellid": p.get("WARNCELLID")
        }
        
    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Manueller Service-Call."""
        await self.async_refresh()

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)
    
    def _float_state(self, entity_id: str | None) -> float | None:
        """Sensorwert sicher zu Float konvertieren."""
        if not entity_id or not isinstance(entity_id, str): return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""): return None
        try:
            return float(state.state.replace(",", "."))
        except (ValueError, TypeError): return None
            
    def _is_moving(self) -> bool:
        """Geschwindigkeits-Check."""
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False
        
    def _has_valid_fix(self):
        """Satelliten-Check."""
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        return sats >= float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES)) if sats is not None else True
