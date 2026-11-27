"""Base protocol abstraction and ChangYow frame encoding/decoding."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..const import STARTER


def calc_checksum(data: bytes | bytearray) -> int:
    """Calculate 8-bit additive checksum for a ChangYow frame."""
    return sum(data) & 0xFF


def build_packet(action: int, payload: list[int] | bytes) -> bytes:
    """Build a ChangYow frame: 0xF0, action, (+1 encoded payload), checksum."""
    encoded = [(b + 1) & 0xFF for b in payload]
    body = bytes([STARTER, action & 0xFF, *encoded])
    return body + bytes([calc_checksum(body)])


def decode_packet(raw: bytes | bytearray) -> tuple[int, list[int]] | None:
    """Verify checksum and decode a ChangYow frame into (response_code, payload)."""
    if len(raw) < 4 or raw[0] != STARTER:
        return None
    if calc_checksum(raw[:-1]) != raw[-1]:
        return None
    resp_code = raw[1]
    decoded = [(b - 1) & 0xFF for b in raw[2:-1]]
    return resp_code, decoded


@dataclass(frozen=True, slots=True)
class TreadmillLimits:
    """Hardware speed and inclination limits reported by 0xB1."""

    min_speed: float
    max_speed: float
    min_incline: float
    max_incline: float


@dataclass(frozen=True, slots=True)
class TreadmillTelemetry:
    """Decoded workout status frame reported by 0xB2."""

    duration_s: int
    distance_m: int
    calories_kcal: int
    heart_rate_bpm: int
    speed_kmh: float
    incline_pct: float
    raw_state: int
    warmup_state: int


class TreadmillProtocol(ABC):
    """Abstract base strategy for a ChangYow treadmill protocol revision."""

    supports_start_pause: bool = False
    supports_stop: bool = False
    supports_target_incline: bool = False
    supports_target_speed: bool = False
    requires_disconnect_on_stop: bool = False

    @abstractmethod
    def candidate_lengths(self, resp_code: int) -> tuple[int, ...]:
        """Return valid wire frame lengths for a given response opcode."""

    @abstractmethod
    def build_init_packets(self, cid: int, mid: int) -> list[bytes]:
        """Return initialization handshake packets."""

    @abstractmethod
    def build_status_poll(self, cid: int, mid: int) -> bytes:
        """Return the 500ms telemetry poll packet (0xA2)."""

    def build_unlock_packets(self, cid: int, mid: int) -> list[bytes]:
        """Return packets to unlock physical console keys after stop (if applicable)."""
        return []

    def build_countdown_confirm_packets(
        self, cid: int, mid: int, telemetry: TreadmillTelemetry
    ) -> list[bytes]:
        """Return packets to confirm workout start after countdown finishes."""
        return []

    @abstractmethod
    def build_start_packets(self, cid: int, mid: int, is_paused: bool) -> list[bytes]:
        """Return packets to start or resume a workout."""

    @abstractmethod
    def build_pause_packets(self, cid: int, mid: int) -> list[bytes]:
        """Return packets to pause a workout."""

    @abstractmethod
    def build_stop_packets(self, cid: int, mid: int) -> list[bytes]:
        """Return packets to stop and reset a workout."""

    @abstractmethod
    def build_incline_packets(self, cid: int, mid: int, incline: int) -> list[bytes]:
        """Return packets to set target inclination."""

    @abstractmethod
    def build_speed_packets(self, cid: int, mid: int, speed_kmh: float) -> list[bytes]:
        """Return packets to set target speed."""

    @abstractmethod
    def parse_limits(self, payload: list[int]) -> TreadmillLimits | None:
        """Parse a decoded 0xB1 limits payload."""

    @abstractmethod
    def parse_status(self, payload: list[int]) -> TreadmillTelemetry | None:
        """Parse a decoded 0xB2 workout status payload."""

    @abstractmethod
    def parse_control_state(self, payload: list[int]) -> int | None:
        """Parse a decoded 0xB5 control state payload."""
