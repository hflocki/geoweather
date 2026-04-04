"""
DWD Radar – eigenständige Klasse für Niederschlagsradar-Daten.
Basiert auf: https://github.com/stoppegp/ha-dwd-precipitation-forecast
Angepasst für asynchrone Nutzung in GeoWeather (kein blocking requests).

FIX v2.3.2:
  - get_next_precipitation: Nur Zeitschritte AB JETZT auswerten (kein Blick in die Vergangenheit)
  - get_forecast_2h: Neues Feature - Zusammenfassung der nächsten 2 Stunden
  - get_current_value: Sucht den nächsten Zeitschritt um/nach jetzt statt blind ersten zu nehmen
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

# Wie viele Minuten in die Zukunft schaut get_forecast_2h?
FORECAST_WINDOW_MIN = 120


class NotInAreaError(Exception):
    """GPS-Koordinate liegt ausserhalb des DWD-Radar-Bereichs."""


class RadarNotAvailableError(Exception):
    """Radar-Daten sind noch nicht geladen."""


class DWDRadar:
    """
    Verarbeitet DWD-Radar-Daten (RV-Format, tar.bz2).

    Nutzung:
        radar = DWDRadar()
        radar.load_from_bytes(content)
        current = radar.get_current_value(lat, lon)
        result  = radar.get_next_precipitation(lat, lon)
        f2h     = radar.get_forecast_2h(lat, lon)
    """

    def __init__(self) -> None:
        self._radars: dict[datetime, "np.ndarray"] | None = None

    def load_from_bytes(self, content: bytes) -> None:
        import numpy as np

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
                        "Radar-Member '%s' uebersprungen: %s", member.name, exc
                    )

        self._radars = dict(sorted(radars.items()))
        _LOGGER.debug("Radar geladen: %d Zeitschritte", len(self._radars))

    def get_location_index(self, lat: float, lon: float) -> tuple[int, int]:
        """GPS-Koordinaten -> DWD-Radar-Gitterindex."""
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
                f"Koordinaten ({lat}, {lon}) liegen ausserhalb des DWD-Radar-Bereichs"
            )
        return x_cart, y_cart

    def get_precipitation_values(
        self, lat: float, lon: float, future_only: bool = False
    ) -> dict[datetime, float]:
        """
        Gibt Niederschlagswerte [mm/h] fuer alle (oder nur zukuenftige) Zeitschritte zurueck.

        Args:
            lat: Breitengrad
            lon: Laengengrad
            future_only: Wenn True, nur Zeitschritte >= jetzt. Wichtig fuer Vorhersage!
        """
        if self._radars is None:
            raise RadarNotAvailableError("Keine Radar-Daten geladen")

        x_cart, y_cart = self.get_location_index(lat, lon)
        now = datetime.now(UTC)
        values: dict[datetime, float] = {}

        for radar_time, grid in self._radars.items():
            # BUG-FIX: Vergangenheit ueberspringen wenn future_only=True
            if future_only and radar_time < now - timedelta(minutes=5):
                continue

            raw_val = int(grid[y_cart][x_cart])
            if raw_val & 0b0010000000000000:
                value = 0.0
            else:
                value = float(raw_val & 0b0000111111111111) / 100 * 12
            values[radar_time] = round(value, 2)

        return values

    def get_current_value(self, lat: float, lon: float) -> float:
        """
        Gibt den aktuellen Niederschlagswert zurueck.
        Waehlt den Zeitschritt, der jetzt am naechsten liegt.
        """
        if self._radars is None:
            return 0.0

        x_cart, y_cart = self.get_location_index(lat, lon)
        now = datetime.now(UTC)

        closest_time = None
        closest_delta = timedelta(minutes=999)

        for radar_time in self._radars:
            delta = abs(radar_time - now)
            if delta < closest_delta and radar_time <= now + timedelta(minutes=5):
                closest_delta = delta
                closest_time = radar_time

        if closest_time is None:
            return 0.0

        grid = self._radars[closest_time]
        raw_val = int(grid[y_cart][x_cart])
        if raw_val & 0b0010000000000000:
            return 0.0
        return round(float(raw_val & 0b0000111111111111) / 100 * 12, 2)

    def get_next_precipitation(self, lat: float, lon: float) -> dict:
        """
        BUG-FIX: Sucht naechsten Regenabschnitt NUR in der Zukunft.
        Gibt Start, Ende, Laenge, Max und Summe zurueck.
        """
        precipitation_values = self.get_precipitation_values(lat, lon, future_only=True)
        if not precipitation_values:
            return {"start": None, "end": None, "length": 0, "max": 0.0, "sum": 0.0}

        rain_start = None
        rain_end = None
        rain_max = 0.0
        rain_sum = 0.0
        dry_steps = 0
        MAX_DRY_STEPS = 2  # bis zu 10 Min Pause werden ignoriert

        for rain_time in sorted(precipitation_values.keys()):
            precip = precipitation_values[rain_time]

            if precip > 0:
                dry_steps = 0
                if rain_start is None:
                    rain_start = rain_time
                rain_end = rain_time + timedelta(minutes=5)
                rain_max = max(rain_max, precip)
                rain_sum += precip / 12
            else:
                if rain_start is not None:
                    dry_steps += 1
                    if dry_steps > MAX_DRY_STEPS:
                        break

        length_min = 0
        if rain_start and rain_end:
            length_min = int((rain_end - rain_start).total_seconds() / 60)

        return {
            "start": rain_start.isoformat() if rain_start else None,
            "end": rain_end.isoformat() if rain_end else None,
            "length": length_min,
            "max": round(rain_max, 2),
            "sum": round(rain_sum, 2),
        }

    def get_forecast_2h(self, lat: float, lon: float) -> dict:
        """
        NEU: Zusammenfassung der Regenvorhersage fuer die naechsten 2 Stunden.

        Gibt zurueck:
          - raining_now:       bool  - Regnet es gerade?
          - rain_expected:     bool  - Kommt Regen in den naechsten 2h?
          - next_rain_start:   ISO   - Wann beginnt naechster Regen?
          - next_rain_end:     ISO   - Wann endet er (innerhalb Fenster)?
          - next_rain_in_min:  int   - In wie vielen Minuten beginnt Regen?
          - duration_min:      int   - Wie lange dauert er?
          - max_intensity_mmh: float - Maximale Intensitaet [mm/h]
          - total_mm:          float - Gesamtniederschlag [mm]
          - forecast_steps:    dict  - Alle 5-Min-Schritte {ISO: mm/h}
        """
        now = datetime.now(UTC)
        cutoff = now + timedelta(minutes=FORECAST_WINDOW_MIN)

        current_val = self.get_current_value(lat, lon)
        raining_now = current_val > 0

        future_values = {
            t: v
            for t, v in self.get_precipitation_values(
                lat, lon, future_only=True
            ).items()
            if t <= cutoff
        }

        forecast_steps = {t.isoformat(): v for t, v in sorted(future_values.items())}

        rain_start = None
        rain_end = None
        rain_max = 0.0
        rain_sum = 0.0
        dry_steps = 0
        MAX_DRY_STEPS = 2

        for t in sorted(future_values.keys()):
            v = future_values[t]
            if v > 0:
                dry_steps = 0
                if rain_start is None:
                    rain_start = t
                rain_end = t + timedelta(minutes=5)
                rain_max = max(rain_max, v)
                rain_sum += v / 12
            else:
                if rain_start is not None:
                    dry_steps += 1
                    if dry_steps > MAX_DRY_STEPS:
                        break

        next_rain_in_min = None
        duration_min = 0

        if rain_start is not None:
            delta = (rain_start - now).total_seconds() / 60
            next_rain_in_min = max(0, int(delta))
            if rain_end:
                duration_min = int((rain_end - rain_start).total_seconds() / 60)

        return {
            "raining_now": raining_now,
            "rain_expected": rain_start is not None,
            "next_rain_start": rain_start.isoformat() if rain_start else None,
            "next_rain_end": rain_end.isoformat() if rain_end else None,
            "next_rain_in_min": next_rain_in_min,
            "duration_min": duration_min,
            "max_intensity_mmh": round(rain_max, 2),
            "total_mm": round(rain_sum, 2),
            "forecast_steps": forecast_steps,
        }

    def get_forecast_map(self, lat: float, lon: float) -> dict[str, float]:
        """Gibt alle Forecast-Zeitschritte als {ISO-Zeitstring: mm/h} zurueck."""
        return {
            t.isoformat(): v
            for t, v in self.get_precipitation_values(
                lat, lon, future_only=False
            ).items()
        }
