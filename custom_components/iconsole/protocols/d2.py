"""Protocol implementation for classic 00.D2 ChangYow treadmills."""

from __future__ import annotations

from ..const import (
    CMD_ACK,
    CMD_GET_MAX_LEVEL,
    CMD_GET_STATUS,
    CMD_SET_CONTROL_STATE,
    CMD_SET_INCLINE,
    CMD_SET_KEY_LOCK,
    CMD_SET_MODE,
    CMD_SET_PARAM,
    RESP_ACK,
    RESP_D5_SET_SPEED,
    RESP_GET_MAX_LEVEL,
    RESP_GET_STATUS,
    RESP_MACHINE_CHECK,
    RESP_SET_CONTROL_STATE,
    RESP_SET_INCLINE,
    RESP_SET_KEY_LOCK,
    RESP_SET_MODE,
    RESP_SET_PARAM,
)
from .base import TreadmillLimits, TreadmillProtocol, TreadmillTelemetry, build_packet


class TreadmillD2Protocol(TreadmillProtocol):
    """Protocol strategy for classic 00.D2 treadmills (e.g. ChangYow SI1022)."""

    supports_start_pause = False
    supports_target_speed = False
    requires_disconnect_on_stop = True

    def candidate_lengths(self, resp_code: int) -> tuple[int, ...]:
        return {
            RESP_ACK: (5,),
            RESP_GET_MAX_LEVEL: (10, 14),
            RESP_GET_STATUS: (19, 20),
            RESP_SET_MODE: (12, 13),
            RESP_SET_PARAM: (16, 17),
            RESP_SET_CONTROL_STATE: (6,),
            RESP_D5_SET_SPEED: (25,),
            0xB7: (25,),
            0xB8: (25,),
            0xB9: (25,),
            0xBA: (25,),
            RESP_MACHINE_CHECK: (6,),
            RESP_SET_INCLINE: (8,),
            RESP_SET_KEY_LOCK: (6,),
        }.get(resp_code, ())

    def build_init_packets(self, cid: int, mid: int) -> list[bytes]:
        return [
            build_packet(CMD_ACK, [0x00, 0x00]),
            build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x03]),
            build_packet(CMD_ACK, [cid, mid]),
            build_packet(CMD_GET_MAX_LEVEL, [cid, mid]),
            build_packet(CMD_ACK, [cid, mid]),
            build_packet(CMD_GET_MAX_LEVEL, [cid, mid]),
            build_packet(CMD_ACK, [cid, mid]),
            build_packet(CMD_ACK, [cid, mid]),
            *self.build_unlock_packets(cid, mid),
        ]

    def build_status_poll(self, cid: int, mid: int) -> bytes:
        return build_packet(CMD_GET_STATUS, [cid, mid])

    def build_unlock_packets(self, cid: int, mid: int) -> list[bytes]:
        return [
            build_packet(
                CMD_SET_MODE, [cid, mid, 0x00, 20, 0, 1, 80, 0, 80]
            ),
            build_packet(
                CMD_SET_PARAM,
                [cid, mid, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ),
            build_packet(CMD_SET_KEY_LOCK, [cid, mid, 0x01]),
        ]

    def build_countdown_confirm_packets(
        self, cid: int, mid: int, telemetry: TreadmillTelemetry
    ) -> list[bytes]:
        # Confirm active session after the 3s countdown completes (status transition to 03 04)
        if telemetry.raw_state == 2 and telemetry.warmup_state == 3:
            return [build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x01])]
        return []

    def build_start_packets(self, cid: int, mid: int, is_paused: bool) -> list[bytes]:
        packets: list[bytes] = []
        if not is_paused:
            packets.extend(self.build_unlock_packets(cid, mid))
        packets.append(build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x01]))
        return packets

    def build_pause_packets(self, cid: int, mid: int) -> list[bytes]:
        return [build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x04])]

    def build_stop_packets(self, cid: int, mid: int) -> list[bytes]:
        # Send Stop (0x02) followed by 2x Reset (0x03)
        return [
            build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x02]),
            build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x03]),
            build_packet(CMD_SET_CONTROL_STATE, [cid, mid, 0x03]),
        ]

    def build_incline_packets(self, cid: int, mid: int, incline: int) -> list[bytes]:
        return [build_packet(CMD_SET_INCLINE, [cid, mid, incline, 0x63, 0x63])]

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
        if len(payload) < 3:
            return None
        return payload[2]
