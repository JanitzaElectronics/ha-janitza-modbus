"""Small Modbus helpers for Janitza devices."""

from __future__ import annotations

from collections.abc import Sequence

from pymodbus.client import AsyncModbusTcpClient

from .validation import (
    MODBUS_ERROR_CONNECT,
    MODBUS_ERROR_INVALID_RESPONSE,
    MODBUS_ERROR_MODBUS_EXCEPTION,
    MODBUS_ERROR_NO_RESPONSE,
    MODBUS_ERROR_UNKNOWN,
    classify_modbus_error,
    validate_register_block,
)


class JanitzaModbusError(Exception):
    """Raised when a Janitza Modbus request fails."""

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


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
                raise JanitzaModbusError(
                    "Unable to open TCP connection to Modbus device",
                    MODBUS_ERROR_CONNECT,
                )

            try:
                result = await self._client.read_holding_registers(
                    address=address,
                    count=count,
                    device_id=self._unit_id,
                )
            except TypeError:
                result = await self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self._unit_id,
                )
        except JanitzaModbusError:
            raise
        except Exception as err:
            raise JanitzaModbusError(str(err), MODBUS_ERROR_NO_RESPONSE) from err

        try:
            if result.isError():
                message = str(result)
                reason = classify_modbus_error(message)
                if reason == MODBUS_ERROR_UNKNOWN:
                    reason = MODBUS_ERROR_MODBUS_EXCEPTION
                raise JanitzaModbusError(message, reason)

            registers = result.registers
            validate_register_block(registers, count)
        except JanitzaModbusError:
            raise
        except (AttributeError, TypeError, ValueError) as err:
            raise JanitzaModbusError(
                str(err), MODBUS_ERROR_INVALID_RESPONSE
            ) from err

        return registers
