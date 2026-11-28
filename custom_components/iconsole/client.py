"""BLE client for iConsole+ / ChangYow treadmills (0xFFF0 and ISSC)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import close_stale_connections, establish_connection

from .const import (
    CMD_ACK,
    CONN_AUTONOMOUS_RUNNING,
    CONN_CONNECTED,
    CONN_CONNECTING,
    CONN_DISCONNECTED,
    CONN_SLEEPING,
    DIS_HW_REV_UUID,
    DIS_MANUFACTURER_UUID,
    DIS_MODEL_UUID,
    DIS_SERIAL_UUID,
    DIS_SERVICE_UUID,
    DIS_SW_REV_UUID,
    FFF1_NOTIFY_UUID,
    FFF2_WRITE_UUID,
    ISSC_NOTIFY_UUID,
    ISSC_WRITE_UUID,
    KEY_CALORIES,
    KEY_CONNECTION_STATUS,
    KEY_DISTANCE,
    KEY_HEART_RATE,
    KEY_INCLINE,
    KEY_SPEED,
    KEY_TARGET_INCLINE,
    KEY_TARGET_SPEED,
    KEY_TIME_ELAPSED,
    KEY_TRAINING_STATUS,
    RESP_ACK,
    RESP_GET_MAX_LEVEL,
    RESP_GET_STATUS,
    RESP_MACHINE_CHECK,
    RESP_SET_CONTROL_STATE,
    RESP_SET_KEY_LOCK,
    STARTER,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_STOPPED,
)
from .protocols import (
    TreadmillProtocol,
    TreadmillReadOnlyProtocol,
    build_packet,
    decode_packet,
    get_protocol,
)

_LOGGER = logging.getLogger(__name__)

_DIS_CHAR_MAP = {
    "manufacturer": DIS_MANUFACTURER_UUID,
    "model": DIS_MODEL_UUID,
    "serial_number": DIS_SERIAL_UUID,
    "hw_version": DIS_HW_REV_UUID,
    "sw_version": DIS_SW_REV_UUID,
}


def find_changyow_chars(
    cli: BleakClient,
) -> tuple[BleakGATTCharacteristic, BleakGATTCharacteristic] | None:
    """Locate (notify_char, write_char) for ChangYow / iConsole+ services."""
    for svc in cli.services:
        suuid = svc.uuid.lower()
        if "fff0" in suuid or suuid.startswith("49535343-fe7d"):
            notify_char: BleakGATTCharacteristic | None = None
            write_char: BleakGATTCharacteristic | None = None
            for ch in svc.characteristics:
                cuuid = ch.uuid.lower()
                props = [p.lower() for p in getattr(ch, "properties", [])]
                if (
                    "fff1" in cuuid or cuuid.startswith("49535343-1e4d")
                ) and "notify" in props:
                    notify_char = ch
                elif ("fff2" in cuuid or cuuid.startswith("49535343-8841")) and (
                    "write" in props or "write-without-response" in props
                ):
                    write_char = ch
            if notify_char and write_char:
                return notify_char, write_char

    notify_char = cli.services.get_characteristic(
        FFF1_NOTIFY_UUID
    ) or cli.services.get_characteristic(ISSC_NOTIFY_UUID)
    write_char = cli.services.get_characteristic(
        FFF2_WRITE_UUID
    ) or cli.services.get_characteristic(ISSC_WRITE_UUID)
    if notify_char and write_char:
        return notify_char, write_char

    return None


async def read_device_info(cli: BleakClient) -> dict[str, str]:
    """Read Device Information Service (0x180A) and strip trailing null bytes."""
    info: dict[str, str] = {}
    try:
        srv = cli.services.get_service(DIS_SERVICE_UUID)
    except Exception:
        srv = None

    if srv:
        for key, uuid in _DIS_CHAR_MAP.items():
            if char := srv.get_characteristic(uuid):
                try:
                    raw = await cli.read_gatt_char(char)
                    cleaned = (
                        raw.decode("utf-8", errors="ignore").replace("\x00", "").strip()
                    )
                    if cleaned:
                        info[key] = cleaned
                except Exception as err:
                    _LOGGER.debug("Failed to read DIS %s (%s): %s", key, uuid, err)

    return info


class IConsoleClient:
    """Manages BLE connection, initialization, polling, and commands for an iConsole+ treadmill."""

    def __init__(
        self,
        address: str,
        name: str,
        ble_device: BLEDevice | None = None,
        device_info: dict[str, str] | None = None,
        on_update: Callable[[dict[str, Any]], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        on_protocol_change: Callable[[], None] | None = None,
    ) -> None:
        self.address = address
        self.name = name
        self._device = ble_device
        self.device_info: dict[str, str] = dict(
            device_info
            or {
                "manufacturer": "ChangYow",
                "model": "iConsole+",
            }
        )
        self._on_update = on_update
        self._on_disconnect_cb = on_disconnect
        self._on_protocol_change = on_protocol_change

        self.client_id: int = 0x00
        self.meter_id: int | None = None
        self.protocol: TreadmillProtocol = get_protocol(None)
        self._parse_serial_ids(
            self.device_info.get("serial_number", ""), notify=False
        )

        self._cli: BleakClient | None = None
        self._notify_char: BleakGATTCharacteristic | None = None
        self._write_char: BleakGATTCharacteristic | None = None

        self.need_connect: bool = True
        self._connecting: bool = False
        self._poll_task: asyncio.Task[None] | None = None
        self._cmd_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._rx_buf = bytearray()
        self._got_any_rx = False
        self._got_status_rx = False
        self._last_rx_time: float = 0.0
        self._console_awake: bool = False
        self._use_write_response: bool | None = None
        self._workout_state = 0
        self._ready_to_start = False
        self.limits_ready = asyncio.Event()

        self.min_speed = 1.0
        self.max_speed = 16.0
        self.min_incline = 0.0
        self.max_incline = 15.0

        self.data: dict[str, Any] = {
            KEY_SPEED: 0.0,
            KEY_DISTANCE: 0,
            KEY_CALORIES: 0,
            KEY_HEART_RATE: 0,
            KEY_INCLINE: 0.0,
            KEY_TIME_ELAPSED: 0,
            KEY_TRAINING_STATUS: STATUS_IDLE,
            KEY_CONNECTION_STATUS: CONN_DISCONNECTED,
            KEY_TARGET_INCLINE: 0.0,
            KEY_TARGET_SPEED: 0.0,
        }

    def _parse_serial_ids(self, serial_number: str, *, notify: bool = True) -> None:
        if "." in serial_number:
            parts = serial_number.split(".")
            try:
                self.client_id = int(parts[0], 16) & 0xFF
                meter_id = int(parts[1], 16) & 0xFF
            except ValueError:
                return
            self._update_meter_id(meter_id, notify=notify)

    def _update_meter_id(self, meter_id: int, *, notify: bool = True) -> None:
        if meter_id == self.meter_id:
            return
        prev_protocol_type = type(self.protocol)
        self.meter_id = meter_id
        self.protocol = get_protocol(meter_id)
        if not self.device_info.get("serial_number"):
            self.device_info["serial_number"] = f"{self.client_id:02X}.{meter_id:02X}"
        if isinstance(self.protocol, TreadmillReadOnlyProtocol):
            _LOGGER.info(
                "IConsole: Unverified MeterID %02X.%02X on %s; using read-only protocol",
                self.client_id,
                meter_id,
                self.name,
            )
        if (
            notify
            and type(self.protocol) is not prev_protocol_type
            and self._on_protocol_change
        ):
            self._on_protocol_change()

    @property
    def _effective_mid(self) -> int:
        return self.meter_id if self.meter_id is not None else 0x00

    @property
    def is_connected(self) -> bool:
        return self._cli is not None and self._cli.is_connected

    @property
    def is_awake(self) -> bool:
        return self.is_connected and self._console_awake

    @property
    def is_connecting(self) -> bool:
        return self._connecting

    def _set_connection_status(self, status: str) -> None:
        if self.data.get(KEY_CONNECTION_STATUS) != status:
            self.data[KEY_CONNECTION_STATUS] = status
            if self._on_update:
                self._on_update(self.data)

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        self._device = ble_device
        if ble_device.name:
            self.name = ble_device.name

    async def connect(self) -> None:
        """Connect to the treadmill and start the ChangYow handshake and polling loop."""
        if not self.need_connect or self.is_connected or self._connecting:
            return

        if self._device is None or not getattr(self._device, "details", None):
            raise BleakError(f"{self.name} ({self.address}) is offline / not advertising")

        self._connecting = True
        self._set_connection_status(CONN_CONNECTING)
        try:
            await close_stale_connections(self._device)
            _LOGGER.debug("IConsole: Connecting to %s (%s)", self.name, self.address)

            self._cli = await establish_connection(
                client_class=BleakClient,
                device=self._device,
                name=self.name,
                disconnected_callback=self._handle_ble_disconnect,
            )

            try:
                dis = await read_device_info(self._cli)
                if dis:
                    self.device_info.update(dis)
                    self._parse_serial_ids(self.device_info.get("serial_number", ""))

                chars = find_changyow_chars(self._cli)
                if chars is None:
                    raise BleakError(
                        f"ChangYow service (0xFFF0 / ISSC) not found on {self.name}"
                    )

                self._notify_char, self._write_char = chars
                self._rx_buf.clear()
                self._got_any_rx = False
                self._got_status_rx = False
                self._last_rx_time = 0.0
                self._console_awake = False
                self._use_write_response = None
                self.limits_ready.clear()
                self._set_connection_status(CONN_SLEEPING)

                for svc in self._cli.services:
                    if svc.uuid.lower().startswith(("00001800", "00001801", "0000180a")):
                        continue
                    for ch in svc.characteristics:
                        props_l = [p.lower() for p in getattr(ch, "properties", [])]
                        if (
                            ("notify" in props_l or "indicate" in props_l)
                            and ch.uuid != self._notify_char.uuid
                        ):
                            try:
                                await self._cli.start_notify(ch, self._on_notify)
                            except Exception as err:
                                _LOGGER.debug(
                                    "IConsole: Could not subscribe to secondary char %s: %s",
                                    ch.uuid,
                                    err,
                                )

                await self._cli.start_notify(self._notify_char, self._on_notify)
                _LOGGER.info(
                    "IConsole: Connected to %s (%s), notify=%s, write=%s, IDs=%s",
                    self.name,
                    self.address,
                    self._notify_char.uuid,
                    self._write_char.uuid,
                    (
                        f"{self.client_id:02X}.{self.meter_id:02X}"
                        if self.meter_id is not None
                        else "unknown"
                    ),
                )

                self._poll_task = asyncio.create_task(self._poll_loop())
                try:
                    await asyncio.wait_for(self.limits_ready.wait(), timeout=2.5)
                except TimeoutError:
                    pass

                if self._on_update:
                    self._on_update(self.data)
            except Exception:
                if self._cli and self._cli.is_connected:
                    await self._cli.disconnect()
                self._cli = None
                self._set_connection_status(CONN_DISCONNECTED)
                raise
        except Exception:
            self._set_connection_status(CONN_DISCONNECTED)
            raise
        finally:
            self._connecting = False

    async def disconnect(self) -> None:
        """Disconnect from the treadmill and stop background polling."""
        self.need_connect = False
        self._stop_poll_task()
        self._console_awake = False
        cli = self._cli
        self._cli = None
        if cli and cli.is_connected:
            await cli.disconnect()
        self.data[KEY_CONNECTION_STATUS] = CONN_DISCONNECTED
        if self._on_disconnect_cb:
            self._on_disconnect_cb()

    def _stop_poll_task(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None

    def _handle_ble_disconnect(self, _cli: BleakClient) -> None:
        _LOGGER.info("IConsole: %s (%s) disconnected", self.name, self.address)
        self._stop_poll_task()
        self._console_awake = False
        self._cli = None
        self.data[KEY_CONNECTION_STATUS] = CONN_DISCONNECTED
        if self._on_disconnect_cb:
            self._on_disconnect_cb()

    async def _write_raw(self, packet: bytes) -> None:
        if not self.is_connected or self._cli is None or self._write_char is None:
            return
        props = [p.lower() for p in getattr(self._write_char, "properties", [])]
        if self._use_write_response is not None:
            response = self._use_write_response
        else:
            response = "write" in props and "write-without-response" not in props
        _LOGGER.debug(
            "IConsole SND (resp=%s): %s", response, packet.hex(" ").upper()
        )
        await self._cli.write_gatt_char(self._write_char, packet, response=response)

    async def _run_init_sequence(self) -> None:
        """Execute the protocol-specific initialization handshake."""
        for pkt in self.protocol.build_init_packets(self.client_id, self._effective_mid):
            if not self.is_connected:
                return
            await self._write_raw(pkt)
            await asyncio.sleep(0.35)

    def _build_status_poll_packet(self) -> bytes:
        return self.protocol.build_status_poll(self.client_id, self._effective_mid)

    async def _poll_loop(self) -> None:
        """Background loop that detects console sleep/wake and runs handshake + status polling."""
        try:
            probe_step = 0
            while self.is_connected:
                # 1. Wait for console to respond (probe with GET_STATUS and ACK packets)
                if not self._console_awake:
                    self._got_any_rx = False
                    cid, mid = self.client_id, self.meter_id
                    if mid is None:
                        probe_pkt = build_packet(CMD_ACK, [0x00, 0x00])
                    elif probe_step % 3 == 0:
                        probe_pkt = self._build_status_poll_packet()
                    elif probe_step % 3 == 1:
                        probe_pkt = build_packet(CMD_ACK, [0x00, 0x00])
                    else:
                        probe_pkt = build_packet(CMD_ACK, [cid, mid])
                    probe_step += 1

                    await self._write_raw(probe_pkt)
                    await asyncio.sleep(0.5)

                    if not self._got_any_rx:
                        self._set_connection_status(CONN_SLEEPING)
                        continue

                    if self._workout_state == 1 or self.data.get(KEY_SPEED, 0.0) > 0:
                        _LOGGER.info(
                            "IConsole: Console on %s is already running workout; skipping reset init",
                            self.name,
                        )
                    else:
                        _LOGGER.info(
                            "IConsole: Console on %s woke up; running initialization sequence",
                            self.name,
                        )
                        await self._run_init_sequence()

                    self._console_awake = True
                    self._last_rx_time = time.monotonic()
                    self._set_connection_status(CONN_CONNECTED)

                # 2. Active polling while console is awake
                await asyncio.sleep(0.5)
                if not self.is_connected:
                    break

                # Detect if console stopped responding (went to sleep or started autonomous run)
                if (
                    self._last_rx_time > 0
                    and (time.monotonic() - self._last_rx_time) > 5.0
                ):
                    new_conn_status = (
                        CONN_AUTONOMOUS_RUNNING
                        if self._workout_state == 1 or self.data.get(KEY_SPEED, 0.0) > 0
                        else CONN_SLEEPING
                    )
                    _LOGGER.info(
                        "IConsole: Console on %s stopped responding (no RX for 5s); status=%s",
                        self.name,
                        new_conn_status,
                    )
                    self._console_awake = False
                    self.data[KEY_SPEED] = 0.0
                    self.data[KEY_TRAINING_STATUS] = STATUS_IDLE
                    self.data[KEY_CONNECTION_STATUS] = new_conn_status
                    if self._on_update:
                        self._on_update(self.data)
                    continue

                if not self._cmd_queue.empty():
                    pkt = await self._cmd_queue.get()
                    await self._write_raw(pkt)
                else:
                    await self._write_raw(self._build_status_poll_packet())
        except asyncio.CancelledError:
            return
        except Exception as err:
            _LOGGER.debug("IConsole poll loop ended: %s", err)

    def _on_notify(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        self._got_any_rx = True
        self._last_rx_time = time.monotonic()
        _LOGGER.debug("IConsole RCV: %s", bytes(data).hex(" ").upper())
        self._rx_buf.extend(data)

        while len(self._rx_buf) >= 4:
            if self._rx_buf[0] != STARTER:
                idx = self._rx_buf.find(STARTER)
                if idx == -1:
                    self._rx_buf.clear()
                    return
                del self._rx_buf[:idx]
                if len(self._rx_buf) < 4:
                    return

            resp_code = self._rx_buf[1]
            candidate_lens = self.protocol.candidate_lengths(resp_code)
            if not candidate_lens:
                del self._rx_buf[0]
                continue

            matched = False
            for expected_len in candidate_lens:
                if len(self._rx_buf) < expected_len:
                    continue
                frame = bytes(self._rx_buf[:expected_len])
                decoded = decode_packet(frame)
                if decoded is not None:
                    del self._rx_buf[:expected_len]
                    self._handle_frame(decoded[0], decoded[1])
                    matched = True
                    break

            if not matched:
                if len(self._rx_buf) < max(candidate_lens):
                    return
                del self._rx_buf[0]

    def _handle_frame(self, resp_code: int, payload: list[int]) -> None:
        if resp_code in (RESP_ACK, RESP_MACHINE_CHECK) and len(payload) >= 2:
            self.client_id = payload[0]
            self._update_meter_id(payload[1])

        elif resp_code == RESP_GET_MAX_LEVEL:
            limits = self.protocol.parse_limits(payload)
            if limits is not None:
                if limits.max_speed > 0:
                    self.min_speed = limits.min_speed
                    self.max_speed = limits.max_speed
                if limits.max_incline > 0:
                    self.min_incline = limits.min_incline
                    self.max_incline = limits.max_incline
                self.limits_ready.set()

        elif resp_code == RESP_SET_KEY_LOCK and len(payload) >= 3:
            key_lock_state = payload[2]
            _LOGGER.debug("IConsole: KeyLock state reported as %s", key_lock_state)
            if key_lock_state == 2:
                unlock_pkts = self.protocol.build_unlock_packets(
                    self.client_id, self._effective_mid
                )
                if unlock_pkts:
                    _LOGGER.info(
                        "IConsole: Treadmill locked console after stop; sending unlock sequence"
                    )
                    for pkt in unlock_pkts:
                        self._cmd_queue.put_nowait(pkt)

        elif resp_code == RESP_SET_CONTROL_STATE:
            ctrl_state = self.protocol.parse_control_state(payload)
            if ctrl_state is not None:
                _LOGGER.debug("IConsole: ControlState reported as %s", ctrl_state)
                if ctrl_state == 1:
                    self._workout_state = 1
                    self.data[KEY_TRAINING_STATUS] = STATUS_RUNNING
                elif ctrl_state == 4:
                    self._workout_state = 2
                    self.data[KEY_TRAINING_STATUS] = STATUS_PAUSED
                elif ctrl_state in (2, 3):
                    self._workout_state = 0
                    self.data[KEY_SPEED] = 0.0
                    self.data[KEY_TRAINING_STATUS] = STATUS_STOPPED
                if self._on_update:
                    self._on_update(self.data)

        elif resp_code == RESP_GET_STATUS:
            telemetry = self.protocol.parse_status(payload)
            if telemetry is None:
                return
            self._got_status_rx = True

            if not self._ready_to_start:
                confirm_pkts = self.protocol.build_countdown_confirm_packets(
                    self.client_id, self._effective_mid, telemetry
                )
                if confirm_pkts:
                    self._ready_to_start = True
                    _LOGGER.info(
                        "IConsole: Countdown finished; sending startWorkout confirmation"
                    )
                    for pkt in confirm_pkts:
                        self._cmd_queue.put_nowait(pkt)
            elif telemetry.raw_state == 0 and telemetry.speed_kmh == 0:
                self._ready_to_start = False

            if telemetry.raw_state == 2 or telemetry.speed_kmh > 0:
                self._workout_state = 1
                t_status = STATUS_RUNNING
            elif telemetry.raw_state == 3:
                self._workout_state = 2
                t_status = STATUS_PAUSED
            else:
                self._workout_state = 0
                t_status = STATUS_IDLE

            new_data = {
                KEY_SPEED: telemetry.speed_kmh,
                KEY_DISTANCE: telemetry.distance_m,
                KEY_CALORIES: telemetry.calories_kcal,
                KEY_HEART_RATE: telemetry.heart_rate_bpm,
                KEY_INCLINE: telemetry.incline_pct,
                KEY_TIME_ELAPSED: telemetry.duration_s,
                KEY_TRAINING_STATUS: t_status,
                KEY_CONNECTION_STATUS: CONN_CONNECTED,
                KEY_TARGET_INCLINE: telemetry.incline_pct,
                KEY_TARGET_SPEED: telemetry.speed_kmh,
            }
            self.limits_ready.set()

            if new_data != self.data:
                self.data.update(new_data)
                if self._on_update:
                    self._on_update(self.data)

    async def async_start_workout(self) -> None:
        """Send Start/Resume workout packets."""
        for pkt in self.protocol.build_start_packets(
            self.client_id, self._effective_mid, is_paused=(self._workout_state == 2)
        ):
            await self._cmd_queue.put(pkt)

    async def async_pause_workout(self) -> None:
        """Send Pause workout packets."""
        for pkt in self.protocol.build_pause_packets(
            self.client_id, self._effective_mid
        ):
            await self._cmd_queue.put(pkt)

    async def async_stop_workout(self) -> None:
        """Stop the workout using the protocol strategy."""
        stop_pkts = self.protocol.build_stop_packets(
            self.client_id, self._effective_mid
        )
        if not stop_pkts:
            return
        if not self.protocol.requires_disconnect_on_stop:
            for pkt in stop_pkts:
                await self._cmd_queue.put(pkt)
            return

        for pkt in stop_pkts:
            await self._write_raw(pkt)
            await asyncio.sleep(0.15)
        await asyncio.sleep(0.05)

        cli = self._cli
        if cli and cli.is_connected:
            _LOGGER.info(
                "IConsole: Closing BLE session to complete stop sequence; will auto-reconnect"
            )
            await cli.disconnect()
            asyncio.create_task(self._reconnect_after_stop())

    async def _reconnect_after_stop(self) -> None:
        """Reconnect to the treadmill after the stop-disconnect sequence."""
        await asyncio.sleep(3.0)
        if self.need_connect and not self.is_connected and not self.is_connecting:
            try:
                await self.connect()
            except Exception as err:
                _LOGGER.debug("IConsole: Reconnect after stop failed: %s", err)

    async def async_set_incline(self, value: float) -> None:
        """Set target inclination level."""
        incline_int = max(0, min(int(round(value)), int(self.max_incline)))
        pkts = self.protocol.build_incline_packets(
            self.client_id, self._effective_mid, incline_int
        )
        if not pkts:
            return
        for pkt in pkts:
            await self._cmd_queue.put(pkt)
        self.data[KEY_TARGET_INCLINE] = float(incline_int)
        if self._on_update:
            self._on_update(self.data)

    async def async_set_speed(self, value: float) -> None:
        """Set target speed in km/h."""
        spd = max(0.0, min(round(value, 1), self.max_speed))
        pkts = self.protocol.build_speed_packets(
            self.client_id, self._effective_mid, spd
        )
        if not pkts:
            return
        for pkt in pkts:
            await self._cmd_queue.put(pkt)
        self.data[KEY_TARGET_SPEED] = spd
        if self._on_update:
            self._on_update(self.data)
