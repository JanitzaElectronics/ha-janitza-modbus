"""Small Modbus helpers for Janitza devices."""

from __future__ import annotations

from collections.abc import Sequence

from pymodbus.client import AsyncModbusTcpClient

from .validation import validate_register_block


class JanitzaModbusError(Exception):
    """Raised when a Janitza Modbus request fails."""


class JanitzaModbusClient:
    """Async Modbus TCP client for Janitza 19xxx holding registers."""

    def __init__(self, host: str, port: int, unit_id: int) -> None:
        self._unit_id = int(unit_id)
        self._client = AsyncModbusTcpClient(host=host, port=int(port))

    async def async_close(self) -> None:
        """Close the Modbus connection."""
        self._client.close()

    async def async_read_holding_registers(
        self, address: int, count: int
    ) -> Sequence[int]:
        """Read holding registers from the configured Modbus unit."""
        try:
            if not self._client.connected and not await self._client.connect():
                raise JanitzaModbusError("Unable to connect to Modbus device")

            try:
                result = await self._client.read_holding_registers(
                    address=int(address),
                    count=count,
                    device_id=self._unit_id,
                )
            except TypeError:
                result = await self._client.read_holding_registers(
                    address=int(address),
                    count=count,
                    slave=self._unit_id,
                )
        except JanitzaModbusError:
            raise
        except Exception as err:
            raise JanitzaModbusError(str(err)) from err

        try:
            if result.isError():
                raise JanitzaModbusError(str(result))

            registers = result.registers
            validate_register_block(registers, count)
        except JanitzaModbusError:
            raise
        except (AttributeError, TypeError, ValueError) as err:
            raise JanitzaModbusError(str(err)) from err

        return registers
