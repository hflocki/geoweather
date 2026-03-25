<img src="logo/icon.png" alt="GeoWeather Logo" width="150">

<div align="left">
  <h1>GeoWeather</h1>

  <p>
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom">
    <img src="https://img.shields.io/github/v/release/hflocki/geoweather" alt="Latest Release">
    <a href="https://www.home-assistant.io"><img src="https://img.shields.io/badge/Home%20Assistant-2023.6%2B-blue" alt="HA Version"></a>
    <a href="https://discord.gg/5JUWSw79Rq"><img src="https://img.shields.io/discord/1484194968385093746?color=5865F2&label=Join%20Discord&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

Eine benutzerdefinierte Home Assistant Integration, die die GPS-Koordinaten deines Fahrzeugs nutzt, um Live-Daten vom **Deutschen Wetterdienst (DWD)** abzurufen:

- 📍 **Aktueller Standort:** Gemeinde / Kreis / Bundesland / WarnCellID
- ⛈️ **Wetterwarnungen:** Aktive Warnungen mit Schweregrad, Typ und Zeitraum
- 🌿 **Pollenflug-Vorhersage:** Heute / Morgen / Übermorgen für 9 Pollenarten
- 🚗 **Fahrt-Erkennung:** Automatische Pausierung von API-Aufrufen während der Fahrt via GPS-Geschwindigkeitssensor

> **Philosophie:** Kein fester Abruf-Timer. Du kontrollierst, wann Daten abgerufen werden, indem du den Dienst `geoweather.update` über deine eigenen Automatisierungen aufrufst.

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

Funktioniert mit **jeder** GPS-Quelle: ESPHome, GPSd, MQTT-Tracker, Smartphone, etc.

---

## Entitäten

| Entität | Beschreibung |
|---|---|
| `sensor.geoweather_standort` | Aktuelle Gemeinde (Zustand) + Kreis, Bundesland, WarnCellID |
| `sensor.geoweather_dwd_warnungen` | Anzahl aktiver Warnungen (Zustand) + vollständige Liste in Attributen |
| `sensor.geoweather_pollenflug` | Höchste Belastung heute (Zustand) + alle 9 Arten × 3 Tage |
| `binary_sensor.geoweather_faehrt` | `on` = in Fahrt (Updates pausiert), `off` = Fahrzeug steht |

---

## Dienst: `geoweather.update`

Löst einen frischen Abruf aller DWD-Daten aus. Kann jederzeit sicher aufgerufen werden – wird automatisch übersprungen, wenn:
- Das Fahrzeug fährt (Geschwindigkeit > Schwellenwert)
- Der GPS-Fix unzureichend ist (Satelliten < Minimum)

---

## Pollenflug-Belastungsstufen

Die Integration liefert die präzisen Stufen des DWD. In Dashboards sollte bei Zwischenstufen (z.B. `1-2`) immer die höhere Warnfarbe gewählt werden.

| Wert | Bedeutung | Beschreibung |
|:---:|---|---|
| **0** | Keine | Keine Belastung nachweisbar. |
| **0-1** | Keine bis gering | Erste Pollen, meist symptomfrei. |
| **1** | Gering | Leicht erhöhte Konzentration. |
| **1-2** | Gering bis mittel | Spürbare Belastung für Allergiker. |
| **2** | Mittel | Deutliche Symptome. |
| **2-3** | Mittel bis hoch | Starke Belastung, Aufenthalt im Freien einschränken. |
| **3** | Stark | Maximale Warnstufe. |

---


## Pollen Region Mapping

Der DWD liefert Pollendaten nicht nach Kreisen, sondern nach Regionen (z.B. "Harz"). 

**Wichtig:** Damit die Zuordnung funktioniert, erstelle eine Datei namens `pollen_mapping.yaml` direkt in deinem Home Assistant `/config/` Ordner (nicht im Integration-Ordner!).

**Format der `pollen_mapping.yaml`:**
```yaml
"Dein Kreisname": "Offizieller DWD Regionsname"
"Landkreis Harz": "Harz"
"München": "Allgäu/Oberbayern/Bay. Wald"
```
---


### Beispiel Automatisierungen

```yaml
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
- alias: "GeoWeather – nach Positionswechsel"
  id: geoweather_position_change
  trigger:
    - platform: state
      entity_id: sensor.my_gps_latitude
  condition:
    # 1. Wir müssen stehen
    - condition: state
      entity_id: binary_sensor.geoweather_faehrt
      state: "off"
    # 2. Nur wenn sich der Wert wirklich geändert hat (nicht nur Zeitstempel)
    - condition: template
      value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    # 3. Optional: Nur wenn die Änderung groß genug ist (ca. 1km = 0.01 Grad)
    - condition: template
      value_template: "{{ (trigger.from_state.state | float - trigger.to_state.state | float) | abs > 0.01 }}"
  action:
    - service: geoweather.update
      data: {}
```
---


### Beispiel Dashboard Karte - Warnungen


```yaml
type: custom:button-card
entity: sensor.warnungen
aspect_ratio: 1/1
show_name: false
show_label: true
label: |-
  [[[ 
    const anzahl = parseInt(entity.state);
    const warnings = entity.attributes.warnungen;
    if (isNaN(anzahl) || anzahl === 0 || !warnings || warnings.length === 0) return 'Alles ok';
    // Zeige das Ereignis der ersten Warnung (z.B. Frost)
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
          // Farbskala basierend auf schwere_level
          if (level <= 1) return '#ffeb3b'; // Gelb (Minor)
          if (level === 2) return '#fb8c00'; // Orange (Moderate)
          if (level === 3) return '#e53935'; // Rot (Severe)
          if (level >= 4) return '#880e4f';  // Violett (Extreme)
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
    - justify-self: center
    - text-wrap: wrap
    - color: |-
        [[[ 
          const warnings = entity.attributes.warnungen;
          if (!warnings || warnings.length === 0) return 'var(--primary-text-color)';
          const level = parseInt(warnings[0].schwere_level);
          return (level <= 2) ? 'black' : 'white'; 
        ]]]
  state:
    - font-size: 9px
    - color: var(--secondary-text-color)
    - justify-self: center

```

### Beispiel Dashboard Karte - Pollen Kachel


```yaml
type: custom:button-card
entity: sensor.pollenflug
aspect_ratio: 1/1
show_name: true
name: Pollenflug
show_state: true
state_display: |
  [[[
    const s = entity.state;
    if (s == '0')   return 'Keine';
    if (s == '0-1') return 'Keine bis gering';
    if (s == '1')   return 'Gering';
    if (s == '1-2') return 'Gering bis mittel';
    if (s == '2')   return 'Mittel';
    if (s == '2-3') return 'Mittel bis hoch';
    if (s == '3')   return 'Stark';
    return s;
  ]]]
styles:
  card:
    - padding: 5px
    - background-color: |
        [[[
          const s = entity.state;
          if (!s || s === 'unknown' || s === '0') return 'var(--card-background-color)';
          
          // Nimm bei "1-2" die 2, bei "2-3" die 3 für die Farbe
          const val = s.includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);

          if (val === 1) return '#ffeb3b'; // Gelb
          if (val === 2) return '#fb8c00'; // Orange
          if (val >= 3) return '#e53935'; // Rot
          return 'var(--card-background-color)';
        ]]]
  icon:
    - color: |
        [[[
          const s = entity.state;
          const val = s.includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          if (val === 0 || isNaN(val)) return '#c5e566';
          return (val >= 2) ? 'white' : 'black';
        ]]]
  name:
    - font-weight: bold
    - font-size: 12px
    - color: |
        [[[
          const s = entity.state;
          const val = s.includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          return (val >= 2) ? 'white' : 'var(--primary-text-color)';
        ]]]
  state:
    - font-size: 11px 
    - font-weight: bold
    - color: |
        [[[
          const s = entity.state;
          const val = s.includes('-') ? parseInt(s.split('-')[1]) : parseInt(s);
          return (val >= 2) ? 'white' : 'var(--primary-text-color)';
        ]]]
```

### Beispiel Dashboard Karte - Pollen Übersicht


```yaml
type: vertical-stack
cards:
  - type: vertical-stack
    cards:
      - type: grid
        columns: 3
        square: true
        cards:
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Birke
            icon: mdi:tree
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Gräser
            icon: mdi:grass
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Roggen
            icon: mdi:barley
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Erle
            icon: mdi:leaf
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Hasel
            icon: mdi:nut
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Esche
            icon: mdi:tree-outline
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Beifuß
            icon: mdi:sprout
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Ambrosia
            icon: mdi:flower-tulip
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
          - type: custom:button-card
            entity: sensor.pollenflug
            name: Eiche
            icon: mdi:tree-outline
            aspect_ratio: 1/1
            styles:
              card:
                - border-radius: 15px
                - padding: 10%
              grid:
                - grid-template-areas: "\"i\" \"n\""
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
                - justify-self: center
                - padding-top: 5px
  - type: custom:button-card
    entity: sensor.pollenflug
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


## Credits
DWD data via [DWD OpenData](https://opendata.dwd.de).
