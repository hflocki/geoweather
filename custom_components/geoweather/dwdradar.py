"""
DWD Radar – eigenständige Klasse für Niederschlagsradar-Daten.
Basiert auf: https://github.com/stoppegp/ha-dwd-precipitation-forecast
Angepasst für asynchrone Nutzung in GeoWeather (kein blocking requests).
"""
from __future__ import annotations

import logging
import math
import tarfile
from datetime import UTC, datetime, timedelta
from io import BytesIO

import numpy as np

_LOGGER = logging.getLogger(__name__)

RADAR_XSIZE = 1100
RADAR_YSIZE = 1200


class NotInAreaError(Exception):
    """GPS-Koordinate liegt außerhalb des DWD-Radar-Bereichs."""


class RadarNotAvailableError(Exception):
    """Radar-Daten sind noch nicht geladen."""


class DWDRadar:
    """
    Verarbeitet DWD-Radar-Daten (RV-Format, tar.bz2).
    
    Nutzung:
        radar = DWDRadar()
        radar.load_from_bytes(content)          # content = bytes aus HTTP-Response
        values = radar.get_precipitation_values(lat, lon)
        result = radar.get_next_precipitation(lat, lon)
    """

    def __init__(self) -> None:
        self._radars: dict[datetime, np.ndarray] | None = None

    def load_from_bytes(self, content: bytes) -> None:
        """Lädt Radar-Daten aus einem bereits heruntergeladenen tar.bz2-Archiv."""
        radars: dict[datetime, np.ndarray] = {}
        with tarfile.open(fileobj=BytesIO(content)) as tar:
            for member in tar.getmembers():
                try:
                    radar_minute_delta = int(member.name[-3:])
                    radar_time = datetime.strptime(
                        member.name[-14:-4], "%y%m%d%H%M"
                    ).replace(tzinfo=UTC) + timedelta(minutes=radar_minute_delta)

                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    raw = f.read().split(b"\x03", 1)[1]
                    radars[radar_time] = np.frombuffer(raw, dtype="uint16").reshape(
                        RADAR_YSIZE, RADAR_XSIZE
                    )
                except Exception as exc:
                    _LOGGER.debug("Radar-Member '%s' übersprungen: %s", member.name, exc)

        self._radars = dict(sorted(radars.items()))
        _LOGGER.debug("Radar geladen: %d Zeitschritte", len(self._radars))

    def get_location_index(self, lat: float, lon: float) -> tuple[int, int]:
        """GPS-Koordinaten → DWD-Radar-Gitterindex (identisch zur Referenz)."""
        x_cart = int(
            6370.04
            * (1 + math.sin(60 / 180 * math.pi))
            / (1 + math.sin(lat / 180 * math.pi))
            * math.cos(lat / 180 * math.pi)
            * math.sin((lon - 10) / 180 * math.pi)
            + 543.4622
        )
        y_cart = int(
            -6370.04
            * (1 + math.sin(60 / 180 * math.pi))
            / (1 + math.sin(lat / 180 * math.pi))
            * math.cos(lat / 180 * math.pi)
            * math.cos((lon - 10) / 180 * math.pi)
            + 4808.645
        )
        if not (0 <= y_cart < RADAR_YSIZE) or not (0 <= x_cart < RADAR_XSIZE):
            raise NotInAreaError(
                f"Koordinaten ({lat}, {lon}) liegen außerhalb des DWD-Radar-Bereichs"
            )
        return x_cart, y_cart

    def get_precipitation_values(self, lat: float, lon: float) -> dict[datetime, float]:
        """Gibt Niederschlagswerte [mm/h] für alle Zeitschritte zurück."""
        if self._radars is None:
            raise RadarNotAvailableError("Keine Radar-Daten geladen")

        x_cart, y_cart = self.get_location_index(lat, lon)
        values: dict[datetime, float] = {}

        for radar_time, grid in self._radars.items():
            raw_val = int(grid[y_cart][x_cart])
            # Bit 13 gesetzt = kein gültiger Messwert (Fehler/Lücke)
            if raw_val & 0b0010000000000000:
                value = 0.0
            else:
                # Untere 12 Bit = Messwert; Skalierung: /100 * 12 → mm/h
                value = float(raw_val & 0b0000111111111111) / 100 * 12
            values[radar_time] = round(value, 2)

        return values

    def get_next_precipitation(self, lat: float, lon: float) -> dict:
        """
        Ermittelt Regenstart, -ende, -dauer, -max und -summe aus dem Forecast.
        Gibt dict mit 'start', 'end', 'length', 'max', 'sum' zurück.
        """
        rain_start: datetime | None = None
        rain_end: datetime | None = None
        rain_max = 0.0
        rain_sum = 0.0

        for rain_time, precip in self.get_precipitation_values(lat, lon).items():
            if rain_start is None and precip > 0:
                rain_start = rain_time
                rain_max = precip
                rain_sum = precip
                continue
            if rain_start is not None:
                rain_max = max(rain_max, precip)
                rain_sum += precip
            if rain_start is not None and rain_end is None and precip == 0:
                rain_end = rain_time
                continue
            if rain_start is not None and rain_end is not None and precip != 0:
                rain_end = None
                continue
            if rain_start is not None and rain_end is not None and precip == 0:
                break

        rain_length: timedelta | None = None
        if rain_start is not None:
            rain_sum = rain_sum / 12
            if rain_end is not None:
                rain_length = rain_end - rain_start

        return {
            "start": rain_start.isoformat() if rain_start else None,
            "end": rain_end.isoformat() if rain_end else None,
            "length_min": int(rain_length.total_seconds() / 60) if rain_length else None,
            "max_mmh": round(rain_max, 2),
            "sum_mm": round(rain_sum, 2),
        }

    def get_forecast_map(self, lat: float, lon: float) -> dict[str, float]:
        """Gibt alle Forecast-Zeitschritte als {ISO-Zeitstring: mm/h} zurück."""
        return {
            t.isoformat(): v
            for t, v in self.get_precipitation_values(lat, lon).items()
        }

    def get_current_value(self, lat: float, lon: float) -> float:
        """Gibt den aktuellsten verfügbaren Messwert zurück (erster Zeitschritt)."""
        values = self.get_precipitation_values(lat, lon)
        if not values:
            return 0.0
        return next(iter(values.values()))
