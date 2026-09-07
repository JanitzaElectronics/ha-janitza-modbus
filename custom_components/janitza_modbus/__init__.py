"""Janitza Modbus integration."""

from __future__ import annotations

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import JanitzaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

JanitzaConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Set up Janitza Modbus from a config entry."""
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=int(entry.data[CONF_PORT]),
        ),
        int(entry.data[CONF_UNIT_ID]),
    )
    coordinator = JanitzaCoordinator(hass, entry, unit)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Unload a Janitza Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
