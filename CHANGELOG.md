# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-11-17

### Fixed
- Replaced the white outer background around the integration icon and logo (`custom_components/iconsole/brand/`) with clean vector-clipped transparent rounded corners (`RGBA`) in accordance with Home Assistant Brands guidelines.

## [0.5.0] - 2026-11-17

### Added
- Initial public release of the **iConsole+ (ChangYow)** custom integration for Home Assistant.
- Direct Bluetooth LE communication over ChangYow UART (`0xFFF0` / `ISSC`) with zero external PyPI dependencies.
- Modular protocol strategies (`TreadmillD2Protocol` for `00.D2` and `TreadmillD5Protocol` for `00.D5`) selected automatically via Bluetooth Device Information (`0x180A`).
- 8 sensors: Speed, Distance, Calories, Heart Rate, Inclination, Elapsed Time, Training Status, and diagnostic Connection Status (`disconnected`, `connecting`, `sleeping`, `connected`, `autonomous_running`).
- Revision-aware controls (`Stop` button, `Target inclination`, and `Bluetooth connection` switch on `00.D2`; additional `Start / Resume`, `Pause`, and `Target speed` controls on `00.D5`).
- Automatic main console panel unlock (`CMD_SET_KEY_LOCK`) upon initialization and after workout stop on `00.D2` hardware.
- Translations for 11 languages: English (`en`), Polish (`pl`), German (`de`), French (`fr`), Spanish (`es`), Italian (`it`), Dutch (`nl`), Portuguese (`pt`), Czech (`cs`), Ukrainian (`uk`), and Russian (`ru`).
- Protocol technical reference (`docs/PROTOCOL.md`) and HACS / Hassfest validation workflows.

[0.5.1]: https://github.com/d-lebed/ha-iconsole/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/d-lebed/ha-iconsole/releases/tag/v0.5.0
