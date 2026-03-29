"""GeoWeather – main setup."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SERVICE_UPDATE
from .coordinator import GeoWeatherCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GeoWeather from a config entry."""
    
    # 1. Coordinator Instanz erstellen
    coordinator = GeoWeatherCoordinator(hass, entry)
    
    # 2. Ersten Datenabruf beim Start ausführen
    await coordinator.async_config_entry_first_refresh()

    # 3. Coordinator global in hass.data speichern (für sensor.py)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 4. Service registrieren (falls noch nicht vorhanden)
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE):
        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE, coordinator.async_service_update
        )

    # 5. Plattformen (Sensor, etc.) laden
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # 6. Listener für Konfigurationsänderungen
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_UPDATE)
    return unload_ok
