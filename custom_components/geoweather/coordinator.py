import logging
import os
import yaml
from datetime import datetime
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_SPEED_SENSOR, 
    CONF_SPEED_THRESHOLD, URL_DWD_WARNCELL, URL_DWD_POLLEN, POLLEN_TYPES
)

_LOGGER = logging.getLogger(__name__)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry
        # Lade Mapping aus YAML (deine Idee!)
        self._mapping = self._load_pollen_mapping()

    def _load_pollen_mapping(self):
        path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except:
                return {}
        return {}

    async def _async_update_data(self):
        # 1. Sensoren auslesen (wie in deinem Template)
        lat_s = self.hass.states.get(self.entry.data.get(CONF_LAT_SENSOR))
        lon_s = self.hass.states.get(self.entry.data.get(CONF_LON_SENSOR))
        speed_s = self.hass.states.get(self.entry.data.get(CONF_SPEED_SENSOR))

        # 2. Validierung (Deine Template-Logik: speed < 5 und lat != 0)
        try:
            lat = float(lat_s.state.replace(',', '.')) if lat_s else 0
            lon = float(lon_s.state.replace(',', '.')) if lon_s else 0
            speed = float(speed_s.state.replace(',', '.')) if speed_s else 0
        except:
            return self.data # Behalte alte Daten bei Fehlern

        # Fahrt-Check
        threshold = float(self.entry.data.get(CONF_SPEED_THRESHOLD, 5.0))
        if speed > threshold or lat == 0:
            # Wir geben einen Status zurück, der "Fahrt" signalisiert, 
            # aber die alten Standortdaten behält (wie dein Template)
            if self.data:
                self.data["status"] = "Fahrt - Pause"
                return self.data
            return {"status": "Warte auf Stillstand"}

        try:
            async with aiohttp.ClientSession() as session:
                # 3. DWD Geoserver (Warnzelle)
                url = URL_DWD_WARNCELL.format(
                    south=lat-0.01, west=lon-0.01, north=lat+0.01, east=lon+0.01
                )
                async with session.get(url, timeout=10) as resp:
                    res = await resp.json()
                    feat = res.get("features", [{}])[0].get("properties", {})
                    
                    kreis = feat.get("KREIS", "Unbekannt")
                    gemeinde = feat.get("NAME", "Unbekannt")

                # 4. Pollen (Mapping nutzen)
                search = self._mapping.get(kreis, kreis)
                async with session.get(URL_DWD_POLLEN, timeout=10) as resp:
                    p_data = await resp.json()
                    match = next((i for i in p_data.get("content", []) 
                                 if search.lower() in str(i.get("region_name", "")).lower()), None)
                    
                    pollen_res = {}
                    if match:
                        for pt in POLLEN_TYPES:
                            val = match.get("Pollen", {}).get(pt, {}).get("today", 0)
                            pollen_res[pt.lower()] = self._parse_pollen(val)

            return {
                "location": {"gemeinde": gemeinde, "kreis": kreis},
                "pollen": pollen_results,
                "status": "OK",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            _LOGGER.error("Fehler: %s", e)
            return self.data

    def _parse_pollen(self, val):
        if val is None: return 0
        s = str(val).split('-')[-1] # Nimmt bei "0-1" die 1
        try: return int(float(s))
        except: return 0

    async def async_service_update(self, call=None):
        await self.async_refresh()
