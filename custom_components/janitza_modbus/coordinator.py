"""Data coordinator for Janitza Modbus sensors."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .codec import decode_float32
from .const import CONF_SCAN_INTERVAL, CONF_UNIT_ID, DOMAIN
from .modbus import JanitzaModbusClient, JanitzaModbusError
from .registers import MAX_REGISTER_ADDRESS, MIN_REGISTER_ADDRESS, REGISTERS

_LOGGER = logging.getLogger(__name__)


class JanitzaCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Coordinator that reads Janitza 19xxx registers."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Janitza coordinator."""
        self._client = JanitzaModbusClient(
            host=entry.data["host"],
            port=entry.data["port"],
            unit_id=entry.data[CONF_UNIT_ID],
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

    async def async_close(self) -> None:
        """Close the Modbus client."""
        await self._client.async_close()

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch all configured 19xxx register values."""
        count = MAX_REGISTER_ADDRESS - MIN_REGISTER_ADDRESS + 2
        try:
            registers = await self._client.async_read_holding_registers(
                MIN_REGISTER_ADDRESS, count
            )
        except JanitzaModbusError as err:
            raise UpdateFailed(str(err)) from err

        values: dict[str, float] = {}
        for register in REGISTERS:
            index = register.address - MIN_REGISTER_ADDRESS
            values[register.key] = round(decode_float32(registers, index), 6)

        return values
