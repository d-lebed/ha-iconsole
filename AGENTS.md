# AGENTS.md — AI Coding Agent Guidelines for `ha-iconsole`

## Project Overview

`ha-iconsole` is a standalone Home Assistant custom integration (`custom_components/iconsole`, domain `iconsole`) for **iConsole+ / ChangYow** Bluetooth LE treadmills (Zipro, Toorx, Reebok, DKN, Focus Fitness, JTX, etc.).

It is structured as a 100% HACS-compliant and Hassfest-validated repository with **zero external PyPI requirements**, relying exclusively on Home Assistant's built-in Bluetooth stack (`homeassistant.components.bluetooth`, `bleak`, `bleak_retry_connector`).

## Repository Layout

- `custom_components/iconsole/`
  - `__init__.py` — ConfigEntry setup/unload, `DataUpdateCoordinator`, and passive/active BLE advertisement listener for automatic background reconnection.
  - `client.py` — `IConsoleClient`: BLE GATT transport, Device Information Service (`0x180A`) reading, sleep/wake probing, command queue, and delegation to protocol strategies.
  - `protocols/` — Protocol strategy package:
    - `base.py` — `TreadmillProtocol` (ABC), `TreadmillLimits`, `TreadmillTelemetry`, and ChangYow `0xF0` packet framing (`+1` encoding and checksum).
    - `d2.py` — `TreadmillD2Protocol` for classic `00.D2` treadmills (e.g. `SI1022`).
    - `d5.py` — `TreadmillD5Protocol` for newer `00.D5` treadmills (prepends length byte; read-only telemetry until D5 writes are verified on physical hardware).
    - `__init__.py` — `get_protocol(meter_id)` factory and exports.
  - `config_flow.py` — Bluetooth auto-discovery (`iConsole*` and service `0xFFF0`) and manual user device selection flow.
  - `const.py` — GATT UUIDs, command/response opcodes (`0xA0..0xAF`, `0xB0..0xBF`), entity keys, and status enums.
  - `entity.py` — Base `IConsoleEntity` (`CoordinatorEntity` + `RestoreEntity`).
  - `sensor.py` — 7 workout telemetry sensors + 1 diagnostic `connection_status` sensor.
  - `button.py` — Capability-gated workout control buttons (`Stop` on `00.D2`; disabled on `00.D5` pending hardware validation).
  - `number.py` — Capability-gated target controls (`Target inclination` on `00.D2`; disabled on `00.D5` pending hardware validation).
  - `switch.py` — `Bluetooth connection` switch allowing users to disconnect HA when using a mobile app or handrail controls.
  - `brand/` — Local integration icons (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`).
  - `manifest.json`, `translations/` (`en`, `pl`, `de`, `fr`, `es`, `it`, `nl`, `pt`, `cs`, `uk`, `ru`).
- `docs/PROTOCOL.md` — Complete reverse-engineered ChangYow BLE protocol specification.
- `CHANGELOG.md` — Version history following Keep a Changelog and Semantic Versioning.
- `hacs.json` — HACS manifest.
- `.github/workflows/validate.yml` — GitHub Actions workflow running official `hacs/action` and `home-assistant/actions/hassfest`.

## Critical Protocol & Hardware Rules (Do Not Regress)

1. **Write-Without-Response (`response=False`)**:
   The ChangYow write characteristic (`0000fff2-0000-1000-8000-00805f9b34fb`) on `SI1022` consoles advertises both `write` and `write-without-response`, but silently drops GATT Write-With-Response requests. Always prefer `write-without-response` (`response=False`) when supported by the characteristic.
2. **Hardware Revisions (`00.D2` vs `00.D5`)**:
   - `TreadmillD5Protocol` (`meter_id == 0xD5`) handles newer D5 consoles, which prepend a length byte to every command/response. On `main`, `TreadmillD5Protocol` is **read-only** (`supports_start_pause = supports_stop = supports_target_incline = supports_target_speed = False`) and must not send unverified belt/workout write commands until confirmed on physical `00.D5` hardware (see `feat/d5-controls` branch and Issue #1).
   - `TreadmillD2Protocol` (`meter_id == 0xD2`) handles classic consoles, which do **not** prepend a length byte, treat `0xA6` as a 25-byte program speed profile (never send an 8-byte `0xA6` to `00.D2`!), and support verified `Stop` and `Target inclination` (`0xAC`) controls.
3. **Console Panel Unlock (`CMD_SET_KEY_LOCK` `0xAF` on `00.D2`)**:
   - Sending `F0 A0` puts a `00.D2` console into Bluetooth mode, which locks all physical console buttons by default.
   - To keep the main console panel buttons working, always finish initialization (and handle post-stop `F0 BF ... 03` lock notifications) with `CMD_SET_MODE` (`0xA3`) + `CMD_SET_PARAM` (`0xA4`) + `CMD_SET_KEY_LOCK` (`0xAF` with raw value `0x01` -> wire `F0 AF 01 D3 02 75`).
   - Never send `CMD_SET_KEY_LOCK` with raw value `0x00` (`F0 AF 01 D3 01 74`), as it locks the main panel on `SI1022` hardware.
4. **Countdown Handling (`03 02` -> `03 04` on `00.D2`)**:
   - Never send `F0 A5 01 D3 02 6B` (`CMD_SET_CONTROL_STATE` start) *during* the 3-second countdown (`raw_state == 2, warmup_state == 1`), as the console interprets it as an abort. Only send it after the countdown completes (`raw_state == 2, warmup_state == 3`).
5. **Offline / Sleep Tolerance**:
   - `async_setup_entry` must never raise `ConfigEntryNotReady` when the treadmill is powered off. Instead, load the entry with entities unavailable (`connection_status = disconnected`) and rely on the registered `bluetooth.async_register_callback` to connect automatically when BLE advertisements appear.

## Validation & Quality Checks

Before committing or opening a PR:
- Ensure `manifest.json` keys are sorted: `domain`, `name`, then alphabetical order (required by `hassfest`).
- Keep `translations/en.json` and the other locale files in `translations/` synchronized.
- Ensure no debug-only `importlib.reload` hooks remain in `__init__.py` for production releases.
- Never move or force-push an already published release tag. Bump `version` in `manifest.json`, update `CHANGELOG.md`, and cut a new SemVer tag/release instead.
