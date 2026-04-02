<img src="/logo/icon.png" alt="GeoWeather Logo" width="150">

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
- 🌿 **Pollenflug-Vorhersage:** NEU: Jetzt mit Vorhersage für **Heute / Morgen / Übermorgen**
- 🌧️ **Regenvorhersage:** Aktuelle Niederschlagsintensität + Forecast via DWD Radar
- 🚀 **Zero-Config:** Das Pollen-Region-Mapping ist nun fest integriert

🚐 **Warum GeoWeather? (Die Mission)**
Die meisten Wetter-Integrationen in Home Assistant sind für stationäre Häuser entwickelt. Wer jedoch mit dem Wohnmobil oder Camper reist, stößt schnell an Grenzen:

- Das GPS-Dilemma: Der Deutsche Wetterdienst (DWD) liefert Daten nicht direkt per Breitengrad/Längengrad. Er benötigt spezifische Warnzellen-IDs (für Wetter) und Region-IDs (für Pollen). GeoWeather erledigt diese komplexe "Übersetzung" im Hintergrund vollautomatisch bei jedem Stopp.
- Daten-Hygiene: Ständiges Abfragen von Wetterdaten während der Fahrt verbraucht unnötig mobiles Datenvolumen und CPU-Last. GeoWeather pausiert intelligent, solange du dich bewegst.
- Ankunfts-Logik: Was bringt dir die Pollenwarnung von vor 200 km? GeoWeather wartet mit dem Update, bis du wirklich an deinem Ziel angekommen bist (Arrival Delay).

GeoWeather wurde genau für diese Lücke entwickelt. Als Vorbilder dienten die großartigen Arbeiten der unten genannten Projekte, deren Logik ich für den mobilen Einsatz adaptiert und erweitert habe.

---
Wenn dir die integration gefällt, gib mir bitte einen Stern bei [github](https://github.com/hflocki/geoweather)



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
Starte Home Assistant neu

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
| **Arrival Delay** | ➖ | Wartezeit in Minuten nach Ankunft vor dem ersten Update (0-60). |

* bei einem Update-Intervall von 0 (Manuell) , werden Daten nur geladen, wenn der Service (die Action) aufgerufen wird.

---

## 📡 Entitäten

Alle Entitäten werden unter einem gemeinsamen **GeoWeather-Gerät** gruppiert, um die Übersicht zu behalten.

| Entität | State (Zustand) | Beschreibung |
|:---|:---|:---|
| `sensor.geoweather_standort` | Gemeindename | Liefert Kreis, Bundesland und WarnCellID in den Attributen. |
| `sensor.geoweather_warnungen` | Anzahl (Int) | Anzahl aktiver Warnungen. Details in den Attributen. |
| `sensor.geoweather_pollen_...` | Index (0-3) | **9 Einzelsensoren** (Birke, Gräser, etc.) mit Vorhersage-Attributen. |
| `sensor.geoweather_pollenbelastung_gesamt` | Höchste Stufe | Aktueller Belastungsindex inkl. DWD-Region-Info. |
| `sensor.geoweather_niederschlag_aktuell` |	mm/h	| Aktuelle Regenintensität direkt an deiner GPS-Position. |
| `sensor.geoweather_wind_warnstatus`| km/h | Zeigt Wind-Events (Sturm/Böen) & max. km/h aus DWD-Texten. |
| `sensor.geoweather_regenvorhersage`	| Startzeit	| Wann der nächste Regen beginnt (inkl. Radar-Forecast-Map). |
| `binary_sensor.geoweather_moving` | `on` / `off` | `on` = Fahrt erkannt (Updates pausiert zum Ressourcenschutz) |
| `sensor.geoweather_api_call_intervall` | Minuten | Zeigt das aktuell konfigurierte Abruf-Intervall an. |


Ab Version 2.0.0 liefert jeder Pollensensor (`sensor.geoweather_pollen_*`) folgende Attribute:
- **today**: Belastung heute (entspricht dem State).
- **tomorrow**: Belastung für morgen.
- **dayafter_to**: Belastung für übermorgen.

Ab Version v2.3.0
- Arrival Delay: Wetter-Updates erst X Minuten nach Ankunft.
- Smart Pollen Logic: Trennung von Wetter- und Pollenintervallen.

---

## 🛠 Dienste (Actions)

### `geoweather.update`
Aktualisiert Standort, Warnungen und Radar. Pollen werden nur mitgeladen, wenn das tägliche Zeitfenster (ab 12:00 Uhr) erreicht oder der Ort gewechselt wurde.

### `geoweather.update_pollen_now`
Erzwingt ein sofortiges Update der Pollendaten, unabhängig von Zeitregeln oder Standzeit.

> **Intelligente Sperren:** Beide Dienste werden nur ausgeführt, wenn das Fahrzeug **steht** und ein **gültiger GPS-Fix** vorliegt.
---

## 🌸 Pollenflug-Belastungsstufen (DWD)

| Wert | Bedeutung | Beschreibung |
|:---:|:---|:---|
| 0.0 | Keine | Keine Belastung nachweisbar. |
| 0.5 | Keine bis gering | Erste Pollen messbar. |
| 1.0 | Gering | Leicht erhöhte Konzentration. |
| 1.5 | Gering bis mittel | Spürbare Belastung. |
| 2.0 | Mittel | Deutliche Symptome. |
| 2.5 | Mittel bis hoch | Starke Belastung. |
| 3.0 | Stark | Maximale Warnstufe. |

---

## 🤖 Automatisierung & Dashboard
Detaillierte Beispiele für den Camper-Betrieb (Update-Trigger) und schicke Dashboard-Karten findest du hier:

👉 [ha_examples.yaml](https://github.com/hflocki/geoweather/blob/main/ha_examples.yaml)

---

## 🗺 Pollen Region Mapping

Über 430 Regionen sind integriert. Falls dein Standort fehlt (Log: "Kein ID-Mapping gefunden"), kannst du ihn manuell in der `mapping.py` ergänzen und uns als Issue melden.

---
## Credits

DWD-Daten via [DWD OpenData](https://opendata.dwd.de). [Copyright](https://www.dwd.de/DE/service/rechtliche_hinweise/rechtliche_hinweise.html)

Inspiriert von:
- [DWD Pollenflug](https://github.com/mampfes/hacs_dwd_pollenflug)
- [DWD Precipitation Forecast](https://github.com/stoppegp/ha-dwd-precipitation-forecast)
- [DWD Weather](https://github.com/FL550/dwd_weather)
- [hass-geolocator](https://github.com/SmartyVan/hass-geolocator)
