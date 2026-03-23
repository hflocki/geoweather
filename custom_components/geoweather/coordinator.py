"""DataUpdateCoordinator for GeoWeather."""
from __future__ import annotations

import logging
from datetime import datetime
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_LAT_SENSOR,
    CONF_LON_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_SPEED_THRESHOLD,
    URL_DWD_WARNCELL,
    URL_DWD_POLLEN,
    POLLEN_TYPES,
    POLLEN_REGION_MAPPING,
)

_LOGGER = logging.getLogger(__name__)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Manages all DWD data fetching."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None, # Wir updaten nur per Service oder manuell
        )
        self.entry = entry
        self.last_skip_reason = None

    async def async_service_update(self, call=None) -> None:
        """Wird vom geoweather.update Service aufgerufen."""
        _LOGGER.debug("Service Update getriggert")
        await self.async_refresh()

    async def _async_update_data(self):
        """Hole Daten vom DWD."""
        lat_id = self.entry.data.get(CONF_LAT_SENSOR)
        lon_id = self.entry.data.get(CONF_LON_SENSOR)
        
        lat_s = self.hass.states.get(lat_id)
        lon_s = self.hass.states.get(lon_id)

        if not lat_s or not lon_s or lat_s.state in ("unknown", "unavailable"):
            self.last_skip_reason = "Kein GPS Fix"
            return self.data # Behalte alte Daten

        try:
            lat = float(str(lat_s.state).replace(',', '.'))
            lon = float(str(lon_s.state).replace(',', '.'))
            
            async with aiohttp.ClientSession() as session:
                # 1. Warnzelle
                warn_url = URL_DWD_WARNCELL.format(
                    south=lat-0.01, west=lon-0.01, north=lat+0.01, east=lon+0.01
                )
                async with session.get(warn_url, timeout=15) as resp:
                    warn_data = await resp.json()
                    if not warn_data.get("features"):
                        return {"error": "Außerhalb DWD Bereich"}
                    
                    props = warn_data["features"][0]["properties"]
                    kreis = str(props.get("KREIS", "Unbekannt"))
                    gemeinde = str(props.get("NAME", "Unbekannt"))

                # 2. Pollen
                async with session.get(URL_DWD_POLLEN, timeout=15) as resp:
                    pollen_json = await resp.json()
                    content = pollen_json.get("content", [])
                    
                    # Mapping
                    search = POLLEN_REGION_MAPPING.get(kreis, kreis)
                    match = next((item for item in content if search.lower() in str(item.get("region_name", "")).lower() 
                                 or search.lower() in str(item.get("partregion_name", "")).lower()), None)

                    pollen_results = {}
                    if match:
                        p_vals = match.get("Pollen", {})
                        for p_type in POLLEN_TYPES:
                            val = p_vals.get(p_type, {}).get("today", "0")
                            pollen_results[p_type.lower()] = _parse_pollen(val)

            return {
                "location": {"gemeinde": gemeinde, "kreis": kreis},
                "pollen": pollen_results,
                "last_updated": datetime.now().isoformat()
            }

        except Exception as err:
            _LOGGER.error("Update Fehler: %s", err)
            raise UpdateFailed(f"DWD API Fehler: {err}")

def _parse_pollen(val) -> int:
    """Wandelt DWD Werte sicher um."""
    if val is None: return 0
    s = str(val).strip().lower()
    if s in ("-1", "", "nan", "null", "none"): return 0
    try:
        if '-' in s: return int(s.split('-')[-1])
        return int(float(s))
    except: return 0
