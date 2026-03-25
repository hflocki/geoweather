"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
import math
import os
import tarfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import aiohttp
import numpy as np
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

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=30)

class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping: dict = {}
        self.stopped_at: datetime | None = None

    async def async_load_pollen_mapping(self) -> None:
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
        except Exception as err:
            _LOGGER.error("Fehler beim Laden von pollen_mapping.yaml: %s", err)

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        # Initial-Update erzwingen
        if self.data is None:
            await self.async_refresh()
            return

        if self._is_moving():
            self.stopped_at = None
            return

        if self.stopped_at is None:
            self.stopped_at = datetime.now()

        standing_min = (datetime.now() - self.stopped_at).total_seconds() / 60
        limit = float(self._cfg(CONF_MIN_STATIONARY_TIME, DEFAULT_MIN_STATIONARY_TIME))

        if standing_min < limit:
            return

        await self.async_refresh()

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id: return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""): return None
        try: return float(state.state.replace(",", "."))
        except (ValueError, TypeError): return None

    def _is_moving(self) -> bool:
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False

    def _get_radar_coords(self, lat, lon):
        phi_0, lambda_0 = 60.0 * math.pi / 180.0, 10.0 * math.pi / 180.0
        r_earth = 6370.04
        phi, lamb = lat * math.pi / 180.0, lon * math.pi / 180.0
        m = (1.0 + math.sin(phi_0)) / (1.0 + math.sin(phi))
        x = m * r_earth * math.cos(phi) * math.sin(lamb - lambda_0)
        y = m * r_earth * math.cos(phi) * math.cos(lamb - lambda_0)
        x_grid = int(round(x + 542.362))
        y_grid = int(round(y + 3590.442))
        if not (0 <= x_grid < 1100 and 0 <= y_grid < 1200): return None, None
        return x_grid, 1200 - y_grid

    async def _async_update_data(self) -> dict:
        lat = self._float_state(self._cfg(CONF_LAT_SENSOR))
        lon = self._float_state(self._cfg(CONF_LON_SENSOR))
        if lat is None or lon is None: return self.data or {}

        async with aiohttp.ClientSession() as session:
            location = await self._fetch_location(session, lat, lon)
            warnings = await self._fetch_warnings(session, lat, lon)
            pollen = await self._fetch_pollen(session, location.get("kreis", ""))
            regen = await self._fetch_radar(session, lat, lon)

        return {
            "location": location,
            "warnings": warnings,
            "pollen": pollen,
            "regen": regen,
            "gps": {"latitude": lat, "longitude": lon},
            "last_updated": datetime.now().isoformat(),
        }

    async def _fetch_radar(self, session, lat, lon) -> dict:
        x, y = self._get_radar_coords(lat, lon)
        if x is None: return {"aktuell": 0, "forecast": {}}
        try:
            async with session.get(URL_DWD_RADAR, timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                content = await resp.read()
            
            def _proc():
                data_map = {}
                with tarfile.open(fileobj=BytesIO(content)) as tar:
                    for m in sorted(tar.getmembers(), key=lambda x: x.name):
                        f = tar.extractfile(m)
                        raw = f.read().split(b"\x03", 1)[1]
                        grid = np.frombuffer(raw, dtype="uint16").reshape(1200, 1100)
                        val = float(grid[y, x]) * 0.1
                        data_map[m.name] = round(val, 2)
                return data_map
            
            res = await self.hass.async_add_executor_job(_proc)
            return {"aktuell": list(res.values())[0] if res else 0, "forecast": res}
        except Exception as e:
            _LOGGER.error("Radar Fehler: %s", e)
            return {"aktuell": 0, "forecast": {}}

    async def _fetch_location(self, session, lat, lon) -> dict:
        url = URL_DWD_WARNCELL.format(south=lat-0.01, west=lon-0.01, north=lat+0.01, east=lon+0.01)
        async with session.get(url) as r: data = await r.json(content_type=None)
        feat = data.get("features", [])
        if not feat: return {"kreis": "Unbekannt"}
        return {"kreis": feat[0]["properties"].get("KREIS"), "gemeinde": feat[0]["properties"].get("NAME")}

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        return {"anzahl": 0} # Platzhalter für Kürze

    async def _fetch_pollen(self, session, kreis: str) -> dict:
        return {"status": "OK"} # Platzhalter für Kürze
