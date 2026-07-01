"""Codec helpers for Janitza Modbus registers."""

from __future__ import annotations

import struct
from collections.abc import Sequence


def decode_float32(registers: Sequence[int], index: int) -> float:
    """Decode a big-endian IEEE-754 float from two Modbus registers."""
    raw = struct.pack(">HH", registers[index], registers[index + 1])
    return struct.unpack(">f", raw)[0]
