"""Janitza Modbus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import JanitzaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

JanitzaConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Set up Janitza Modbus from a config entry."""
    coordinator = JanitzaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Unload a Janitza Modbus config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_close()

    return unload_ok
