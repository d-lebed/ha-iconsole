"""Fail-safe read-only protocol fallback for unknown or unreadable MeterIDs."""

from __future__ import annotations

from ..const import (
    CMD_ACK,
    CMD_GET_MAX_LEVEL,
    CMD_GET_STATUS,
    RESP_ACK,
    RESP_GET_MAX_LEVEL,
    RESP_GET_STATUS,
    RESP_MACHINE_CHECK,
)
from .base import TreadmillLimits, TreadmillProtocol, TreadmillTelemetry, build_packet


class TreadmillReadOnlyProtocol(TreadmillProtocol):
    """Read-only protocol strategy used when MeterID is unknown or unverified.

    Never sends motor, mode, parameter, key-lock, or workout control writes.
    Only sends safe discovery/telemetry queries so unknown consoles cannot
    receive untested write commands.
    """

    supports_start_pause = False
    supports_stop = False
    supports_target_incline = False
    supports_target_speed = False
    requires_disconnect_on_stop = False

    def candidate_lengths(self, resp_code: int) -> tuple[int, ...]:
        return {
            RESP_ACK: (5,),
            RESP_GET_MAX_LEVEL: (10, 11, 14),
            RESP_GET_STATUS: (19, 20),
            RESP_MACHINE_CHECK: (6,),
        }.get(resp_code, ())

    def build_init_packets(self, cid: int, mid: int) -> list[bytes]:
        packets = [build_packet(CMD_ACK, [0x00, 0x00])]
        if mid != 0:
            packets.append(build_packet(CMD_ACK, [cid, mid]))
            packets.append(build_packet(CMD_GET_MAX_LEVEL, [cid, mid]))
        return packets

    def build_status_poll(self, cid: int, mid: int) -> bytes:
        if mid == 0:
            return build_packet(CMD_ACK, [0x00, 0x00])
        return build_packet(CMD_GET_STATUS, [cid, mid])

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
        if len(payload) < 7:
            return None
        return TreadmillLimits(
            min_speed=float(payload[2]),
            max_speed=float(payload[3]),
            min_incline=float(payload[5]),
            max_incline=float(payload[6]),
        )

    def parse_status(self, payload: list[int]) -> TreadmillTelemetry | None:
        if len(payload) < 14:
            return None
        return TreadmillTelemetry(
            duration_s=payload[3] * 60 + payload[2],
            distance_m=(payload[4] * 100 + payload[5]) * 10,
            calories_kcal=payload[6] * 100 + payload[7],
            heart_rate_bpm=payload[8] * 100 + payload[9],
            speed_kmh=round((payload[10] * 100 + payload[11]) / 10.0, 1),
            incline_pct=float(payload[12]),
            raw_state=payload[13],
            warmup_state=payload[14] if len(payload) >= 15 else 0,
        )

    def parse_control_state(self, payload: list[int]) -> int | None:
        return None
