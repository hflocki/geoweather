<img src="logo/icon.png" alt="GeoWeather Logo" width="150">

<div align="left">
  <h1>GeoWeather for Home Assistant</h1>

  <p>
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom">
    <img src="https://img.shields.io/github/v/release/hflocki/geoweather" alt="Latest Release">
    <a href="https://www.home-assistant.io"><img src="https://img.shields.io/badge/Home%20Assistant-2023.6%2B-blue" alt="HA Version"></a>
    <a href="https://discord.gg/5JUWSw79Rq"><img src="https://img.shields.io/discord/1484194968385093746?color=5865F2&label=Join%20Discord&logo=discord&logoColor=white" alt="Discord"></a>
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
| `sensor.geoweather_standort` | Gemeindename | + Kreis, Bundesland, WarnCellID, GPS-Koordinaten |
| `sensor.geoweather_warnungen` | Anzahl (Integer) | + vollständige Warnliste in Attributen |
| `sensor.geoweather_pollenflug` | Höchste Stufe heute | + alle 9 Pollenarten × 3 Tage |
| `sensor.geoweather_regenvorhersage` | mm/h (aktuell) | + Forecast-Map, Regenstart/-ende |
| `binary_sensor.geoweather_faehrt` | `on`/`off` | `on` = fährt (Updates pausiert) |

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

```yaml
# Stündliche Aktualisierung während des Stillstands
- alias: "GeoWeather – periodisch aktualisieren"
  id: geoweather_periodic_update
  trigger:
    - platform: time_pattern
      hours: /1
    - platform: state
      entity_id: binary_sensor.geoweather_faehrt
      from: "on"
      to: "off"
  condition:
    - condition: state
      entity_id: binary_sensor.geoweather_faehrt
      state: "off"
  action:
    - service: geoweather.update
      data: {}
```

```yaml
# Update nach deutlicher Positionsänderung (~1 km)
- alias: "GeoWeather – nach Positionswechsel"
  id: geoweather_position_change
  trigger:
    - platform: state
      entity_id: sensor.mein_gps_latitude
  condition:
    - condition: state
      entity_id: binary_sensor.geoweather_faehrt
      state: "off"
    - condition: template
      value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    - condition: template
      value_template: "{{ (trigger.from_state.state | float - trigger.to_state.state | float) | abs > 0.01 }}"
  action:
    - service: geoweather.update
      data: {}
```

---

## Beispiel Dashboard – Warnungen

```yaml
type: custom:button-card
entity: sensor.geoweather_warnungen
aspect_ratio: 1/1
show_name: false
show_label: true
label: |
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
    value: |
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
    - grid-template-areas: '"i" "l" "s"'
    - grid-template-rows: 1fr auto min-content
```

Markdown-Karte für Warnungsdetails:

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

---

## Beispiel Dashboard – Pollen Übersicht

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
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - width: 80%
            - color: |
                [[[
                  const v = entity.attributes.birke_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Gräser
        icon: mdi:grass
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
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
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Roggen
        icon: mdi:barley
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
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
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Erle
        icon: mdi:leaf
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.erle_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Hasel
        icon: mdi:nut
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.hasel_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Esche
        icon: mdi:tree-outline
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.esche_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Beifuß
        icon: mdi:sprout
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.beifuss_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Ambrosia
        icon: mdi:flower-tulip
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.ambrosia_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
      - type: custom:button-card
        entity: sensor.geoweather_pollenflug
        name: Eiche
        icon: mdi:tree-outline
        aspect_ratio: 1/1
        styles:
          card:
            - border-radius: 15px
            - padding: 10%
          grid:
            - grid-template-areas: '"i" "n"'
            - grid-template-rows: 1fr min-content
          icon:
            - color: |
                [[[
                  const v = entity.attributes.eiche_heute;
                  if (v == '0') return '#4caf50';
                  if (v == '1' || v == '1-2') return '#ffeb3b';
                  if (v == '2' || v == '2-3') return '#fb8c00';
                  if (v == '3') return '#e53935';
                  return 'grey';
                ]]]
          name:
            - font-size: 13px
            - font-weight: bold
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
