"""Data coordinator for Janitza Modbus sensors."""

from __future__ import annotations

from datetime import timedelta
import logging
import struct

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .codec import decode_float32, decode_string
from .const import CONF_SCAN_INTERVAL, CONF_UNIT_ID, DOMAIN
from .modbus import JanitzaModbusClient, JanitzaModbusError
from .registers import (
    MAX_REGISTER_ADDRESS,
    MIN_REGISTER_ADDRESS,
    MODULE_GROUP_COUNT,
    MODULE_GROUP_READ_COUNT,
    REGISTERS,
    JanitzaRegister,
    build_module_group_registers,
    module_group_base_address,
)

_LOGGER = logging.getLogger(__name__)

MODULE_INFO_BASE_ADDRESS = 4178
MODULE_INFO_ADDRESS_STRIDE = 80
MODULE_INFO_NAME_REGISTER_COUNT = 32
MODULE_INFO_STATE_OFFSET = 68
MODULE_TYPE_TO_GROUP_COUNT = {
    1: 2,  # 800-CT8-A / CT8_5A on the live UMG801
    2: 0,  # DI_14
    3: 6,  # CT24_LP
    4: 2,  # 800-CT8-LP on the live UMG801
}


class JanitzaCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Coordinator that reads Janitza 19xxx registers."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Janitza coordinator."""
        self._client = JanitzaModbusClient(
            host=entry.data["host"],
            port=int(entry.data["port"]),
            unit_id=int(entry.data[CONF_UNIT_ID]),
        )
        self.registers: tuple[JanitzaRegister, ...] = REGISTERS
        self._module_group_labels: dict[int, str] = {}
        self._module_groups_discovered = False

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(entry.data[CONF_SCAN_INTERVAL])),
        )

    async def async_close(self) -> None:
        """Close the Modbus client."""
        await self._client.async_close()

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch all configured 19xxx register values."""
        if not self._module_groups_discovered:
            await self._async_discover_module_groups()

        count = MAX_REGISTER_ADDRESS - MIN_REGISTER_ADDRESS + 2
        try:
            registers = await self._client.async_read_holding_registers(
                MIN_REGISTER_ADDRESS, count
            )
        except JanitzaModbusError as err:
            raise UpdateFailed(str(err)) from err

        try:
            values: dict[str, float] = {}
            for register in REGISTERS:
                index = register.address - MIN_REGISTER_ADDRESS
                values[register.key] = round(decode_float32(registers, index), 6)

            for group in self._discovered_module_groups():
                group_registers = build_module_group_registers(
                    group,
                    label=self._module_group_labels.get(group),
                )
                group_base = module_group_base_address(group)
                group_block = await self._client.async_read_holding_registers(
                    group_base,
                    MODULE_GROUP_READ_COUNT,
                )
                for register in group_registers:
                    index = register.address - group_base
                    values[register.key] = round(
                        decode_float32(group_block, index), 6
                    )
        except (IndexError, struct.error, ValueError) as err:
            raise UpdateFailed(str(err)) from err
        except JanitzaModbusError as err:
            raise UpdateFailed(str(err)) from err

        return values

    async def _async_discover_module_groups(self) -> None:
        """Discover which documented UMG801 module groups answer over Modbus."""
        registers = list(REGISTERS)
        discovered_groups: list[int] = []
        self._module_group_labels = await self._async_discover_module_group_labels()

        for group in range(1, MODULE_GROUP_COUNT + 1):
            group_base = module_group_base_address(group)
            try:
                await self._client.async_read_holding_registers(group_base, 2)
            except JanitzaModbusError:
                continue

            discovered_groups.append(group)
            registers.extend(
                build_module_group_registers(
                    group,
                    label=self._module_group_labels.get(group),
                )
            )

        self.registers = tuple(registers)
        self._module_groups = tuple(discovered_groups)
        self._module_groups_discovered = True

        if discovered_groups:
            _LOGGER.info("Discovered Janitza module groups: %s", discovered_groups)

    def _discovered_module_groups(self) -> tuple[int, ...]:
        """Return the discovered UMG801 current module groups."""
        return getattr(self, "_module_groups", ())

    async def _async_discover_module_group_labels(self) -> dict[int, str]:
        """Read module names from the documented Modbus slot info area."""
        labels: dict[int, str] = {}
        next_group = 1

        for slot in range(1, MODULE_GROUP_COUNT + 1):
            slot_base = MODULE_INFO_BASE_ADDRESS + ((slot - 1) * MODULE_INFO_ADDRESS_STRIDE)
            try:
                name_registers = await self._client.async_read_holding_registers(
                    slot_base,
                    MODULE_INFO_NAME_REGISTER_COUNT,
                )
                state_type = await self._client.async_read_holding_registers(
                    slot_base + MODULE_INFO_STATE_OFFSET,
                    2,
                )
            except JanitzaModbusError:
                continue

            state = state_type[0]
            module_type = state_type[1]
            group_count = MODULE_TYPE_TO_GROUP_COUNT.get(module_type, 0)
            if state != 2 or group_count == 0:
                continue

            module_name = decode_string(name_registers) or f"Module {slot:02d}"
            for module_group in range(1, group_count + 1):
                labels[next_group] = f"{module_name} Group {module_group}"
                next_group += 1

        return labels
