"""Protocol strategies for ChangYow / iConsole+ treadmills."""

from __future__ import annotations

from .base import (
    TreadmillLimits,
    TreadmillProtocol,
    TreadmillTelemetry,
    build_packet,
    calc_checksum,
    decode_packet,
)
from .d2 import TreadmillD2Protocol
from .d5 import TreadmillD5Protocol
from .readonly import TreadmillReadOnlyProtocol

__all__ = [
    "TreadmillD2Protocol",
    "TreadmillD5Protocol",
    "TreadmillLimits",
    "TreadmillProtocol",
    "TreadmillReadOnlyProtocol",
    "TreadmillTelemetry",
    "build_packet",
    "calc_checksum",
    "decode_packet",
    "get_protocol",
]


def get_protocol(meter_id: int | None) -> TreadmillProtocol:
    """Return the protocol strategy matching the treadmill's MeterID.

    Only hardware-verified revisions receive write capabilities. Unknown or
    unreadable revisions default to the read-only protocol.
    """
    if meter_id == 0xD2:
        return TreadmillD2Protocol()
    if meter_id == 0xD5:
        return TreadmillD5Protocol()
    return TreadmillReadOnlyProtocol()
