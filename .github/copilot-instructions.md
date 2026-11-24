# GitHub Copilot Instructions for `ha-iconsole`

Read [AGENTS.md](../AGENTS.md) and [docs/PROTOCOL.md](../docs/PROTOCOL.md) before modifying the codebase.

## Key Conventions

- **Home Assistant Standards**:
  - Target Python 3.12+ and Home Assistant 2024.4+.
  - Use modern type annotations (`from __future__ import annotations`, `type IConsoleConfigEntry = ConfigEntry[IConsoleRuntimeData]`).
  - Keep `custom_components/iconsole/manifest.json` strictly valid for `hassfest` (`domain`, `name`, then alphabetical keys).
  - Update `translations/en.json` and the other locale files in `translations/` together whenever adding or renaming entities or states.
- **Releases**:
  - Never overwrite or force-push an existing release tag. Always bump `version` in `custom_components/iconsole/manifest.json`, document changes in `CHANGELOG.md`, and publish a new SemVer tag/release.
- **ChangYow BLE Protocol**:
  - Maintain strict separation between `00.D2` (`TreadmillD2Protocol`) and `00.D5` (`TreadmillD5Protocol`) packet formats and entity sets.
  - On `00.D2` hardware, always use `WriteWithoutResponse` (`response=False`) on `0000fff2-0000-1000-8000-00805f9b34fb` and unlock the console panel using `CMD_SET_KEY_LOCK` (`0xAF` with payload `0x01` -> wire `0x02`).
