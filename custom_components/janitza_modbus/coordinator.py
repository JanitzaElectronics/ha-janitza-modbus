"""Data coordinator for Janitza Modbus sensors."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import struct

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .codec import decode_finite_float32, decode_string
from .const import CONF_SCAN_INTERVAL, CONF_UNIT_ID, DOMAIN
from .modbus import JanitzaModbusClient, JanitzaModbusError
from .registers import (
    MAX_REGISTER_ADDRESS,
    MIN_REGISTER_ADDRESS,
    MODULE_GROUP_COUNT,
    MODULE_GROUP_READ_COUNT,
    REGISTERS,
    UMG800_MODULE_GROUP_COUNT,
    UMG800_MODULE_GROUP_READ_COUNT,
    UMG800_VIRTUAL_METER_NAME_REGISTER_COUNT,
    JanitzaRegister,
    build_module_group_registers,
    build_umg800_module_group_registers,
    module_group_base_address,
    umg800_module_group_base_address,
    umg800_virtual_meter_name_address,
)

_LOGGER = logging.getLogger(__name__)

UMG801_MODULE_INFO_BASE_ADDRESS = 4178
UMG801_MODULE_INFO_ADDRESS_STRIDE = 80
MODULE_INFO_NAME_REGISTER_COUNT = 32
UMG801_MODULE_INFO_STATE_OFFSET = 68

UMG800_DEVICE_NAME_ADDRESS = 0
UMG800_DEVICE_NAME_REGISTER_COUNT = 32
UMG800_MODULE_SLOT_COUNT = 13
UMG800_MODULE_INFO_BASE_ADDRESS = 54
UMG800_MODULE_INFO_ADDRESS_STRIDE = 56
UMG800_MODULE_INFO_STATE_OFFSET = 44
MODULE_TYPE_TO_GROUP_COUNT = {
    1: 2,  # 800-CT8-A / CT8_5A on the live UMG801
    2: 0,  # DI_14
    3: 6,  # CT24_LP
    4: 2,  # 800-CT8-LP on the live UMG801
}


class JanitzaCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
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
        self._module_profile: str | None = None
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

    async def _async_update_data(self) -> dict[str, float | None]:
        """Fetch all configured 19xxx register values."""
        count = MAX_REGISTER_ADDRESS - MIN_REGISTER_ADDRESS + 2
        try:
            registers = await self._client.async_read_holding_registers(
                MIN_REGISTER_ADDRESS, count
            )
        except JanitzaModbusError as err:
            raise UpdateFailed(str(err)) from err

        try:
            values: dict[str, float | None] = {}
            for register in REGISTERS:
                index = register.address - MIN_REGISTER_ADDRESS
                value = decode_finite_float32(registers, index)
                values[register.key] = round(value, 6) if value is not None else None
        except (IndexError, struct.error, ValueError) as err:
            raise UpdateFailed(str(err)) from err

        if not self._module_groups_discovered:
            await self._async_discover_module_groups()

        try:
            for group in self._discovered_module_groups():
                group_registers = self._build_module_group_registers(group)
                group_base = self._module_group_base_address(group)
                group_block = await self._client.async_read_holding_registers(
                    group_base,
                    self._module_group_read_count(),
                )
                for register in group_registers:
                    index = register.address - group_base
                    value = decode_finite_float32(group_block, index)
                    values[register.key] = (
                        round(value, 6) if value is not None else None
                    )
        except (IndexError, struct.error, ValueError) as err:
            raise UpdateFailed(str(err)) from err
        except JanitzaModbusError as err:
            raise UpdateFailed(str(err)) from err

        return values

    async def _async_discover_module_groups(self) -> None:
        """Discover supported UMG 800 or UMG 801 module groups over Modbus."""
        registers = list(REGISTERS)
        discovered_groups: list[int] = []
        try:
            # Keep the established UMG 801 probe first. This avoids adding a
            # new, possibly unsupported low-address read to working UMG 801
            # installations that already expose current modules.
            self._module_group_labels = (
                await self._async_discover_umg801_module_group_labels()
            )
            if self._module_group_labels:
                self._module_profile = "umg801"
            elif await self._async_is_umg800():
                self._module_profile = "umg800"
                module_labels = (
                    await self._async_discover_umg800_module_group_labels()
                )
                virtual_meter_labels = (
                    await self._async_discover_umg800_virtual_meter_labels()
                )
                self._module_group_labels = {
                    **module_labels,
                    **virtual_meter_labels,
                }
        except asyncio.CancelledError:
            _LOGGER.debug("Janitza module discovery was cancelled; skipping modules")
            self.registers = tuple(registers)
            self._module_groups = ()
            self._module_groups_discovered = True
            return

        if not self._module_group_labels:
            self.registers = tuple(registers)
            self._module_groups = ()
            self._module_groups_discovered = True
            return

        for group in sorted(self._module_group_labels):
            group_base = self._module_group_base_address(group)
            try:
                if self._module_profile == "umg800":
                    group_block = await self._client.async_read_holding_registers(
                        group_base,
                        UMG800_MODULE_GROUP_READ_COUNT,
                    )
                    group_registers = self._build_module_group_registers(group)
                    if not any(
                        decode_finite_float32(
                            group_block,
                            register.address - group_base,
                        )
                        is not None
                        for register in group_registers
                    ):
                        continue
                else:
                    await self._client.async_read_holding_registers(group_base, 2)
            except asyncio.CancelledError:
                _LOGGER.debug("Janitza module group probe was cancelled")
                break
            except JanitzaModbusError:
                continue

            discovered_groups.append(group)
            registers.extend(self._build_module_group_registers(group))

        self.registers = tuple(registers)
        self._module_groups = tuple(discovered_groups)
        self._module_groups_discovered = True

        if discovered_groups:
            _LOGGER.info("Discovered Janitza module groups: %s", discovered_groups)

    def _discovered_module_groups(self) -> tuple[int, ...]:
        """Return the discovered current module groups."""
        return getattr(self, "_module_groups", ())

    async def _async_is_umg800(self) -> bool:
        """Identify a UMG 800 using its default Modbus device-name mapping."""
        try:
            registers = await self._client.async_read_holding_registers(
                UMG800_DEVICE_NAME_ADDRESS,
                UMG800_DEVICE_NAME_REGISTER_COUNT,
            )
        except JanitzaModbusError:
            return False

        device_name = decode_string(registers).upper().replace(" ", "")
        return device_name.startswith("UMG800")

    async def _async_discover_umg801_module_group_labels(self) -> dict[int, str]:
        """Read UMG 801 module names from its Modbus slot information area."""
        labels: dict[int, str] = {}
        next_group = 1

        for slot in range(1, MODULE_GROUP_COUNT + 1):
            slot_base = UMG801_MODULE_INFO_BASE_ADDRESS + (
                (slot - 1) * UMG801_MODULE_INFO_ADDRESS_STRIDE
            )
            try:
                name_registers = await self._client.async_read_holding_registers(
                    slot_base,
                    MODULE_INFO_NAME_REGISTER_COUNT,
                )
                state_type = await self._client.async_read_holding_registers(
                    slot_base + UMG801_MODULE_INFO_STATE_OFFSET,
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

    async def _async_discover_umg800_module_group_labels(self) -> dict[int, str]:
        """Build fallback labels from UMG 800 physical module metadata."""
        labels: dict[int, str] = {}
        next_group = 1

        for slot in range(1, UMG800_MODULE_SLOT_COUNT + 1):
            slot_base = UMG800_MODULE_INFO_BASE_ADDRESS + (
                (slot - 1) * UMG800_MODULE_INFO_ADDRESS_STRIDE
            )
            try:
                name_registers = await self._client.async_read_holding_registers(
                    slot_base,
                    MODULE_INFO_NAME_REGISTER_COUNT,
                )
                state_and_type = await self._client.async_read_holding_registers(
                    slot_base + UMG800_MODULE_INFO_STATE_OFFSET,
                    2,
                )
            except JanitzaModbusError:
                continue

            module_type = state_and_type[1]
            module_name = decode_string(name_registers) or f"Module {slot:02d}"
            group_count = MODULE_TYPE_TO_GROUP_COUNT.get(module_type, 0)
            if group_count == 0:
                normalized_name = module_name.upper().replace("-", "")
                if "CT12" in normalized_name:
                    group_count = 3
                elif "CT24" in normalized_name:
                    group_count = 6
                elif "CT8" in normalized_name:
                    group_count = 2

            # Module kind/name is the presence guard. Maintenance state is not
            # used here because a connected UMG 800 module should remain
            # visible while it reports a fault or transitional state.
            if group_count == 0:
                continue

            for module_group in range(1, group_count + 1):
                if next_group > UMG800_MODULE_GROUP_COUNT:
                    break
                labels[next_group] = f"{module_name} Group {module_group}"
                next_group += 1

        return labels

    async def _async_discover_umg800_virtual_meter_labels(self) -> dict[int, str]:
        """Read independently configured UMG 800 virtual meter names."""
        labels: dict[int, str] = {}

        for group in range(1, UMG800_MODULE_GROUP_COUNT + 1):
            try:
                name_registers = await self._client.async_read_holding_registers(
                    umg800_virtual_meter_name_address(group),
                    UMG800_VIRTUAL_METER_NAME_REGISTER_COUNT,
                )
            except JanitzaModbusError:
                continue

            meter_name = decode_string(name_registers)
            if meter_name:
                labels[group] = meter_name

        return labels

    def _module_group_base_address(self, group: int) -> int:
        """Return the module group base for the detected device profile."""
        if self._module_profile == "umg800":
            return umg800_module_group_base_address(group)
        return module_group_base_address(group)

    def _module_group_read_count(self) -> int:
        """Return the register span for the detected device profile."""
        if self._module_profile == "umg800":
            return UMG800_MODULE_GROUP_READ_COUNT
        return MODULE_GROUP_READ_COUNT

    def _build_module_group_registers(
        self, group: int
    ) -> tuple[JanitzaRegister, ...]:
        """Build module sensors for the detected device profile."""
        label = self._module_group_labels.get(group)
        if self._module_profile == "umg800":
            return build_umg800_module_group_registers(group, label=label)
        return build_module_group_registers(group, label=label)
