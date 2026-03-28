<img src="/custom_components/geoweather/icon.png" alt="GeoWeather Logo" width="150">

<div align="left">
  <h1>GeoWeather for Home Assistant</h1>

  <p>
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom">
    <img src="https://img.shields.io/github/v/release/hflocki/geoweather" alt="Latest Release">
    <a href="https://www.home-assistant.io"><img src="https://img.shields.io/badge/Home%20Assistant-2023.6%2B-blue" alt="HA Version"></a>
    <a href="https://discord.gg/5JUWSw79Rq"><img src="https://img.shields.io/discord/1484194968385093746?color=5865F2&label=Join%20Discord&logo=discord&logoColor=white" alt="Discord"></a>
    <a href="https://www.buymeacoffee.com/hflocki">
  <img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee">
</a>
  </p>
</div>

GeoWeather ist eine spezialisierte Home Assistant Integration für Wohnmobile und Camper. Sie nutzt die GPS-Koordinaten deines Fahrzeugs, um hyper-lokale Wetter- und Umweltdaten vom Deutschen Wetterdienst (DWD) abzurufen.

- 📍 **Aktueller Standort:** Gemeinde / Kreis / Bundesland / WarnCellID
- ⛈️ **Wetterwarnungen:** Aktive Warnungen mit Schweregrad, Typ und Zeitraum
- 🌿 **Pollenflug-Vorhersage:** Heute / Morgen / Übermorgen für 9 Pollenarten
- 🌧️ **Regenvorhersage:** Aktuelle Niederschlagsintensität + Forecast via DWD Radar
- 🚗 **Fahrt-Erkennung:** Automatische Pausierung von API-Aufrufen während der Fahrt
- ⏱️ **Mindest-Standzeit:** Kein Update bei Kurzstopps (Ampeln, Bahnübergänge)


---

## Installation über HACS
Diese Integration ist noch nicht im standardmäßigen HACS‑Store verfügbar. Du kannst sie jedoch trotzdem über HACS installieren, indem du sie als benutzerdefiniertes Repository hinzufügst.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hflocki&repository=geoweather)


1. Öffne HACS → **Integrationen** → ⋮ → **Benutzerdefinierte Repositories**
2. Füge `https://github.com/hflocki/geoweather` als Typ **Integration** hinzu
3. Installiere **GeoWeather**
4. Starte Home Assistant neu
5. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen → GeoWeather**

## Manuelle Installation
Lade den Quellcode `https://github.com/hflocki/geoweather/releases` herunter.
Entpacke der Quellcode 
Kopiere den Ordner `custom_components/geoweather/` in dein `config/custom_components/` Verzeichnis und starte Home Assistant neu.

```
config/custom_components/geoweather/
```
Starte Homeassistant neu

---

## Konfiguration

Während der Einrichtung wählst du deine GPS-Sensoren aus:

| Feld | Erforderlich | Beschreibung |
|---|---|---|
| Breitengrad-Sensor (Lat) | ✅ | z.B. `sensor.mein_gps_latitude` |
| Längengrad-Sensor (Lon) | ✅ | z.B. `sensor.mein_gps_longitude` |
| Geschwindigkeits-Sensor | ✅ | km/h – wird für die Fahrt-Erkennung genutzt |
| Höhen-Sensor | ➖ | Optional – wird in den Attributen angezeigt |
| Satelliten-Sensor | ➖ | Optional – ermöglicht Prüfung der GPS-Fix-Qualität |
| Geschwindigkeits-Schwellenwert | ➖ | Standard: 5.0 km/h – darüber = Fahrzeug fährt |
| Min. Satelliten | ➖ | Standard: 4 – darunter = schlechter Fix, Update überspringen |
| Mindest steh Zeit | ➖ | Standard: 10 – mann muss mindestens 10 minuten stehen sonst, Update überspringen |

Steh-Zeit
0–30 Minuten, Schritte à 1 Minute, Standard 10 Minuten, Wert 0 = Feature deaktiviert

Funktioniert mit **jeder** GPS-Quelle: ESPHome, GPSd, MQTT-Tracker, Smartphone, etc.

---

## Entitäten

Alle Entitäten werden unter einem gemeinsamen **GeoWeather-Gerät** gruppiert.

| Entität | State | Beschreibung |
|---|---|---|
| `sensor.standort` | Gemeindename | + Kreis, Bundesland, WarnCellID, GPS-Koordinaten |
| `sensor.warnungen` | Anzahl (Integer) | + vollständige Warnliste in Attributen |
| `sensor.pollenflug` | Höchste Stufe heute | + alle 9 Pollenarten × 3 Tage |
| `sensor.regenvorhersage` | mm/h (aktuell) | + Forecast-Map, Regenstart/-ende |
| `binary_sensor.faehrt` | `on`/`off` | `on` = fährt (Updates pausiert) |

> **Hinweis:** Der Warnungen-Sensor liefert als State eine **Ganzzahl** (0, 1, 2, ...). Das ermöglicht einfache Automationen wie `state > 0` statt String-Vergleiche.

---

## Dienst: `geoweather.update`

Löst einen frischen Abruf aller DWD-Daten aus. Wird automatisch übersprungen wenn:
- Das Fahrzeug fährt (Geschwindigkeit > Schwellenwert)
- Der GPS-Fix unzureichend ist (Satelliten < Minimum)
- Die Mindest-Standzeit noch nicht erreicht ist

---

## Pollenflug-Belastungsstufen

Die Integration liefert die präzisen DWD-Stufen als Strings. In Dashboards sollte bei Zwischenstufen (z.B. `1-2`) immer die höhere Warnfarbe gewählt werden.

| Wert | Bedeutung | Beschreibung |
|:---:|---|---|
| **0** | Keine | Keine Belastung nachweisbar |
| **0-1** | Keine bis gering | Erste Pollen, meist symptomfrei |
| **1** | Gering | Leicht erhöhte Konzentration |
| **1-2** | Gering bis mittel | Spürbare Belastung für Allergiker |
| **2** | Mittel | Deutliche Symptome |
| **2-3** | Mittel bis hoch | Starke Belastung, Aufenthalt einschränken |
| **3** | Stark | Maximale Warnstufe |

---

## Pollen Region Mapping

Der DWD liefert Pollendaten nach Regionen (z.B. "Harz"), nicht nach Kreisen. Erstelle eine Datei `pollen_mapping.yaml` direkt in deinem `/config/` Ordner:

```yaml
"Landkreis Harz": "Harz"
"München": "Allgäu/Oberbayern/Bay. Wald"
"Rheinisch-Bergischer Kreis": "Rhein.-Westfäl. Tiefland"
```

Alle verfügbaren Regionen findest du in der `regions.md` im Repository.

---

## Beispiel Automatisierungen

`automation.yaml.example`

---

## Beispiel Dashboard Kacheln

# 🌦️ GeoWeather Dashboard Beispiele

Dieses Dokument enthält fertige Konfigurationen für dein Home Assistant Dashboard. Die Karten sind darauf optimiert, die Daten der GeoWeather-Integration (Warnungen, Pollenflug, Regenradar) übersichtlich darzustellen.

## 🛠️ Voraussetzungen

Damit diese Karten funktionieren, müssen folgende Erweiterungen über **HACS** installiert sein:
1. [button-card](https://github.com/custom-cards/button-card)
2. [mushroom-cards](https://github.com/piitaya/lovelace-mushroom)
3. [card-mod](https://github.com/thomasloven/lovelace-card-mod)

---

## Pollenflug Status (Hauptkarte)
Diese Karte zeigt das aktuelle Maximum der Pollenbelastung. Der Hintergrund und das Icon färben sich je nach Warnstufe automatisch ein.

```yaml
type: custom:button-card
entity: sensor.geoweather_pollenflug
aspect_ratio: 1/1
show_name: true
name: Pollenflug
show_state: true
state_display: |
  [[[
    const s = entity.state;
    if (!s || s === 'unknown' || s === 'unavailable') return 'Lade...';
    if (s === '0')   return 'Keine';
    if (s === '0-1') return 'Keine bis gering';
    if (s === '1')   return 'Gering';
    if (s === '1-2') return 'Gering bis mittel';
    if (s === '2')   return 'Mittel';
    if (s === '2-3') return 'Mittel bis hoch';
    if (s === '3')   return 'Stark';
    return s;
  ]]]
styles:
  card:
    - padding: 5px
    - background-color: |
        [[[
          const s = entity.state;
          if (!s || s === 'unknown' || s === 'unavailable' || s === '0') 
            return 'var(--card-background-color)';
          const val = String(s).includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          if (val === 1) return '#ffeb3b'; // Gelb
          if (val === 2) return '#fb8c00'; // Orange
          if (val >= 3) return '#e53935';  // Rot
          return 'var(--card-background-color)';
        ]]]
  icon:
    - color: |
        [[[
          const s = entity.state;
          if (!s || s === '0' || s === 'unknown' || s === 'unavailable') return '#c5e566';
          const val = String(s).includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          return (val === 1 || val === 2) ? 'black' : 'white';
        ]]]
  name:
    - font-weight: bold
    - font-size: 12px
    - color: |
        [[[
          const s = entity.state;
          if (!s || s === '0' || s === 'unknown' || s === 'unavailable') 
            return 'var(--primary-text-color)';
          const val = String(s).includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          return (val === 1 || val === 2) ? 'black' : 'white';
        ]]]
  state:
    - font-size: 11px
    - font-weight: bold
    - color: |
        [[[
          const s = entity.state;
          if (!s || s === '0' || s === 'unknown' || s === 'unavailable') 
            return 'var(--primary-text-color)';
          const val = String(s).includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          return (val === 1 || val === 2) ? 'black' : 'white';
        ]]]

```



## Wetterwarnungen (Status-Icon)

```yaml

type: custom:button-card
entity: sensor.geoweather_warnungen
aspect_ratio: 1/1
show_name: false
show_label: true
label: |-
  [[[ 
    const anzahl = parseInt(entity.state);
    const warnings = entity.attributes.warnungen;
    if (isNaN(anzahl) || anzahl === 0 || !warnings || warnings.length === 0) return 'Alles ok';
    return warnings[0].ereignis; 
  ]]]
icon: mdi:shield-check
size: 45%
state:
  - operator: template
    value: |-
      [[[ 
        const warnings = entity.attributes.warnungen;
        return warnings && warnings.length > 0 && parseInt(warnings[0].schwere_level) >= 3;
      ]]]
    styles:
      icon:
        - animation: blink 2s ease-in-out infinite
      label:
        - animation: blink 2s ease-in-out infinite
styles:
  grid:
    - grid-template-areas: "\"i\" \"l\" \"s\""
    - grid-template-rows: 1fr auto min-content
  card:
    - padding: 5px
    - background-color: |-
        [[[ 
          const warnings = entity.attributes.warnungen;
          if (!warnings || warnings.length === 0) return 'var(--card-background-color)';
          const level = parseInt(warnings[0].schwere_level);
          if (level <= 1) return '#ffeb3b'; // Gelb
          if (level === 2) return '#fb8c00'; // Orange
          if (level === 3) return '#e53935'; // Rot
          if (level >= 4) return '#880e4f';  // Violett
          return 'var(--card-background-color)';
        ]]]
  icon:
    - color: |-
        [[[ 
          const warnings = entity.attributes.warnungen;
          if (!warnings || warnings.length === 0) return '#c5e566';
          const level = parseInt(warnings[0].schwere_level);
          return (level <= 2) ? 'black' : 'white'; 
        ]]]
  label:
    - font-size: 10px
    - font-weight: bold
    - color: |-
        [[[ 
          const warnings = entity.attributes.warnungen;
          if (!warnings || warnings.length === 0) return 'var(--primary-text-color)';
          const level = parseInt(warnings[0].schwere_level);
          return (level <= 2) ? 'black' : 'white'; 
        ]]]
```


## Warnungs-Details (Markdown-Liste)

```yaml
type: markdown
content: |
  {% set warnungen = state_attr('sensor.geoweather_warnungen', 'warnungen') %}
  {% if warnungen %}
    {% for w in warnungen %}
    ### ⚠️ {{ w.ereignis }}
    **{{ w.headline }}**
    *🕒 {{ as_timestamp(w.beginn) | timestamp_custom('%H:%M') }} - {{ as_timestamp(w.ende) | timestamp_custom('%H:%M Uhr') }}*
    > {{ w.beschreibung }}
    ---
    {% endfor %}
  {% else %}
    *Aktuell liegen keine Warnmeldungen vor.*
  {% endif %}
```

## Regenvorhersage (Mushroom Style)
```yaml
type: custom:mushroom-template-card
entity: sensor.geoweather_regenvorhersage
icon: mdi:weather-rainy
icon_color: |-
  {% if states(entity) | float(0) > 0 %} blue {% else %} grey {% endif %}
primary: |2-
  {% set next_start = state_attr(entity, 'next_start') %}
  {% set next_end = state_attr(entity, 'next_end') %}
  {% set next_length = state_attr(entity, 'next_length_min') %}
  {% if next_start is not none %}
    {% set start_ts = next_start | as_timestamp(0) %}
    {% set now_ts = now() | as_timestamp %}
    {% if (start_ts > now_ts) %}
      In {{ ((start_ts - now_ts) / 60) | int }} Min. Regen für {{ next_length }} Min.
    {% elif (next_end is not none) %}
      Regen noch für {{ ((as_timestamp(next_end) - now_ts) / 60) | int }} Min.
    {% else %}
      Aktuell Dauerregen.
    {% endif %}
  {% else %}
    Kein Regen in Sicht.
  {% endif %}
card_mod:
  style: |
    ha-card {
      background-image: linear-gradient(90deg{% set forecast = state_attr(config.entity, 'forecast') %}{% if forecast %}{% set duration = forecast.keys() | last | as_timestamp - now() | as_timestamp %}{% for x, y in forecast.items() %}{% set pos = ((x | as_timestamp - now() | as_timestamp)/duration*100) | round %}{% set alpha = 0.5 if y > 0 else 0 %}{% if pos >= 0 %}, hsla(200, 100%, 50%, {{alpha}}) {{pos}}%{% endif %}{% endfor %}{% endif %});
    }
```

## Detaillierte Pollen-Übersicht (Grid)
```yaml
type: vertical-stack
cards:
  - type: grid
    columns: 3
    square: true
    cards:
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Birke
        icon: mdi:tree
        styles:
          icon:
            - color: |
                [[[
                  const v = entity.attributes.birke_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Gräser
        icon: mdi:grass
        styles:
          icon:
            - color: |
                [[[
                  const v = entity.attributes.graeser_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Roggen
        icon: mdi:barley
        styles:
          icon:
            - color: |
                [[[
                  const v = entity.attributes.roggen_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
  - type: custom:button-card
    entity: sensor.geoweather_pollenflug
    show_icon: false
    name: |
      [[[ return "Region: " + entity.attributes.dwd_teilregion ]]]
    styles:
      card:
        - background: none
        - border: none
        - box-shadow: none
        - padding: 5px
      name:
        - font-size: 14px
        - font-style: italic
        - opacity: 0.7
```

---

## Credits

DWD-Daten via [DWD OpenData](https://opendata.dwd.de). [Copyright](https://www.dwd.de/DE/service/rechtliche_hinweise/rechtliche_hinweise.html)

Inspiriert von:
- [DWD Pollenflug](https://github.com/mampfes/hacs_dwd_pollenflug)
- [DWD Precipitation Forecast](https://github.com/stoppegp/ha-dwd-precipitation-forecast)
- [DWD Weather](https://github.com/FL550/dwd_weather)
- [hass-geolocator](https://github.com/SmartyVan/hass-geolocator)
