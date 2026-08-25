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

> **Wichtig:** Achte darauf, dass dieser Block eingerückt unter der Kategorie `- sensor:` in deiner `templates.yaml` steht!

```yaml
# ── DWD Pollenprognos-Card Aliase (Region 11 - Exakte Namen & Skalenumrechnung) ──
- sensor:
    - name: "Pollenflug-Gefahrenindex Pollenflug Birke 11"
      unique_id: geoweather_alias_pollen_birke_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_birke', 'today') | default(states('sensor.geoweather_pollen_birke')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_birke', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_birke', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_birke', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_birke', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Graeser 11"
      unique_id: geoweather_alias_pollen_graeser_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_graeser', 'today') | default(states('sensor.geoweather_pollen_graeser')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_graeser', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_graeser', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_graeser', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_graeser', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Roggen 11"
      unique_id: geoweather_alias_pollen_roggen_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_roggen', 'today') | default(states('sensor.geoweather_pollen_roggen')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_roggen', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_roggen', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_roggen', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Erle 11"
      unique_id: geoweather_alias_pollen_erle_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_erle', 'today') | default(states('sensor.geoweather_pollen_erle')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_erle', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_erle', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_erle', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_erle', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Hasel 11"
      unique_id: geoweather_alias_pollen_hasel_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_hasel', 'today') | default(states('sensor.geoweather_pollen_hasel')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_hasel', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_hasel', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_hasel', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Esche 11"
      unique_id: geoweather_alias_pollen_esche_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_esche', 'today') | default(states('sensor.geoweather_pollen_esche')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_esche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_esche', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_esche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_esche', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Beifuss 11"
      unique_id: geoweather_alias_pollen_beifuss_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'today') | default(states('sensor.geoweather_pollen_beifuss')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_beifuss', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_beifuss', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Ambrosia 11"
      unique_id: geoweather_alias_pollen_ambrosia_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'today') | default(states('sensor.geoweather_pollen_ambrosia')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_ambrosia', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_ambrosia', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}

    - name: "Pollenflug-Gefahrenindex Pollenflug Eiche 11"
      unique_id: geoweather_alias_pollen_eiche_11
      state: >
        {% set v = state_attr('sensor.geoweather_pollen_eiche', 'today') | default(states('sensor.geoweather_pollen_eiche')) | int(0) %}
        {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
      attributes:
        state_tomorrow: >
          {% set v = state_attr('sensor.geoweather_pollen_eiche', 'tomorrow') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_tomorrow')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
        state_in_2_days: >
          {% set v = state_attr('sensor.geoweather_pollen_eiche', 'dayafter_to') | default(state_attr('sensor.geoweather_pollen_eiche', 'state_in_2_days')) | int(0) %}
          {{ 0 if v == 0 else 1 if v <= 2 else 2 if v <= 4 else 3 }}
