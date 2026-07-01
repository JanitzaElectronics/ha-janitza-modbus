"""Tests for Janitza Modbus helpers."""

import ast
import importlib.util
from pathlib import Path


def _load_decode_float32():
    """Load the codec helper without importing the Home Assistant package."""
    codec_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "janitza_modbus"
        / "codec.py"
    )
    spec = importlib.util.spec_from_file_location("janitza_codec", codec_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decode_float32


def test_decode_float32_big_endian() -> None:
    """Decode two registers as a big-endian float."""
    decode_float32 = _load_decode_float32()
    assert decode_float32([0x4366, 0x0000], 0) == 230.0


def test_registers_use_only_19xxx_addresses() -> None:
    """Ensure the generic register catalogue stays in the requested range."""
    addresses = _register_addresses()

    assert addresses
    assert all(19000 <= address <= 19999 for address in addresses.values())


def test_pdf_checked_total_power_addresses() -> None:
    """Ensure total power addresses match the UMG 96-PA address list."""
    addresses = _register_addresses()

    assert addresses["active_power_total"] == 19026
    assert addresses["apparent_power_total"] == 19034
    assert addresses["reactive_power_total"] == 19042
    assert addresses["reactive_energy_total"] == 19092


def test_pdf_checked_per_phase_energy_addresses() -> None:
    """Ensure per-phase energy addresses use the shared non-starred block."""
    addresses = _register_addresses()

    assert addresses["active_energy_consumed_l1"] == 19062
    assert addresses["active_energy_consumed_l2"] == 19064
    assert addresses["active_energy_consumed_l3"] == 19066
    assert addresses["active_energy_delivered_l1"] == 19070
    assert addresses["active_energy_delivered_l2"] == 19072
    assert addresses["active_energy_delivered_l3"] == 19074
    assert addresses["apparent_energy_l1"] == 19078
    assert addresses["apparent_energy_l2"] == 19080
    assert addresses["apparent_energy_l3"] == 19082
    assert addresses["reactive_energy_inductive_l1"] == 19094
    assert addresses["reactive_energy_inductive_l2"] == 19096
    assert addresses["reactive_energy_inductive_l3"] == 19098
    assert addresses["reactive_energy_capacitive_l1"] == 19102
    assert addresses["reactive_energy_capacitive_l2"] == 19104
    assert addresses["reactive_energy_capacitive_l3"] == 19106


def _register_addresses() -> dict[str, int]:
    """Return register key to address mappings without importing Home Assistant."""
    registers_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "janitza_modbus"
        / "registers.py"
    )
    tree = ast.parse(registers_path.read_text())
    addresses = [
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "address" and isinstance(keyword.value, ast.Constant)
    ]
    keys = [
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "key" and isinstance(keyword.value, ast.Constant)
    ]

    assert len(keys) == len(addresses)
    return dict(zip(keys, addresses))
