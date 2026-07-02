"""Codec helpers for Janitza Modbus registers."""

from __future__ import annotations

import struct
from collections.abc import Sequence


def decode_float32(registers: Sequence[int], index: int) -> float:
    """Decode a big-endian IEEE-754 float from two Modbus registers."""
    raw = struct.pack(">HH", registers[index], registers[index + 1])
    return struct.unpack(">f", raw)[0]


def decode_string(registers: Sequence[int]) -> str:
    """Decode a NUL-terminated UTF-8 string from Modbus registers."""
    raw = bytearray()
    for register in registers:
        raw.extend(int(register).to_bytes(2, "big"))
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
