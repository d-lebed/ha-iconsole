"""Protocol implementation for newer 00.D5 ChangYow treadmills (read-only telemetry)."""

from __future__ import annotations

from ..const import (
    CMD_ACK,
    CMD_GET_MAX_LEVEL,
    CMD_GET_STATUS,
    RESP_ACK,
    RESP_D5_SET_SPEED,
    RESP_GET_MAX_LEVEL,
    RESP_GET_STATUS,
    RESP_MACHINE_CHECK,
    RESP_SET_CONTROL_STATE,
    RESP_SET_MODE,
    RESP_SET_PARAM,
)
from .base import TreadmillLimits, TreadmillProtocol, TreadmillTelemetry, build_packet


class TreadmillD5Protocol(TreadmillProtocol):
    """Protocol strategy for newer 00.D5 treadmills (prepends length byte to frames).

    Workout and motor control writes (start, pause, stop, incline, speed) are
    intentionally disabled until confirmed on physical 00.D5 hardware.
    """

    supports_start_pause = False
    supports_stop = False
    supports_target_incline = False
    supports_target_speed = False
    requires_disconnect_on_stop = False

    def candidate_lengths(self, resp_code: int) -> tuple[int, ...]:
        return {
            RESP_ACK: (5,),
            RESP_GET_MAX_LEVEL: (11,),
            RESP_GET_STATUS: (19,),
            RESP_SET_MODE: (7,),
            RESP_SET_PARAM: (14,),
            RESP_SET_CONTROL_STATE: (7,),
            RESP_D5_SET_SPEED: (8,),
            0xB8: (7,),
            RESP_MACHINE_CHECK: (6,),
        }.get(resp_code, ())

    def build_init_packets(self, cid: int, mid: int) -> list[bytes]:
        # Read-only handshake and hardware limits query; state/mode writes are
        # disabled pending verification on a real 00.D5 console.
        return [
            build_packet(CMD_ACK, [0x00, 0x00]),
            build_packet(CMD_ACK, [cid, mid]),
            build_packet(CMD_GET_MAX_LEVEL, [0x02, cid, mid]),
        ]

    def build_status_poll(self, cid: int, mid: int) -> bytes:
        return build_packet(CMD_GET_STATUS, [0x02, cid, mid])

    def build_start_packets(self, cid: int, mid: int, is_paused: bool) -> list[bytes]:
        return []

    def build_pause_packets(self, cid: int, mid: int) -> list[bytes]:
        return []

    def build_stop_packets(self, cid: int, mid: int) -> list[bytes]:
        return []

    def build_incline_packets(self, cid: int, mid: int, incline: int) -> list[bytes]:
        return []

    def build_speed_packets(self, cid: int, mid: int, speed_kmh: float) -> list[bytes]:
        return []

    def parse_limits(self, payload: list[int]) -> TreadmillLimits | None:
        if len(payload) < 8:
            return None
        return TreadmillLimits(
            min_speed=float(payload[3]),
            max_speed=float(payload[4]),
            min_incline=float(payload[6]),
            max_incline=float(payload[7]),
        )

    def parse_status(self, payload: list[int]) -> TreadmillTelemetry | None:
        if len(payload) < 15:
            return None
        return TreadmillTelemetry(
            duration_s=payload[4] * 60 + payload[3],
            distance_m=(payload[5] * 100 + payload[6]) * 10,
            calories_kcal=payload[7] * 100 + payload[8],
            heart_rate_bpm=payload[9] * 100 + payload[10],
            speed_kmh=round((payload[11] * 100 + payload[12]) / 10.0, 1),
            incline_pct=float(payload[13]),
            raw_state=payload[14],
            warmup_state=payload[15] if len(payload) >= 16 else 0,
        )

    def parse_control_state(self, payload: list[int]) -> int | None:
        if len(payload) < 4:
            return None
        return payload[3]
