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
        import numpy as np

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
                    _LOGGER.debug(
                        "Radar-Member '%s' übersprungen: %s", member.name, exc
                    )

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

    def get_next_precipitation(self, x, y):
        precipitation_values = self.get_precipitation_values(x, y)
        if not precipitation_values:
            return {"start": None, "end": None, "length": 0, "max": 0, "sum": 0}

        rain_start = None
        rain_end = None
        rain_max = 0.0
        rain_sum = 0.0

        sorted_times = sorted(precipitation_values.keys())

        for rain_time in sorted_times:
            precip = precipitation_values[rain_time]

            if precip > 0:
                if rain_start is None:
                    rain_start = rain_time
                # Wir schieben das Ende immer weiter nach hinten, solange es regnet
                rain_end = rain_time + timedelta(minutes=5)
                rain_max = max(rain_max, precip)
                rain_sum += precip / 12
            else:
                # Wenn wir schon Regen hatten und jetzt eine 0 kommt:
                # Nur abbrechen, wenn wir weit genug in der Zukunft sind (Ende gefunden)
                if rain_start is not None:
                    # Optional: Hier könnte man kleine Pausen von 5 Min ignorieren.
                    # Für den Moment: Wir haben ein Ende gefunden.
                    if rain_end is not None and rain_time >= rain_end:
                        break

        # Berechnung der Länge
        length_min = 0
        if rain_start and rain_end:
            length_min = int((rain_end - rain_start).total_seconds() / 60)

        return {
            "start": rain_start,
            "end": rain_end,
            "length": length_min,
            "max": round(rain_max, 2),
            "sum": round(rain_sum, 2),
        }

    def get_forecast_map(self, lat: float, lon: float) -> dict[str, float]:
        """Gibt alle Forecast-Zeitschritte als {ISO-Zeitstring: mm/h} zurück."""
        return {
            t.isoformat(): v for t, v in self.get_precipitation_values(lat, lon).items()
        }

    def get_current_value(self, lat: float, lon: float) -> float:
        """Gibt den aktuellsten verfügbaren Messwert zurück (erster Zeitschritt)."""
        values = self.get_precipitation_values(lat, lon)
        if not values:
            return 0.0
        return next(iter(values.values()))
