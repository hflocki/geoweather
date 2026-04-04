"""Constants for GeoWeather."""

DOMAIN = "geoweather"

# ── Config entry keys ────────────────────────────────────────────────────────
CONF_LAT_SENSOR = "lat_sensor"
CONF_LON_SENSOR = "lon_sensor"
CONF_SPEED_SENSOR = "speed_sensor"
CONF_ALT_SENSOR = "alt_sensor"  # optional
CONF_SAT_SENSOR = "sat_sensor"  # optional
CONF_SPEED_THRESHOLD = "speed_threshold"
CONF_MIN_SATELLITES = "min_satellites"

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_SPEED_THRESHOLD = 5.0  # km/h  – above this = moving
DEFAULT_MIN_SATELLITES = 4  # below this = bad GPS fix

# ── Service name ─────────────────────────────────────────────────────────────
SERVICE_UPDATE = "update"  # called as geoweather.update

# ── DWD API endpoints ────────────────────────────────────────────────────────
# Statische Gemeindegrenzen (für den Standort-Namen)
URL_DWD_WARNCELL = (
    "https://maps.dwd.de/geoserver/dwd/ows"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=dwd:Warngebiete_Gemeinden"
    "&outputFormat=application/json"
    "&bbox={south},{west},{north},{east},urn:ogc:def:crs:EPSG::4326"
)

# 1. Nur Gemeinde-Warnungen
URL_DWD_WARNINGS_GEMEINDE = (
    "https://maps.dwd.de/geoserver/dwd/ows"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=dwd:Warnungen_Gemeinden"
    "&outputFormat=application/json"
    "&bbox={south},{west},{north},{east},urn:ogc:def:crs:EPSG::4326"
)

# 2. Nur Kreis-Warnungen (vereinigt)
URL_DWD_WARNINGS_KREIS = (
    "https://maps.dwd.de/geoserver/dwd/ows"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=dwd:Warnungen_Gemeinden_vereinigt"
    "&outputFormat=application/json"
    "&bbox={south},{west},{north},{east},urn:ogc:def:crs:EPSG::4326"
)

URL_DWD_POLLEN = "https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json"

URL_DWD_RADAR = (
    "https://opendata.dwd.de/weather/radar/composite/rv/DE1200_RV_LATEST.tar.bz2"
)


# ── DWD lookup tables ────────────────────────────────────────────────────────
DWD_SEVERITY = {
    10: "Minor",
    20: "Moderate",
    30: "Severe",
    40: "Extreme",
}

DWD_EVENT_TYPES = {
    22: "Frost",
    24: "Glätte",
    31: "Gewitter",
    33: "Starkes Gewitter",
    34: "Starkes Gewitter mit Sturm",
    36: "Starkes Gewitter mit Hagel",
    38: "Heftiges Gewitter",
    40: "Schweres Gewitter",
    41: "Orkanartiger Sturm",
    42: "Orkan",
    44: "Windböen",
    45: "Sturmböen",
    46: "Schwere Sturmböen",
    48: "Extrem schwere Sturmböen",
    51: "Windböen",
    52: "Sturmböen",
    53: "Schwere Sturmböen",
    54: "Extrem schwere Sturmböen",
    55: "Orkanartige Böen",
    56: "Orkanböen",
    57: "Extrem orkanartige Böen",
    58: "Extremer Orkan",
    61: "Starkregen",
    62: "Heftiger Starkregen",
    63: "Dauerregen",
    64: "Ergiebiger Dauerregen",
    65: "Extrem ergiebiger Dauerregen",
    66: "Extrem heftiger Starkregen",
    70: "Leichter Schneefall",
    71: "Schneefall",
    72: "Starker Schneefall",
    73: "Extrem starker Schneefall",
    74: "Schneeverwehungen",
    75: "Starke Schneeverwehungen",
    76: "Extrem starke Schneeverwehungen",
    82: "Nebel",
    84: "Dichter Nebel",
    85: "Extrem dichter Nebel",
    87: "Glätte",
    88: "Glatteis",
    89: "Schweres Glatteis",
    90: "Gewitter",
    91: "Starkes Gewitter",
    92: "Heftiges Gewitter",
    93: "Extrem heftiges Gewitter",
    95: "Hagel",
    96: "Schwerer Hagel",
}

# ── Pollen ───────────────────────────────────────────────────────────────────
POLLEN_TYPES = [
    "Birke",
    "Graeser",
    "Roggen",
    "Erle",
    "Hasel",
    "Esche",
    "Ambrosia",
    "Beifuss",
    "Eiche",
]
