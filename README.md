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

## ⚙️ Konfiguration

Während der Einrichtung in der Benutzeroberfläche wählst du deine GPS-Quellen aus. Die Integration ist extrem flexibel und funktioniert mit **jeder** GPS-Quelle (ESPHome, GPSd, MQTT-Tracker, Smartphone-App, etc.).

| Feld | Erforderlich | Beschreibung |
|:---|:---:|:---|
| **Latitude Sensor** | ✅ | z.B. `sensor.phone_latitude` |
| **Longitude Sensor** | ✅ | z.B. `sensor.phone_longitude` |
| **Speed Sensor** | ✅ | km/h – wird für die Erkennung von "Moving" genutzt. |
| **Altitude Sensor** | ➖ | Optional – für die Anzeige der Meereshöhe. |
| **Satellites Sensor** | ➖ | Optional – zur Prüfung der GPS-Fix-Qualität. |
| **Speed Threshold** | ➖ | Standard: `5.0` km/h – darüber gilt das Fahrzeug als fahrend. |
| **Min. Satellites** | ➖ | Standard: `4` – darunter wird ein Update zum Schutz vor Fehlpositionen übersprungen. |
| **Update Interval** | ➖ | Automatisches Polling in Minuten (Standard `30`). `0` deaktiviert das automatische Update * |

* bei einem Update-Intervall von 0 (Manuell) , werden Daten nur geladen, wenn der Service (die Action) aufgerufen wird.

---

## 📡 Entitäten

Alle Entitäten werden unter einem gemeinsamen **GeoWeather-Gerät** gruppiert, um die Übersicht zu behalten.

| Entität | State (Zustand) | Beschreibung |
|:---|:---|:---|
| `sensor.geoweather_standort` | Gemeindename | Liefert Kreis, Bundesland und WarnCellID in den Attributen. |
| `sensor.geoweather_warnungen` | Anzahl (Int) | Anzahl aktiver Warnungen. Details (Event, Level, Beschreibung) in den Attributen. |
| `sensor.geoweather_pollenflug` | Höchste Stufe | Aktueller Belastungsindex. Alle 8 Pollenarten sind als Attribute verfügbar. |
| `sensor.geoweather_regenvorhersage` | mm/h | Aktuelle Regenrate. Inklusive 2h-Forecast-Map und Regenstart/-ende. |
| `binary_sensor.geoweather_moving` | `on` / `off` | `on` = Fahrt erkannt (Updates pausiert) |
| `sensor.geoweather_api_call_intervall` | Minuten | Zeigt das aktuell konfigurierte Abruf-Intervall an. |

> **Pro-Tipp:** Der Warnungen-Sensor liefert eine Ganzzahl. Du kannst ihn im Dashboard einfach mit einem Badge versehen oder Automationen triggern, wenn `state > 0`.

---

## 🛠 Dienst: `geoweather.update`

Dieser Dienst löst einen frischen Abruf aller DWD-Daten (Standort, Warnungen, Pollen, Radar) aus. 

**Intelligente Sperren:**
Der Dienst führt den Abruf nur aus, wenn:
1. Das Fahrzeug **steht** (Geschwindigkeit unter dem Schwellenwert).
2. Ein **gültiger GPS-Fix** vorliegt (sofern ein Satelliten-Sensor konfiguriert ist).

Da die Mindest-Standzeit nun flexibel über Home Assistant Automatisierungen gesteuert wird (siehe `DASHBOARD.md`), reagiert dieser Dienst sofort, wenn er aufgerufen wird.

---

## 🌸 Pollenflug-Belastungsstufen

Die Integration liefert die offiziellen DWD-Grenzwerte. Für Dashboards empfehlen wir, bei Zwischenstufen (z.B. `1-2`) immer die Farbe der höheren Stufe zu wählen.

| Wert | Bedeutung | Beschreibung |
|:---:|:---|:---|
| 0.0 | Keine | Keine Belastung nachweisbar. |
| 0.5 | Keine bis gering | (Früher 0-1) Erste Pollen messbar. |
| 1.0 | Gering | Leicht erhöhte Konzentration. |
| 1.5 | Gering bis mittel | (Früher 1-2) Spürbare Belastung. |
| 2.0 | Mittel | Deutliche Symptome. |
| 2.5 | Mittel bis hoch | (Früher 2-3) Starke Belastung. |
| 3.0 | Stark | Maximale Warnstufe. |

---

## 🗺 Pollen Region Mapping

Da der DWD Pollendaten nach meteorologischen Regionen (z.B. "Rhein.-Westfäl. Tiefland") und nicht nach exakten Kreisen bereitstellt, nutzt GeoWeather ein Mapping. 
Sollte dein Kreis nicht automatisch erkannt werden, kannst du eine `pollen_mapping.yaml` im `/config/` Ordner anlegen:

```yaml
"Landkreis Harz": "Harz"
"Wermelskirchen": "Rhein.-Westfäl. Tiefland"
"München": "Allgäu/Oberbayern/Bay. Wald"
```
---

## 🤖 Empfohlene Automatisierungen

Da die Integration im fahrbereiten Zustand (Moving = ON) keine Daten abruft, um Ressourcen zu sparen, werden Automatisierungen genutzt, um Updates im Stand zu steuern.

## Periodisches Update & Sofort-Update bei Stop
Diese Automatisierung sorgt dafür, dass die Daten jede Stunde aktualisiert werden, sofern der Camper steht. Zusätzlich triggert sie sofort, wenn die Fahrt beendet wird.

```yaml
alias: "GeoWeather: Periodisches Update & Stop-Trigger"
description: "Aktualisiert Daten stündlich und sofort beim Anhalten."
id: geoweather_periodic_update
trigger:
  - platform: time_pattern
    hours: "/1"
  - platform: state
    entity_id: binary_sensor.geoweather_moving
    from: "on"
    to: "off"
condition:
  - condition: state
    entity_id: binary_sensor.geoweather_moving
    state: "off"
action:
  - action: geoweather.update
    data: {}
mode: skip

```
---

## Update nach Ankunft (Stabilisierungs-Sperre)
Diese Automatisierung wartet, bis der Camper für 10 Minuten steht. Dies ist ideal, um sicherzustellen, dass man wirklich am Ziel angekommen ist und nicht nur an einer Ampel oder im Stau steht, bevor die Wetterdaten für den neuen Standort geladen werden.

```yaml
alias: "GeoWeather: Update nach Ankunft (10 Min)"
description: "Aktualisiert Wetterdaten, wenn der Camper für 10 Minuten steht."
id: geoweather_position_change
trigger:
  - platform: state
    entity_id: binary_sensor.geoweather_moving
    from: "on"
    to: "off"
    for:
      minutes: 10
condition:
  - condition: state
    entity_id: binary_sensor.geoweather_moving
    state: "off"
action:
  - action: geoweather.update
    data: {}
mode: restart

```

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
entity: sensor.geoweather_pollenbelastung_gesamt
aspect_ratio: 1/1
show_name: true
name: Pollenflug
show_state: true
state_display: |
  [[[
    const s = parseFloat(entity.state);
    if (isNaN(s)) return 'Lade...';
    if (s === 0)   return 'Keine';
    if (s <= 0.5) return 'Sehr gering';
    if (s <= 1.5) return 'Gering';
    if (s <= 2.5) return 'Mittel';
    if (s > 2.5)  return 'Stark';
    return s;
  ]]]
styles:
  card:
    - padding: 5px
    - background-color: |
        [[[
          const val = parseFloat(entity.state);
          if (isNaN(val) || val === 0) return 'var(--card-background-color)';
          if (val <= 1.5) return '#ffeb3b'; // Gelb
          if (val <= 2.5) return '#fb8c00'; // Orange
          if (val > 2.5)  return '#e53935'; // Rot
          return 'var(--card-background-color)';
        ]]]
  icon:
    - color: |
        [[[
          const val = parseFloat(entity.state);
          if (isNaN(val) || val === 0) return '#c5e566';
          return (val <= 2.5) ? 'black' : 'white';
        ]]]
  name:
    - font-weight: bold
    - font-size: 12px
    - color: |
        [[[
          const val = parseFloat(entity.state);
          if (isNaN(val) || val === 0) return 'var(--primary-text-color)';
          return (val <= 2.5) ? 'black' : 'white';
        ]]]
  state:
    - font-size: 11px
    - font-weight: bold
    - color: |
        [[[
          const val = parseFloat(entity.state);
          if (isNaN(val) || val === 0) return 'var(--primary-text-color)';
          return (val <= 2.5) ? 'black' : 'white';
        ]]]

```

## Wetterwarnungen (Status-Icon)

```yaml
type: custom:button-card
entity: sensor.geoweather_wetterwarnungen_anzahl
aspect_ratio: 1/1
show_name: false
show_label: true
label: |-
  [[[ 
    const anzahl = parseInt(entity.state);
    const warnings = entity.attributes.aktive_warnungen;
    if (isNaN(anzahl) || anzahl === 0 || !warnings || warnings.length === 0) return 'Alles ok';
    return warnings[0].ereignis; 
  ]]]
icon: |-
  [[[
    const anzahl = parseInt(entity.state);
    return (anzahl > 0) ? 'mdi:alert-decagram' : 'mdi:shield-check';
  ]]]
size: 45%
styles:
  grid:
    - grid-template-areas: "\"i\" \"l\" \"s\""
    - grid-template-rows: 1fr auto min-content
  card:
    - padding: 5px
    - background-color: |-
        [[[ 
          const warnings = entity.attributes.aktive_warnungen;
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
          const warnings = entity.attributes.aktive_warnungen;
          if (!warnings || warnings.length === 0) return '#c5e566';
          const level = parseInt(warnings[0].schwere_level);
          return (level <= 2) ? 'black' : 'white'; 
        ]]]
    - animation: |-
        [[[
          const warnings = entity.attributes.aktive_warnungen;
          return (warnings && warnings.length > 0 && parseInt(warnings[0].schwere_level) >= 2) 
            ? 'blink 2s ease-in-out infinite' 
            : 'none';
        ]]]
  label:
    - font-size: 10px
    - font-weight: bold
    - justify-self: center
    - text-wrap: wrap
    - color: |-
        [[[ 
          const warnings = entity.attributes.aktive_warnungen;
          if (!warnings || warnings.length === 0) return 'var(--primary-text-color)';
          const level = parseInt(warnings[0].schwere_level);
          return (level <= 2) ? 'black' : 'white'; 
        ]]]
```


## Warnungs-Details (Markdown-Liste)

```yaml
type: markdown
content: |
  {% set warnungen = state_attr('sensor.geoweather_wetterwarnungen_anzahl', 'aktive_warnungen') %}
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
primary: |
  {% if states('sensor.geoweather_regenvorhersage') == 'Kein Regen' %}
    Alles trocken
  {% else %}
    Regen ab {{ states('sensor.geoweather_regenvorhersage') }}
  {% endif %}
secondary: |
  {% set mm = state_attr('sensor.geoweather_regenvorhersage', 'next_sum_mm') | float(0) %}
  {% if mm > 0 %}
    Menge: {{ mm }} mm | Dauer: {{ state_attr('sensor.geoweather_regenvorhersage', 'next_length_min') }} min
  {% else %}
    Intensität: {{ states('sensor.geoweather_niederschlag_aktuell') }} mm/h
  {% endif %}
icon: mdi:weather-pouring
icon_color: |-
  {% if states('sensor.geoweather_regenvorhersage') == 'Kein Regen' %}
    disabled
  {% else %}
    blue
  {% endif %}
entity: sensor.geoweather_regenvorhersage
tap_action:
  action: more-info

```

## Visualisierung der Regenvorhersage (2h Nowcasting)
Für die Darstellung müssen folgende Frontend-Erweiterungen über HACS installiert sein: `ApexCharts Card`

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Regenvorhersage (Nächste 2 Stunden)
  show_states: true
  colorize_states: true
graph_span: 2h
span:
  start: minute
apex_config:
  chart:
    height: 200px
  fill:
    type: gradient
    gradient:
      shadeIntensity: 1
      opacityFrom: 0.7
      opacityTo: 0.2
      stops: [0, 90, 100]
  yaxis:
    decimalsInFloat: 1
    labels:
      style:
        colors: 'var(--secondary-text-color)'
series:
  - entity: sensor.geoweather_regenvorhersage
    name: Intensität
    unit: mm/h
    data_generator: |
      const forecast = entity.attributes.forecast;
      if (!forecast) return [];
      return Object.entries(forecast).map(([time, value]) => {
        return [new Date(time).getTime(), value];
      });
    type: area
    color: '#03a9f4'
    curve: smooth
    stroke_width: 2
    fill_raw: 'null'
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
        template: pollen_style
        entity: sensor.geoweather_pollen_birke
        name: Birke
        icon: mdi:tree
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_graeser
        name: Gräser
        icon: mdi:grass
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_roggen
        name: Roggen
        icon: mdi:barley
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_erle
        name: Erle
        icon: mdi:leaf
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_hasel
        name: Hasel
        icon: mdi:nut
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_esche
        name: Esche
        icon: mdi:tree-outline
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_beifuss
        name: Beifuß
        icon: mdi:sprout
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_ambrosia
        name: Ambrosia
        icon: mdi:flower-tulip
      - type: custom:button-card
        template: pollen_style
        entity: sensor.geoweather_pollen_eiche
        name: Eiche
        icon: mdi:tree-outline
  - type: custom:button-card
    entity: sensor.geoweather_pollenbelastung_gesamt
    show_icon: false
    name: |
      [[[ 
        if (!entity || !entity.attributes) return "Lade Daten...";
        const id = entity.attributes.dwd_region_id || '??';
        const region = entity.attributes.dwd_teilregion || 'Unbekannt';
        const kreis = entity.attributes.kreis || 'Standort wird ermittelt...';
        return "Kreis: " + kreis + "<br><small>DWD ID " + id + ": " + region + "</small>";
      ]]]
    styles:
      card:
        - border-top: 1px solid rgba(255,255,255,0.1)
        - margin-top: 5px
        - background: none
      name:
        - font-size: 11px
        - font-style: italic
        - opacity: 0.8
        - text-align: center


```

##Beispiel für Kacheln als Pollenraster (Einfügen unter Raw-Konfigurationseditor oberhalb von views: )
```yaml
button_card_templates:
  pollen_style: 
    aspect_ratio: 1/1
    show_state: false
    show_label: true
    styles:
      card:
        - border-radius: 12px
        - padding: 5px
      grid:
        - grid-template-areas: '"i" "n" "l"'
        - grid-template-rows: 1fr min-content min-content
      icon:
        - width: 55%
        - color: |
            [[[
              const v = parseFloat(entity.state);
              if (isNaN(v) || v === 0) return 'rgba(255,255,255,0.2)';
              if (v <= 1) return '#c5e566'; // Sehr gering
              if (v <= 2) return '#ffeb3b'; // Gering
              if (v <= 3) return '#fdd835'; // Gering-Mittel
              if (v <= 4) return '#fb8c00'; // Mittel
              if (v <= 5) return '#ff7043'; // Mittel-Stark
              return '#e53935';             // Stark
            ]]]
      name:
        - font-size: 11px
        - font-weight: bold
      label:
        - font-size: 10px
        - opacity: 0.9
        - justify-self: center
    label: |
      [[[
        const h = entity.state;
        const m = (entity.attributes && entity.attributes.tomorrow !== undefined) ? entity.attributes.tomorrow : '?';
        return "H: " + h + " | M: " + m;
      ]]]
```
---

## Credits

DWD-Daten via [DWD OpenData](https://opendata.dwd.de). [Copyright](https://www.dwd.de/DE/service/rechtliche_hinweise/rechtliche_hinweise.html)

Inspiriert von:
- [DWD Pollenflug](https://github.com/mampfes/hacs_dwd_pollenflug)
- [DWD Precipitation Forecast](https://github.com/stoppegp/ha-dwd-precipitation-forecast)
- [DWD Weather](https://github.com/FL550/dwd_weather)
- [hass-geolocator](https://github.com/SmartyVan/hass-geolocator)
