# ChangYow / iConsole+ BLE Protocol Reference

This document summarizes the proprietary Bluetooth Low Energy protocol used by **ChangYow (`iConsole+`)** treadmill consoles (such as `ChangYow SI1022`), reconstructed from:
- Community protocol research in [Nickwasused/iconsoleplus-app-diff](https://github.com/Nickwasused/iconsoleplus-app-diff)
- BLE packet captures and driver implementation in [cagnulein/qdomyos-zwift](https://github.com/cagnulein/qdomyos-zwift) (`trxappgateusbtreadmill.cpp`)
- Live packet analysis against a **Zipro (`iConsole+0017`, model `SI1022`, serial `00.D2`)** treadmill.

---

## 1. GATT Services & Characteristics

Although `iConsole+` treadmills include the standard FTMS UUID (`0x1826`) in their BLE advertisement payload, their GATT table does **not** contain `0x1826`. Instead, they expose:

1. **Device Information Service (`0x180A`)**:
   - Manufacturer (`0x2A29`): e.g. `ChangYow`
   - Model Number (`0x2A24`): e.g. `SI1022`
   - Serial Number (`0x2A25`): `<ClientID_hex>.<MeterID_hex>`, e.g. `00.D2` (`client_id = 0x00`, `meter_id = 0xD2`) or `00.D5` (`meter_id = 0xD5`).

2. **ChangYow UART Service (`0000fff0-0000-1000-8000-00805f9b34fb`)** *(or ISSC `49535343-fe7d-4ae5-8fa9-9fafd205e455`)*:
   - **Notify Characteristic**: `0000fff1-0000-1000-8000-00805f9b34fb`
   - **Write Characteristic**: `0000fff2-0000-1000-8000-00805f9b34fb`
     - **Important**: Even if the characteristic reports both `write` and `write-without-response` properties, `SI1022` consoles ignore GATT Write-With-Response requests. Commands **must** be sent with `response=False` (`WriteWithoutResponse`).

---

## 2. Packet Framing & `+1` Encoding

Every frame starts with `0xF0` (`STARTER`), followed by an action/response opcode (`0xA0..0xAF` for requests, `0xB0..0xBF` for responses), `+1`-encoded payload bytes, and an 8-bit additive checksum:

```text
+------+--------+-----------------------+----------+
| 0xF0 | Opcode | Encoded Payload (+1)  | Checksum |
+------+--------+-----------------------+----------+
```

- **Encoding payload bytes (`build_packet`)**:
  Each raw byte `b` in the payload is encoded as `(b + 1) & 0xFF`.
  For example, `client_id = 0x00, meter_id = 0xD2` is transmitted on the wire as `0x01, 0xD3`.
- **Decoding payload bytes (`decode_packet`)**:
  Each wire byte `w` (between the opcode and checksum) is decoded as `(w - 1) & 0xFF`.
- **Checksum (`calc_checksum`)**:
  `sum(frame[:-1]) & 0xFF` (the sum of all bytes including `0xF0`, opcode, and encoded payload bytes).

---

## 3. Hardware Revisions: `00.D2` (`TreadmillD2Protocol`) vs `00.D5` (`TreadmillD5Protocol`)

The console's `MeterID` (from the Bluetooth Device Information serial number or the `0xB0` ACK reply) selects the protocol dialect using an explicit allowlist:
- **`0xD2` (`00.D2`)** — Classic treadmill revision (`TreadmillD2Protocol`). Live-verified on **Zipro `iConsole+0017` (`SI1022`, serial `00.D2`)** for telemetry, `Stop`, and `Target inclination`.
- **`0xD5` (`00.D5`)** — Newer D5 treadmill revision (`TreadmillD5Protocol`). **Read-only telemetry mode** in `main`: only `CMD_ACK` (`0xA0`), `CMD_GET_MAX_LEVEL` (`0xA1`), and `CMD_GET_STATUS` (`0xA2`) are sent. All belt/workout write commands (`Start`, `Pause`, `Stop`, `Incline`, `Speed`) and state/mode initialization writes are disabled until verified on physical `00.D5` hardware (tracked in [Issue #1](https://github.com/d-lebed/ha-iconsole/issues/1)).
- **Unknown / unreadable `MeterID`** — Fail-safe read-only fallback (`TreadmillReadOnlyProtocol`). When DIS cannot be read or an unrecognized `MeterID` is reported, no write commands are sent and no control entities are exposed. If a previously unidentified console later identifies itself as `00.D2`, the integration persists its revision and reloads automatically.

### Key Structural Difference
- On **`00.D2`**, commands do **not** include a length byte after the opcode; the payload starts immediately with `[client_id, meter_id, ...]`.
- On **`00.D5`**, every command and response prepends a `length` byte before `client_id` and `meter_id`: `[length, client_id, meter_id, ...]`.

Because of this, opcode `0xA6` has two different wire formats depending on revision:
- On **`00.D5`** *(documented from community research; write disabled in `main` pending hardware validation)*: `0xA6` (`CMD_D5_SET_SPEED`) is an **8-byte** command (`[0x04, cid, mid, spd_hi, spd_lo]`).
- On **`00.D2`**: `0xA6` is a **25-byte** command containing 10 speed segments for preset programs. Sending an 8-byte `0xA6` packet to a `00.D2` console causes its parser to wait for the remaining 17 bytes, corrupting subsequent packets.

---

## 4. Command & Response Reference (`00.D2`)

| Opcode | Response | Constant | Wire Example (`cid=00, mid=D2`) | Description |
| :---: | :---: | :--- | :--- | :--- |
| `0xA0` | `0xB0` | `CMD_ACK` | `F0 A0 01 01 92` / `F0 A0 01 D3 64` | Handshake / discover `cid` & `mid` |
| `0xA1` | `0xB1` | `CMD_GET_MAX_LEVEL` | `F0 A1 01 D3 65` | Read min/max speed & incline limits |
| `0xA2` | `0xB2` | `CMD_GET_STATUS` | `F0 A2 01 D3 66` | Poll live telemetry (every 500 ms) |
| `0xA3` | `0xB3` | `CMD_SET_MODE` | `F0 A3 01 D3 01 15 01 02 51 01 51 23` | Set workout mode (`0`=QuickStart, `1`=Program, `2`=Interval, `3`=Route) and user profile |
| `0xA4` | `0xB4` | `CMD_SET_PARAM` | `F0 A4 01 D3 01 01 01 01 01 01 01 01 01 01 01 73` | Set target time, distance, calories, pulse, speed, incline, unit |
| `0xA5` | `0xB5` | `CMD_SET_CONTROL_STATE` | `F0 A5 01 D3 <state+1> <sum>` | Control state: raw `1` (`0x02`)=Start, `2` (`0x03`)=Stop, `3` (`0x04`)=Reset, `4` (`0x05`)=Pause |
| `0xAC` | `0xBC` | `CMD_SET_INCLINE` | `F0 AC 01 D3 <inc+1> 64 64 <sum>` | Set live inclination level |
| `0xAF` | `0xBF` | `CMD_SET_KEY_LOCK` | `F0 AF 01 D3 02 75` | Console panel key lock (`0x01`=None/Locked, `0x02`=Unlock, `0x03`=Lock) |

### Telemetry Frame (`0xB2`, 19 bytes on `00.D2`)
Decoded payload indices (`raw_byte - 1`):
- `payload[0]`: `client_id`
- `payload[1]`: `meter_id`
- `payload[2]`: `seconds` (`0..59`)
- `payload[3]`: `minutes` (`duration_s = payload[3] * 60 + payload[2]`)
- `payload[4..5]`: `distance` (`(payload[4] * 100 + payload[5]) * 10` meters)
- `payload[6..7]`: `calories` (`payload[6] * 100 + payload[7]` kcal)
- `payload[8..9]`: `heart_rate` (`payload[8] * 100 + payload[9]` bpm)
- `payload[10..11]`: `speed` (`(payload[10] * 100 + payload[11]) / 10.0` km/h)
- `payload[12]`: `incline` (`%`)
- `payload[13]`: `raw_state` (`0` = Idle/Stopped, `2` = Running/Countdown, `3` = Paused)
- `payload[14]`: `warmup_state` (`1` = 3-second countdown, `3` = active running)

---

## 5. Console State Machine & Key Lock (`0xAF`) on `00.D2`

1. **Initialization & Panel Unlock**:
   When a BLE client sends `F0 A0`, the `00.D2` console enters Bluetooth mode and **locks all physical buttons by default**.
   To unlock the main panel buttons so the user can press `START`, the client must send:
   1. `CMD_SET_MODE` (`0xA3`)
   2. `CMD_SET_PARAM` (`0xA4`)
   3. `CMD_SET_KEY_LOCK` (`0xAF`) with raw value `1` (wire `F0 AF 01 D3 02 75` = Unlock).
   *(Note: Sending raw value `0` (`F0 AF 01 D3 01 74`) or `2` (`F0 AF 01 D3 03 76`) leaves the console panel locked!)*

2. **Re-unlocking After Workout Stop**:
   When the user stops the treadmill from the panel, the console sends notification `F0 BF 01 D3 03 86` (key lock state `2` = Locked). The client must immediately resend `0xA3` + `0xA4` + `0xAF` (`0x01`) so the panel buttons remain unlocked for the next run.

3. **Stopping a Running Workout from BLE**:
   On `00.D2` hardware, stopping the treadmill over BLE requires sending `CMD_SET_CONTROL_STATE` with `0x02` (`Stop`), followed by `0x03` (`Reset`) twice, and immediately closing the BLE GATT connection, which forces the console to end the session and stop the belt.
