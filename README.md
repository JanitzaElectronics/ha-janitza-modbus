# Janitza Modbus for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![Contributors][contributors-shield]][contributors]
[![Stars][stars-shield]][stars]
[![Issues][issues-shield]][issues]

Custom Home Assistant integration for Janitza energy measurement devices over
Modbus TCP.

The integration intentionally reads only the generic Janitza `19xxx` holding
register range so it can work across device families that expose the common
measurement profile.

## Features

- UI based setup through Home Assistant config entries
- Local polling over Modbus TCP
- Batched reads of the `19xxx` register block
- Auto-discovery of readable UMG 801 current module groups
- Energy dashboard friendly sensor metadata where applicable
- HACS compatible repository layout

## Release 0.2.1

Small stability release. Non-finite Modbus float values such as `nan` and
`inf` are now treated as unavailable sensor samples so Home Assistant does not
reject numeric sensor state updates.

## Release 0.2.0

This release adds UMG 801 current module support. The integration now probes
the documented module measurement blocks from `19400` onward and creates module
entities only for groups that answer over Modbus.

## Installation with HACS

1. Add `https://github.com/JanitzaElectronics/ha-janitza-modbus` as a custom
   HACS integration repository.
2. Install **Janitza Modbus**.
3. Restart Home Assistant.
4. Add the integration from **Settings > Devices & services**.

## Configuration

The setup flow asks for:

- Hostname or IP address
- TCP port, usually `502`
- Modbus unit ID, often `2` for Janitza measurement registers
- Display name
- Poll interval in seconds

## Supported registers

The initial register catalogue is deliberately small and uses only addresses in
the generic `19xxx` range. Register values are decoded as big-endian IEEE-754
32-bit floats from holding registers.

The current catalogue was checked against the Janitza UMG 96-PA and UMG 604-PRO
Modbus address lists. It includes the commonly needed values from `19000`
through `19120`, including:

- Phase and line voltages
- Phase currents and vector current sum
- Per-phase and summed active, apparent, and reactive power
- Per-phase power factor
- Frequency
- Per-phase and total active, apparent, and reactive energy counters
- Voltage and current THD values

If a device exposes additional generic `19xxx` values, add them in
`custom_components/janitza_modbus/registers.py`.

The PDF lists summed active, apparent, and reactive power at `19026`, `19034`,
and `19042`. The adjacent addresses `19024`, `19032`, and `19040` are L3
phase values, not totals.

UMG 604-PRO also exposes additional values later in the `19xxx` range, for
example `19630+`. Those are not enabled by default because the integration
currently performs one contiguous read of the shared `19000` through `19120`
block.

For UMG 801 devices, the integration also probes the documented current module
group blocks starting at `19400`, `19500`, `19600`, and so on. Only groups that
answer over Modbus are added as entities. This matches native Home Assistant
Modbus examples such as `19410`, `19514`, and `19708`.

The UMG 96-PA address list marks `19054` through `19058` and `19086` through
`19090` as device-specific compared with other UMG-series devices. For that
reason, the default catalogue uses the non-starred per-phase energy counters
from `19062` onward.

## Notes

Janitza devices and gateways may need Modbus TCP enabled in the device settings.
Some installations also require firewall access to TCP port `502`.
If connection tests fail but Home Assistant's native Modbus integration works,
double-check the Modbus unit ID. On some Janitza setups the generic `19xxx`
measurement registers are exposed on slave/unit `2` rather than `1`.

The UMG 801 workbook in the repository also documents a per-slot information
area at `4178 + 80 * (slot - 1)`. In that block, `+68` stores the slot state
and `+69` the module type. That is useful for future metadata work, but the
integration currently discovers module measurement groups by probing the
readable `19400+` address blocks directly.

[contributors-shield]: https://img.shields.io/github/contributors/JanitzaElectronics/ha-janitza-modbus
[contributors]: https://github.com/JanitzaElectronics/ha-janitza-modbus/graphs/contributors
[issues-shield]: https://img.shields.io/github/issues/JanitzaElectronics/ha-janitza-modbus
[issues]: https://github.com/JanitzaElectronics/ha-janitza-modbus/issues
[releases-shield]: https://img.shields.io/github/v/release/JanitzaElectronics/ha-janitza-modbus?sort=semver
[releases]: https://github.com/JanitzaElectronics/ha-janitza-modbus/releases
[stars-shield]: https://img.shields.io/github/stars/JanitzaElectronics/ha-janitza-modbus?style=flat
[stars]: https://github.com/JanitzaElectronics/ha-janitza-modbus/stargazers
