"""Validation helpers for Janitza Modbus."""

from __future__ import annotations

from collections.abc import Sequence
import ipaddress
import re

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

MODBUS_ERROR_CONNECT = "connect"
MODBUS_ERROR_INVALID_RESPONSE = "invalid_response"
MODBUS_ERROR_MODBUS_EXCEPTION = "modbus_exception"
MODBUS_ERROR_NO_RESPONSE = "no_response"
MODBUS_ERROR_UNKNOWN = "unknown"


def normalize_host(host: object) -> str:
    """Normalize and validate a Modbus host name or IP address."""
    value = str(host).strip()
    if not value:
        raise ValueError("Host is required")

    if any(ord(char) < 32 or char.isspace() for char in value):
        raise ValueError("Host contains whitespace or control characters")

    if "://" in value or "@" in value or any(char in value for char in "/\\?#"):
        raise ValueError("Host must not be a URL")

    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        if ":" in value:
            raise ValueError("Host must not include a port") from None
        labels = value.rstrip(".").split(".")
        if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
            raise ValueError("Host is not a valid DNS name") from None
        return value

    if address.is_global:
        raise ValueError("Public IP addresses are not allowed")

    return value


def validate_register_block(registers: Sequence[int], expected_count: int) -> None:
    """Validate a Modbus register block before decoding values."""
    try:
        actual_count = len(registers)
    except TypeError as err:
        raise ValueError("Modbus response does not contain a register list") from err

    if actual_count < expected_count:
        raise ValueError(
            f"Expected at least {expected_count} registers, got {actual_count}"
        )

    for register in registers[:expected_count]:
        if isinstance(register, bool) or not isinstance(register, int):
            raise ValueError("Modbus register values must be integers")
        if not 0 <= register <= 0xFFFF:
            raise ValueError("Modbus register values must be 16-bit unsigned integers")


def classify_modbus_error(message: str) -> str:
    """Classify a raw Modbus error string for setup-flow feedback."""
    normalized = message.lower()
    no_response_markers = (
        "no response",
        "timed out",
        "timeout",
        "did not respond",
        "no data",
        "incomplete message",
    )
    if any(marker in normalized for marker in no_response_markers):
        return MODBUS_ERROR_NO_RESPONSE

    modbus_exception_markers = (
        "exception response",
        "illegal address",
        "illegal function",
        "exception code",
        "modbus exception",
    )
    if any(marker in normalized for marker in modbus_exception_markers):
        return MODBUS_ERROR_MODBUS_EXCEPTION

    return MODBUS_ERROR_UNKNOWN
