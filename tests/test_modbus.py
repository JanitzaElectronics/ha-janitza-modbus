"""Tests for Janitza Modbus helpers."""

import ast
import importlib.util
from pathlib import Path


def _load_decode_float32():
    """Load the codec helper without importing the Home Assistant package."""
    return _load_module("janitza_codec", "codec.py").decode_float32


def _load_validation_module():
    """Load validation helpers without importing the Home Assistant package."""
    return _load_module("janitza_validation", "validation.py")


def _load_module(module_name: str, file_name: str):
    """Load an integration module file without importing package __init__."""
    module_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "janitza_modbus"
        / file_name
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decode_float32_big_endian() -> None:
    """Decode two registers as a big-endian float."""
    decode_float32 = _load_decode_float32()
    assert decode_float32([0x4366, 0x0000], 0) == 230.0


def test_normalize_host_accepts_local_targets() -> None:
    """Accept host syntax expected for local Modbus devices."""
    normalize_host = _load_validation_module().normalize_host

    assert normalize_host("  janitza-01.local  ") == "janitza-01.local"
    assert normalize_host("192.168.1.20") == "192.168.1.20"
    assert normalize_host("[fd00::10]") == "fd00::10"


def test_normalize_host_rejects_probe_primitives() -> None:
    """Reject URL-like hosts and public IP literals."""
    normalize_host = _load_validation_module().normalize_host

    for host in (
        "http://192.168.1.20",
        "user@192.168.1.20",
        "192.168.1.20:502",
        "192.168.1.20/path",
        "8.8.8.8",
        "bad host",
        "bad\nhost",
    ):
        try:
            normalize_host(host)
        except ValueError:
            continue
        raise AssertionError(f"Expected host to be rejected: {host}")


def test_validate_register_block_rejects_malformed_replies() -> None:
    """Reject short or malformed Modbus register blocks."""
    validate_register_block = _load_validation_module().validate_register_block

    validate_register_block([0, 65535], 2)

    for registers in ([1], [1, -1], [1, 65536], [1, "2"], [1, True], None):
        try:
            validate_register_block(registers, 2)
        except ValueError:
            continue
        raise AssertionError(f"Expected registers to be rejected: {registers}")


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
