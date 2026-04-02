"""GeoWeather – main setup v2.3.0."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

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

    # 4. Standard-Service registrieren (Update Alles)
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE):
        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE, coordinator.async_service_update
        )

    # 5. NEU in v2.3.0: Spezieller Pollen-Force Service
    async def handle_force_pollen(call: ServiceCall):
        """Service to bypass all timers and update pollen immediately."""
        _LOGGER.info("GeoWeather: Manueller Pollen-Update-Service aufgerufen.")
        coordinator._force_pollen_update = True
        await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, "update_pollen_now", handle_force_pollen)

    # 6. Plattformen (Sensor, etc.) laden
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # 7. Listener für Konfigurationsänderungen
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Services nur entfernen, wenn keine Instanz mehr aktiv ist
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_UPDATE)
            hass.services.async_remove(DOMAIN, "update_pollen_now")
            
    return unload_ok
