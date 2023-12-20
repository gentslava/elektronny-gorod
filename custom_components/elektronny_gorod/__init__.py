"""The Elektronny Gorod integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ElektronnyGorogDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.LOCK,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elektronny Gorod from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = ElektronnyGorogDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for entry that was configured via user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
