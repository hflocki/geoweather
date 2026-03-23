"""DataUpdateCoordinator for GeoWeather."""
from __future__ import annotations

import logging
import os
import yaml
from datetime import datetime
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_LAT_SENSOR, CONF_LON_SENSOR, CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD, URL_DWD_WARNCELL, URL_DWD_POLLEN, POLLEN_TYPES,
)

_LOGGER = logging.getLogger(__name__)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self._mapping = self._load_pollen_mapping()

    def _load_pollen_mapping(self) -> dict:
        path = os.path.join(os.path.dirname(__file__), "pollen_mapping.yaml")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return data if isinstance(data, dict) else {}
        except Exception as err:
            _LOGGER.error("Fehler beim Laden der pollen_mapping.yaml: %s", err)
        return {}

    async def async_service_update(self, call=None) -> None:
        await self.async_refresh()

    async def _async_update_data(self):
        lat_id = self.entry.data.get(CONF_LAT_SENSOR)
        lon_id = self.entry.data.get(CONF_LON_SENSOR)
        speed_id = self.entry.data.get(CONF_SPEED_SENSOR)
        
        lat_s = self.hass.states.get(lat_id)
        lon_s = self.hass.states.get(lon_id)
        speed_s = self.hass.states.get(speed_id)

        try:
            lat = float(str(lat_s.state).replace(',', '.')) if lat_s else 0
            lon = float(str(lon_s.state).replace(',', '.')) if lon_s else 0
            speed = float(str(speed_s.state).replace(',', '.')) if speed_s else 0
        except:
            return self.data

        threshold = float(self.entry.data.get(CONF_SPEED_THRESHOLD, 5.0))
        if speed > threshold or lat == 0:
            return self.data

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Standort
                warn_url = URL_DWD_WARNCELL.format(
                    south=lat-0.01, west=lon-0.01, north=lat+0.01, east=lon+0.01
                )
                async with session.get(warn_url, timeout=15) as resp:
                    warn_data = await resp.json()
                    features = warn_data.get("features", [])
                    if features:
                        props = features[0].get("properties", {})
                        kreis = str(props.get("KREIS", "Unbekannt"))
                        gemeinde = str(props.get("NAME", "Unbekannt"))
                    else:
                        kreis = gemeinde = "Unbekannt"

                # 2. Pollen
                async with session.get(URL_DWD_POLLEN, timeout=15) as resp:
                    pollen_json = await resp.json()
                    content = pollen_json.get("content", [])
                    search = self._mapping.get(kreis, kreis)
                    
                    match = next((item for item in content if search.lower() in str(item.get("region_name", "")).lower()), None)

                    pollen_results = {}
                    if match:
                        p_vals = match.get("Pollen", {})
                        for p_type in POLLEN_TYPES:
                            val = p_vals.get(p_type, {}).get("today", "0")
                            pollen_results[p_type.lower()] = self._parse_pollen(val)

            return {
                "location": {"gemeinde": gemeinde, "kreis": kreis},
                "pollen": pollen_results,
                "dwd_region": match.get("region_name") if match else "Unbekannt",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as err:
            _LOGGER.error("Update fehlgeschlagen: %s", err)
            return self.data

    def _parse_pollen(self, val) -> int:
        s = str(val).split('-')[-1]
        try: return int(float(s))
        except: return 0
