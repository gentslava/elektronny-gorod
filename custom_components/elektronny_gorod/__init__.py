"""The Elektronny Gorod integration."""

from __future__ import annotations
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    LOGGER,
    CONF_OPERATOR_ID,
    CONF_USER_AGENT,
)
from .coordinator import ElektronnyGorodUpdateCoordinator
from .user_agent import UserAgent

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.LOCK,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elektronny Gorod from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    version = config_entry.version
    new_data: ConfigType = {**config_entry.data}
    options: ConfigType = {**config_entry.options}

    LOGGER.debug(f"Migrating from version {version}")

    if config_entry.version == 1:
        user_agent = UserAgent()
        user_agent.operator_id = new_data[CONF_OPERATOR_ID]
        new_data[CONF_USER_AGENT] = json.dumps(user_agent.json())

        version = 2
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options, version=version
        )
        LOGGER.debug(f"Migration to version {version} successful")

    LOGGER.debug(f"Migration to config version {config_entry.version} successful")

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for entry that was configured via user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
