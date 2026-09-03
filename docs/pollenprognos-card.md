# 🌸 Einbindung in die Pollenprognos-Card

Die beliebte Custom-Card [pollenprognos-card](https://github.com/daltonfury42/pollenprognos-card) sucht im `dwd`-Modus nach spezifischen Entitäts-IDs und Namen der offiziellen DWD-Integration (`sensor.pollenflug_gefahrenindex_pollenflug_<pollenart>_<region_id>`).

Da **GeoWeather** die Daten aus dem DWD intern auf einer erweiterten Skala von `0.0` bis `6.0` aufbereitet, die Dashboard-Karte jedoch zwingend die originale DWD-Skala (`0` bis `3`) erwartet, rechnen die nachfolgenden Templates die Werte automatisch für das Dashboard um.

---

## 🛠️ Skalenumrechnung

| GeoWeather Wert | DWD Stufe | Bedeutung |
|:---:|:---:|---|
| **0** | **0** | Keine Belastung |
| **1 – 2** | **1** | Geringe Belastung |
| **3 – 4** | **2** | Mittlere Belastung |
| **5 – 6** | **3** | Hohe Belastung |

---

## 1. Template-Sensoren in Home Assistant anlegen

Füge den folgenden Block in deine `templates.yaml` ein. Wir nutzen stellvertretend die Region-ID `11` (Berlin/Brandenburg) als Platzhalter.

```yaml
# ── DWD Pollenprognose Aliase (Region 11 - Exakte Namen & Skalenumrechnung) ──
    - name: "Pollenflug-Gefahrenindex Pollenflug Birke 11"
      unique_id: geoweather_alias_pollen_birke_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_birke', 'today') | default(states('sensor.geoweather_pollen_birke'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_birke', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_birke', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_birke', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_birke', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Graeser 11"
      unique_id: geoweather_alias_pollen_graeser_11
      state: >
        {% set v = states('sensor.geoweather_pollen_graser') | float(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_graser', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_graser', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_graser', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_graser', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
          
    - name: "Pollenflug-Gefahrenindex Pollenflug Roggen 11"
      unique_id: geoweather_alias_pollen_roggen_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_roggen', 'today') | default(states('sensor.geoweather_pollen_roggen'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_roggen', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_roggen', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Erle 11"
      unique_id: geoweather_alias_pollen_erle_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_erle', 'today') | default(states('sensor.geoweather_pollen_erle'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_erle', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_erle', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_erle', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_erle', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Hasel 11"
      unique_id: geoweather_alias_pollen_hasel_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_hasel', 'today') | default(states('sensor.geoweather_pollen_hasel'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_hasel', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_hasel', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Esche 11"
      unique_id: geoweather_alias_pollen_esche_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_esche', 'today') | default(states('sensor.geoweather_pollen_esche'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_esche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_esche', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_esche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_esche', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Beifuss 11"
      unique_id: geoweather_alias_pollen_beifuss_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'today') | default(states('sensor.geoweather_pollen_beifuss'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Ambrosia 11"
      unique_id: geoweather_alias_pollen_ambrosia_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'today') | default(states('sensor.geoweather_pollen_ambrosia'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Eiche 11"
      unique_id: geoweather_alias_pollen_eiche_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_eiche', 'today') | default(states('sensor.geoweather_pollen_eiche'), true) | float(0) %}
        {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_eiche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_tomorrow'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_eiche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_in_2_days'), true) | float(0) %}
          {{ 0 if v < 0.5 else 1 if v <= 2.5 else 2 if v <= 4.5 else 3 }}

```

## 2. Pollenprognosscard in Frontend Beispiel
```yaml
integration: dwd
region_id: '11'
entity_prefix: ''
entity_suffix: ''
allergens:
  - erle
  - ambrosia
  - esche
  - birke
  - hasel
  - graeser
  - beifuss
  - roggen
minimal: false
minimal_gap: 35
background_color: ''
icon_size: 48
text_size_ratio: 1
levels_colors:
  - '#FFE55A'
  - '#FFC84E'
  - '#FFA53F'
  - '#FF6E33'
  - '#FF6140'
  - '#FF001C'
levels_empty_color: '#17d214'
levels_thickness: 35
allergen_colors:
  - '#17d214'
  - '#FFE55A'
  - '#FFC84E'
  - '#FFA53F'
  - '#FF6E33'
  - '#FF6140'
  - '#FF001C'
icon_in_ring: true
show_text_allergen: true
show_value_text: true
show_value_numeric: false
show_value_numeric_in_circle: false
show_empty_days: false
debug: false
show_version: true
days_to_show: 2
days_relative: true
days_abbreviated: false
days_uppercase: false
days_boldfaced: false
pollen_threshold: 0.5
sort: value_descending
allergy_risk_top: true
allergens_abbreviated: true
date_locale: de
title: false
phrases:
  full: {}
  short: {}
  levels: []
  days: {}
  no_information: ''
type: custom:pollenprognos-card
service: dwd
show_state: true
allergen_outline_color: '#eff5ef'
allergen_color_mode: custom

```
