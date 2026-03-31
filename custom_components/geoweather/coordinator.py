"""DataUpdateCoordinator for GeoWeather."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
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
    CONF_UPDATE_INTERVAL,
    DEFAULT_MIN_SATELLITES,
    DEFAULT_SPEED_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    DWD_EVENT_TYPES,
    DWD_SEVERITY,
    POLLEN_TYPES,
    URL_DWD_POLLEN,
    URL_DWD_RADAR,
    URL_DWD_WARNCELL,
    URL_DWD_WARNINGS_GEMEINDE,
    URL_DWD_WARNINGS_KREIS,
)
from .dwdradar import DWDRadar
from .mapping import POLLEN_REGION_MAPPING

_LOGGER = logging.getLogger(__name__)


class GeoWeatherCoordinator(DataUpdateCoordinator):
    """Zentrale für Standort, Warnungen, Pollen und Radar-Regendaten."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        interval_min = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        update_interval = timedelta(minutes=interval_min) if interval_min > 0 else None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.entry = entry
        self.last_skip_reason: str | None = None
        self._pollen_mapping = POLLEN_REGION_MAPPING
        self._radar_etag: str | None = None
        self._radar_bytes: bytes | None = None
        self.last_update_success_time = None

        _LOGGER.info(
            "[Pollen Mapping Assistant] Datei erfolgreich eingelesen. %s Orte im Mapping gefunden.",
            len(self._pollen_mapping),
        )

    async def _async_update_data(self) -> dict:
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

                kreis_name = location.get("kreis", "Unbekannt")
                if kreis_name != "Unbekannt":
                    pollen = await self._fetch_pollen(session, kreis_name)
                else:
                    pollen = {
                        "dwd_teilregion": "Warte auf Standort...",
                        "dwd_region_id": "??",
                    }

                # Kreisnamen aus der Standortsuche direkt in das Pollen-Objekt einfügen
                pollen["aktueller_kreis"] = kreis_name

                regen = await self._fetch_radar(session, lat, lon)

        except Exception as exc:
            _LOGGER.error("Fehler beim DWD-Abruf: %s", exc)
            raise UpdateFailed(f"DWD-Abruf fehlgeschlagen: {exc}")

        return {
            "location": location,
            "radar": regen,
            "warnings": warnings,
            "pollen": pollen,  # Hier stecken jetzt ID, Region und Kreis drin
            "regen": regen,
            "gps": {
                "latitude": lat,
                "longitude": lon,
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_pollen(self, session: aiohttp.ClientSession, kreis: str) -> dict:
        """Sucht die Region-ID und ruft DWD Daten ab."""

        suche_ort = str(kreis).strip()

        # DEBUG-LOG:
        _LOGGER.debug("[Pollen Debug] Suche nach: '%s'", suche_ort)
        _LOGGER.debug(
            "[Pollen Debug] Vorhandene Orte im Mapping: %s",
            list(self._pollen_mapping.keys()),
        )

        # ID aus dem Mapping holen
        target_id = self._pollen_mapping.get(suche_ort)

        if target_id is None:
            # Log was wurde geladen
            _LOGGER.warning(
                "GeoWeather: Kein ID-Mapping für Ort '%s' gefunden! "
                "(Mapping enthält %s Einträge). Bitte in der mapping.py ergänzen.",
                suche_ort,
                len(self._pollen_mapping),
            )
            return {f"{p.lower()}_today": 0.0 for p in POLLEN_TYPES}

        try:
            async with session.get(URL_DWD_POLLEN) as resp:
                if resp.status != 200:
                    return {"dwd_teilregion": "Server-Fehler"}
                data = await resp.json(content_type=None)
        except Exception as e:
            _LOGGER.error("Pollen-Abruf fehlgeschlagen: %s", e)
            return {"dwd_teilregion": "Abruffehler"}

        res = {"dwd_teilregion": "Unbekannt", "dwd_region_id": target_id}
        all_today_values = []

        def _convert_to_index(val):
            """Umrechnung laut DWD-Legende (v2.0.0 Standard)."""
            v = str(val).strip()
            mapping = {
                "0": 0.0,
                "0-1": 0.5,
                "1": 1.0,
                "1-2": 1.5,
                "2": 2.0,
                "2-3": 2.5,
                "3": 3.0,
            }
            return mapping.get(v, 0.0)

        def _clean(text):
            return (
                str(text)
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
            )

        # 2. Den richtigen Eintrag im DWD-JSON über die ID finden
        found_entry = None
        for entry in data.get("content", []):
            t_str = str(target_id)
            # Abgleich gegen partregion_id oder region_id
            if t_str == str(entry.get("partregion_id")) or t_str == str(
                entry.get("region_id")
            ):
                found_entry = entry
                break

        if found_entry:
            res["dwd_teilregion"] = found_entry.get(
                "partregion_name"
            ) or found_entry.get("region_name")
            pdata = found_entry.get("Pollen") or found_entry.get("pollen") or {}

            for p_type in POLLEN_TYPES:
                clean_type = _clean(p_type)
                val_today = 0.0
                val_tomorrow = 0.0

                for dwd_key, dwd_content in pdata.items():
                    if clean_type == _clean(dwd_key):
                        val_today = _convert_to_index(dwd_content.get("today"))
                        val_tomorrow = _convert_to_index(dwd_content.get("tomorrow"))
                        break

                # Speicherung der Einzelwerte
                res[f"{clean_type}_today"] = val_today
                res[f"{clean_type}_tomorrow"] = val_tomorrow
                res[f"pollen_{clean_type}"] = val_today

                all_today_values.append(val_today)

            # 3. Den Maximalwert für den Hauptsensor berechnen
            res["pollen_max_today"] = max(all_today_values) if all_today_values else 0.0
        else:
            _LOGGER.error(
                "GeoWeather: ID '%s' im DWD-Datensatz nicht gefunden!", target_id
            )

        return res

    async def _fetch_location(self, session, lat, lon) -> dict:
        import time

        t = int(time.time())
        south, north, west, east = lat - 0.005, lat + 0.005, lon - 0.005, lon + 0.005
        url = (
            URL_DWD_WARNCELL.format(south=south, west=west, north=north, east=east)
            + f"&_={t}"
        )
        async with session.get(url) as resp:
            if resp.status != 200:
                return {"gemeinde": "Fehler", "kreis": "Unbekannt"}
            data = await resp.json(content_type=None)
        if not data.get("features"):
            return {"gemeinde": "Unbekannt", "kreis": "Unbekannt"}
        p = data["features"][0]["properties"]
        return {
            "gemeinde": p.get("NAME"),
            "kreis": p.get("KREIS"),
            "warncellid": p.get("WARNCELLID"),
        }

    async def _fetch_warnings(self, session, lat, lon) -> dict:
        import time

        t = int(time.time())
        south, north, west, east = lat - 0.005, lat + 0.005, lon - 0.005, lon + 0.005
        urls = [
            URL_DWD_WARNINGS_GEMEINDE.format(
                south=south, west=west, north=north, east=east
            )
            + f"&_={t}",
            URL_DWD_WARNINGS_KREIS.format(
                south=south, west=west, north=north, east=east
            )
            + f"&_={t}",
        ]
        all_features = []
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        all_features.extend(data.get("features", []))
            except Exception as e:
                _LOGGER.error("DWD Warnungs-Abruf fehlgeschlagen: %s", e)
        items = []
        seen_ids = set()
        sev_map = {"Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}
        for feat in all_features:
            p = feat.get("properties", {})
            unique_id = f"{p.get('EVENT')}_{p.get('HEADLINE')}"
            if unique_id in seen_ids:
                continue
            seen_ids.add(unique_id)
            raw_event = p.get("EVENT", "Unbekannt")
            ereignis = (
                raw_event.capitalize()
                if isinstance(raw_event, str) and not raw_event.isdigit()
                else DWD_EVENT_TYPES.get(int(raw_event or 0), str(raw_event))
            )
            raw_sev = p.get("SEVERITY", "Minor")
            sev_level = sev_map.get(raw_sev, 1)
            items.append(
                {
                    "ereignis": ereignis,
                    "schwere": DWD_SEVERITY.get(sev_level, "Unbekannt"),
                    "schwere_level": sev_level,
                    "headline": p.get("HEADLINE", ""),
                    "beschreibung": p.get("DESCRIPTION", ""),
                    "beginn": p.get("ONSET"),
                    "ende": p.get("EXPIRES"),
                }
            )
        items.sort(key=lambda x: x["schwere_level"], reverse=True)
        return {"anzahl": len(items), "warnungen": items}

    async def _fetch_radar(self, session, lat, lon) -> dict:
        headers = {"If-None-Match": self._radar_etag} if self._radar_etag else {}
        async with session.get(URL_DWD_RADAR, headers=headers) as resp:
            if resp.status == 200:
                self._radar_bytes = await resp.read()
                self._radar_etag = resp.headers.get("ETag")
            elif resp.status != 304:
                return {"aktuell": 0, "next_length": 0}
        if not self._radar_bytes:
            return {"aktuell": 0, "next_length": 0}

        def _process():
            r = DWDRadar()
            r.load_from_bytes(self._radar_bytes)
            res_data = r.get_next_precipitation(lat, lon)
            return {
                "aktuell": r.get_current_value(lat, lon),
                "forecast": r.get_forecast_map(lat, lon),
                "next_length": res_data.get("length", 0),
                "next_start": res_data.get("start"),
                "next_end": res_data.get("end"),
                "next_max_mmh": res_data.get("max", 0.0),
                "next_sum_mm": res_data.get("sum", 0.0),
            }

        return await self.hass.async_add_executor_job(_process)

    def _cfg(self, key, default=None):
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        if not entity_id or not isinstance(entity_id, str):
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
        return (
            speed > float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
            if speed is not None
            else False
        )

    def _has_valid_fix(self):
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        return (
            sats >= float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
            if sats is not None
            else True
        )

    async def async_service_update(self, call: ServiceCall | None = None) -> None:
        """Service-Aufruf für manuelles Update."""
        await self.async_refresh()

    def _cfg(self, key, default=None):
        """Hilfsfunktion für Config-Werte."""
        return {**self.entry.data, **self.entry.options}.get(key, default)

    def _float_state(self, entity_id: str | None) -> float | None:
        """Extrahiert einen Float-Wert aus einem Entity-Status."""
        if not entity_id or not isinstance(entity_id, str):
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state.replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _is_moving(self) -> bool:
        """Prüft, ob sich das Fahrzeug bewegt."""
        speed = self._float_state(self._cfg(CONF_SPEED_SENSOR))
        threshold = float(self._cfg(CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD))
        return speed > threshold if speed is not None else False

    def _has_valid_fix(self):
        """Prüft auf GPS-Satelliten."""
        sats = self._float_state(self._cfg(CONF_SAT_SENSOR))
        min_sats = float(self._cfg(CONF_MIN_SATELLITES, DEFAULT_MIN_SATELLITES))
        return sats >= min_sats if sats is not None else True
