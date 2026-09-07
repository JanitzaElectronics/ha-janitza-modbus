"""Validation helpers for Janitza Modbus."""

from __future__ import annotations

import ipaddress
import re

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

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
