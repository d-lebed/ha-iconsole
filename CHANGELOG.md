# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.4] - 2026-11-27

### Changed
- **Safety (`00.D5`)**: Disabled all unverified workout and motor control writes on `00.D5` consoles (`Start / Resume`, `Pause`, `Stop`, `Target inclination`, `Target speed`, and state/mode writes during initialization) so `00.D5` operates in read-only telemetry mode until confirmed on physical `00.D5` hardware (tracked in [Issue #1](https://github.com/d-lebed/ha-iconsole/issues/1); draft control code preserved on the `feat/d5-controls` branch).
- Verified `00.D2` controls (`Stop` button and `Target inclination`) and all telemetry sensors remain unchanged.

## [0.5.3] - 2026-11-24

### Changed
- Wrapped the `Installation` section in `README.md` with `ha-marketplace:exclude` markers so Home Assistant Marketplace hides redundant install instructions while GitHub keeps showing them.

### Removed
- Removed unused duplicate `custom_components/iconsole/icon.png` (kept `custom_components/iconsole/brand/icon.png`) and unused `custom_components/iconsole/strings.json` (custom integrations load `translations/en.json`).

## [0.5.2] - 2026-11-22

### Changed
- Enabled `zip_release` (`iconsole.zip`) in `hacs.json` and added a GitHub Actions workflow (`.github/workflows/release.yml`) to automatically build and attach `iconsole.zip` to published releases so Home Assistant Marketplace and GitHub track download counts.

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

[0.5.4]: https://github.com/d-lebed/ha-iconsole/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/d-lebed/ha-iconsole/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/d-lebed/ha-iconsole/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/d-lebed/ha-iconsole/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/d-lebed/ha-iconsole/releases/tag/v0.5.0
