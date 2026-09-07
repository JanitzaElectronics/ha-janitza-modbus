"""Tests for Janitza Modbus helpers."""

import ast
import importlib.util
import json
from pathlib import Path
import sys
import types


def _load_decode_float32():
    """Load the codec helper without importing the Home Assistant package."""
    return _load_module("janitza_codec", "codec.py").decode_float32


def _load_validation_module():
    """Load validation helpers without importing the Home Assistant package."""
    return _load_module("janitza_validation", "validation.py")


def _load_registers_module():
    """Load register helpers with small Home Assistant stubs."""
    sensor_module = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:
        VOLTAGE = "voltage"
        CURRENT = "current"
        POWER = "power"
        APPARENT_POWER = "apparent_power"
        REACTIVE_POWER = "reactive_power"
        REACTIVE_ENERGY = "reactive_energy"
        POWER_FACTOR = "power_factor"
        FREQUENCY = "frequency"
        ENERGY = "energy"

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL = "total"

    sensor_module.SensorDeviceClass = SensorDeviceClass
    sensor_module.SensorStateClass = SensorStateClass

    const_module = types.ModuleType("homeassistant.const")

    class _Unit:
        def __init__(self, **entries):
            for key, value in entries.items():
                setattr(self, key, value)

    const_module.UnitOfApparentPower = _Unit(VOLT_AMPERE="VA")
    const_module.UnitOfElectricCurrent = _Unit(AMPERE="A")
    const_module.UnitOfElectricPotential = _Unit(VOLT="V")
    const_module.UnitOfEnergy = _Unit(WATT_HOUR="Wh")
    const_module.UnitOfFrequency = _Unit(HERTZ="Hz")
    const_module.UnitOfPower = _Unit(WATT="W")
    const_module.UnitOfReactivePower = _Unit(VOLT_AMPERE_REACTIVE="var")

    sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
    sys.modules["homeassistant.components.sensor"] = sensor_module
    sys.modules["homeassistant.const"] = const_module

    return _load_module("janitza_registers", "registers.py")


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
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_decode_float32_big_endian() -> None:
    """Decode two registers as a big-endian float."""
    decode_float32 = _load_decode_float32()
    assert decode_float32([0x4366, 0x0000], 0) == 230.0


def test_decode_finite_float32_rejects_non_finite_values() -> None:
    """Convert IEEE-754 NaN and infinity payloads to None."""
    decode_finite_float32 = _load_module(
        "janitza_codec_finite", "codec.py"
    ).decode_finite_float32

    assert decode_finite_float32([0x4366, 0x0000], 0) == 230.0
    assert decode_finite_float32([0x7FC0, 0x0000], 0) is None
    assert decode_finite_float32([0x7F80, 0x0000], 0) is None


def test_decode_string_nul_terminated() -> None:
    """Decode a Modbus string register block."""
    decode_string = _load_module("janitza_codec_string", "codec.py").decode_string
    assert decode_string([0x4D31, 0x0000, 0x4142]) == "M1"


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


def test_manifest_uses_home_assistant_modbus_platform() -> None:
    """Use Home Assistant's shared Modbus connection instead of PyModbus."""
    integration_root = (
        Path(__file__).parents[1] / "custom_components" / "janitza_modbus"
    )
    manifest = json.loads((integration_root / "manifest.json").read_text())
    source = "\n".join(
        path.read_text() for path in integration_root.glob("*.py")
    )

    assert "modbus" in manifest["dependencies"]
    assert not manifest.get("requirements")
    assert "pymodbus" not in source
    assert "async_get_unit" in (integration_root / "__init__.py").read_text()
    assert "async_get_temporary_unit" in (
        integration_root / "config_flow.py"
    ).read_text()


def test_runtime_translation_bundle_exists() -> None:
    """Ship the runtime English translation bundle for config flow errors."""
    translation_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "janitza_modbus"
        / "translations"
        / "en.json"
    )

    assert translation_path.is_file()
    assert '"cannot_connect"' in translation_path.read_text()


def test_module_group_base_addresses_match_docs() -> None:
    """UMG801 current module groups advance in documented 100-register steps."""
    registers = _load_registers_module()

    assert registers.module_group_base_address(1) == 19400
    assert registers.module_group_base_address(2) == 19500
    assert registers.module_group_base_address(4) == 19700


def test_module_group_registers_match_known_native_modbus_addresses() -> None:
    """Module sensor templates should match the working native Modbus examples."""
    registers = _load_registers_module()
    module_01 = {register.key: register.address for register in registers.build_module_group_registers(1)}
    module_02 = {register.key: register.address for register in registers.build_module_group_registers(2)}
    module_04 = {register.key: register.address for register in registers.build_module_group_registers(4)}

    assert module_01["module_01_active_power_p2"] == 19410
    assert module_02["module_02_active_power_sum"] == 19514
    assert module_04["module_04_active_power_p1"] == 19708


def test_module_group_registers_can_use_modbus_module_label() -> None:
    """Discovered module names should flow into generated entity names."""
    registers = _load_registers_module()
    named_registers = registers.build_module_group_registers(1, label="M1 Group 1")

    assert named_registers[0].name == "M1 Group 1 Current I1"


def test_umg800_module_group_base_addresses_match_default_map() -> None:
    """UMG 800 virtual meter groups advance in 1000-register steps."""
    registers = _load_registers_module()

    assert registers.umg800_module_group_base_address(1) == 1012
    assert registers.umg800_module_group_base_address(2) == 2012
    assert registers.umg800_module_group_base_address(13) == 13012


def test_umg800_module_registers_match_default_map() -> None:
    """UMG 800 virtual meter sensors use the documented offsets."""
    registers = _load_registers_module()
    module_01 = {
        register.key: register.address
        for register in registers.build_umg800_module_group_registers(1)
    }
    module_02 = {
        register.key: register.address
        for register in registers.build_umg800_module_group_registers(2)
    }

    assert module_01["virtual_meter_01_current_i1"] == 1012
    assert module_01["virtual_meter_01_active_power_p1"] == 1024
    assert module_01["virtual_meter_01_active_energy_sum"] == 1064
    assert module_01["virtual_meter_01_current_thd_i3"] == 1124
    assert module_02["virtual_meter_02_active_power_sum"] == 2030


def test_umg800_virtual_meter_names_match_default_map() -> None:
    """UMG 800 virtual meter names follow their documented group blocks."""
    registers = _load_registers_module()

    assert registers.umg800_virtual_meter_name_address(1) == 1966
    assert registers.umg800_virtual_meter_name_address(2) == 2966
    assert registers.umg800_virtual_meter_name_address(32) == 32966


def test_umg800_virtual_meter_registers_do_not_request_translations() -> None:
    """Dynamic virtual meter entities use their Modbus-provided names."""
    registers = _load_registers_module()
    meter_registers = registers.build_umg800_module_group_registers(
        1, label="Main distribution"
    )

    assert meter_registers[0].key == "virtual_meter_01_current_i1"
    assert meter_registers[0].name == "Main distribution Current I1"
    assert meter_registers[0].translation_key is None


def test_umg801_module_registers_are_unchanged_by_umg800_support() -> None:
    """Keep the existing UMG 801 module profile stable."""
    registers = _load_registers_module()
    module_01 = {
        register.key: register.address
        for register in registers.build_module_group_registers(1)
    }

    assert module_01["module_01_current_i1"] == 19400
    assert module_01["module_01_active_power_p1"] == 19408
    assert module_01["module_01_active_energy_sum"] == 19444
    assert module_01["module_01_current_thd_i3"] == 19498


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
