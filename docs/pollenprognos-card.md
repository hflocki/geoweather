# 🌸 Einbindung in die Pollenprognos-Card

Die beliebte Custom-Card [pollenprognos-card](https://github.com/daltonfury42/pollenprognos-card) sucht im `dwd`-Modus fest nach spezifischen Entitäts-IDs der offiziellen DWD-Integration (`sensor.pollenflug_<pollenart>_<region_id>`).

Da **GeoWeather** dynamisch und für den mobilen Einsatz ausgelegt ist, heißen die Quellsensoren `sensor.geoweather_pollen_*`. Mit einem kleinen Template-Mapping in Home Assistant kannst du die Karte dennoch nahtlos nutzen!

---

## 1. Template-Sensoren in Home Assistant anlegen

Füge den folgenden Block in deine `templates.yaml` (oder unter `template:` in deine `configuration.yaml`) ein. Wir nutzen stellvertretend die Region-ID `11` (Berlin) als Platzhalter für die Karte.

> **Wichtig:** Verwende im Feld `name` und `object_id` zwingend **`Graeser`** (mit `ae`), damit Home Assistant die Entity-ID nicht fälschlicherweise als `..._graser_11` anlegt!

```yaml
# DWD Aliase für die Pollenprognos-Card (Region 11)
  - name: "Pollenflug-Gefahrenindex Pollenflug Birke 11"
    object_id: pollenflug_birke_11
    unique_id: geoweather_alias_pollen_birke_11
    state: "{{ states('sensor.geoweather_pollen_birke') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_birke', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_birke', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_birke', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_birke', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Graeser 11"
    object_id: pollenflug_graeser_11
    unique_id: geoweather_alias_pollen_graeser_11
    state: "{{ states('sensor.geoweather_pollen_graeser') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_graeser', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_graeser', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_graeser', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_graeser', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Roggen 11"
    object_id: pollenflug_roggen_11
    unique_id: geoweather_alias_pollen_roggen_11
    state: "{{ states('sensor.geoweather_pollen_roggen') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_roggen', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_roggen', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Erle 11"
    object_id: pollenflug_erle_11
    unique_id: geoweather_alias_pollen_erle_11
    state: "{{ states('sensor.geoweather_pollen_erle') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_erle', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_erle', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_erle', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_erle', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Hasel 11"
    object_id: pollenflug_hasel_11
    unique_id: geoweather_alias_pollen_hasel_11
    state: "{{ states('sensor.geoweather_pollen_hasel') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_hasel', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_hasel', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Esche 11"
    object_id: pollenflug_esche_11
    unique_id: geoweather_alias_pollen_esche_11
    state: "{{ states('sensor.geoweather_pollen_esche') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_esche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_esche', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_esche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_esche', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Beifuss 11"
    object_id: pollenflug_beifuss_11
    unique_id: geoweather_alias_pollen_beifuss_11
    state: "{{ states('sensor.geoweather_pollen_beifuss') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_beifuss', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_beifuss', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Ambrosia 11"
    object_id: pollenflug_ambrosia_11
    unique_id: geoweather_alias_pollen_ambrosia_11
    state: "{{ states('sensor.geoweather_pollen_ambrosia') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_ambrosia', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_ambrosia', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_in_2_days')) | int(0) }}"

  - name: "Pollenflug-Gefahrenindex Pollenflug Eiche 11"
    object_id: pollenflug_eiche_11
    unique_id: geoweather_alias_pollen_eiche_11
    state: "{{ states('sensor.geoweather_pollen_eiche') | int(0) }}"
    attributes:
      state_tomorrow: "{{ state_attr('sensor.geoweather_pollen_eiche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_tomorrow')) | int(0) }}"
      state_in_2_days: "{{ state_attr('sensor.geoweather_pollen_eiche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_in_2_days')) | int(0) }}"

```

```yaml

type: custom:pollenprognos-card
service: dwd
region_id: '11'
integration: dwd
allergens:
  - erle
  - ambrosia
  - esche
  - birke
  - hasel
  - graeser
  - beifuss
  - roggen
title: Pollenflug Camper
show_state: true
days_to_show: 2
minimal: false
minimal_gap: 35
icon_size: 48
text_size_ratio: 1
show_text_allergen: true
show_value_text: true
show_value_numeric: false
show_empty_days: false
sort: value_descending
date_locale: de
levels_colors:
  - '#FFE55A'
  - '#FFC84E'
  - '#FFA53F'
  - '#FF6E33'
  - '#FF6140'
  - '#FF001C'

```
