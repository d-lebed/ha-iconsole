"""Unit tests for ChangYow / iConsole+ protocol framing, dispatch, and safety invariants."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

# Allow importing protocol/const modules without requiring Home Assistant runtime.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if "custom_components" not in sys.modules:
    _cc = types.ModuleType("custom_components")
    _cc.__path__ = [str(_REPO_ROOT / "custom_components")]
    sys.modules["custom_components"] = _cc
if "custom_components.iconsole" not in sys.modules:
    _ic = types.ModuleType("custom_components.iconsole")
    _ic.__path__ = [str(_REPO_ROOT / "custom_components" / "iconsole")]
    sys.modules["custom_components.iconsole"] = _ic

from custom_components.iconsole.const import (  # noqa: E402
    CMD_ACK,
    CMD_GET_MAX_LEVEL,
    CMD_GET_STATUS,
    CMD_SET_CONTROL_STATE,
    CMD_SET_INCLINE,
    CMD_SET_KEY_LOCK,
    STARTER,
)
from custom_components.iconsole.protocols import (  # noqa: E402
    TreadmillD2Protocol,
    TreadmillD5Protocol,
    TreadmillReadOnlyProtocol,
    TreadmillTelemetry,
    build_packet,
    calc_checksum,
    decode_packet,
    get_protocol,
)

_READ_ONLY_INIT_OPCODES = {CMD_ACK, CMD_GET_MAX_LEVEL}
_READ_ONLY_POLL_OPCODES = {CMD_ACK, CMD_GET_STATUS}


class TestFrameCodec(unittest.TestCase):
    """Verify ChangYow 0xF0 +1 encoding, checksums, and decoding."""

    def test_known_wire_vectors(self) -> None:
        self.assertEqual(build_packet(CMD_ACK, [0x00, 0x00]), bytes.fromhex("F0 A0 01 01 92"))
        self.assertEqual(build_packet(CMD_ACK, [0x00, 0xD2]), bytes.fromhex("F0 A0 01 D3 64"))
        self.assertEqual(
            build_packet(CMD_GET_MAX_LEVEL, [0x00, 0xD2]), bytes.fromhex("F0 A1 01 D3 65")
        )
        self.assertEqual(
            build_packet(CMD_GET_STATUS, [0x00, 0xD2]), bytes.fromhex("F0 A2 01 D3 66")
        )
        self.assertEqual(
            build_packet(CMD_SET_KEY_LOCK, [0x00, 0xD2, 0x01]),
            bytes.fromhex("F0 AF 01 D3 02 75"),
        )

    def test_decode_roundtrip(self) -> None:
        raw = build_packet(0xB2, [0x00, 0xD2, 30, 5, 1, 25])
        decoded = decode_packet(raw)
        self.assertEqual(decoded, (0xB2, [0x00, 0xD2, 30, 5, 1, 25]))

    def test_decode_rejects_invalid_frames(self) -> None:
        valid = bytearray(build_packet(CMD_ACK, [0x00, 0xD2]))
        # Bad checksum
        corrupt = bytearray(valid)
        corrupt[-1] ^= 0x01
        self.assertIsNone(decode_packet(corrupt))
        # Wrong starter byte
        bad_starter = bytearray(valid)
        bad_starter[0] = 0xAA
        bad_starter[-1] = calc_checksum(bad_starter[:-1])
        self.assertIsNone(decode_packet(bad_starter))
        # Too short
        self.assertIsNone(decode_packet(bytes([STARTER, 0xB0, 0x00])))


class TestProtocolDispatch(unittest.TestCase):
    """Verify MeterID-to-protocol routing uses explicit allowlist with read-only fallback."""

    def test_verified_d2_dispatch(self) -> None:
        self.assertIsInstance(get_protocol(0xD2), TreadmillD2Protocol)

    def test_d5_dispatch(self) -> None:
        self.assertIsInstance(get_protocol(0xD5), TreadmillD5Protocol)

    def test_unknown_and_none_fallback_to_readonly(self) -> None:
        for meter_id in (None, 0x00, 0xD0, 0xD1, 0xD3, 0xD4, 0xFF):
            with self.subTest(meter_id=meter_id):
                self.assertIsInstance(get_protocol(meter_id), TreadmillReadOnlyProtocol)


class TestReadOnlySafetyInvariants(unittest.TestCase):
    """Guarantee unverified protocols (00.D5 and unknown fallback) never emit write frames."""

    def _assert_protocol_is_strictly_readonly(
        self, proto: TreadmillD5Protocol | TreadmillReadOnlyProtocol, mid: int
    ) -> None:
        self.assertFalse(proto.supports_start_pause)
        self.assertFalse(proto.supports_stop)
        self.assertFalse(proto.supports_target_incline)
        self.assertFalse(proto.supports_target_speed)
        self.assertFalse(proto.requires_disconnect_on_stop)

        self.assertEqual(proto.build_start_packets(0x00, mid, is_paused=False), [])
        self.assertEqual(proto.build_start_packets(0x00, mid, is_paused=True), [])
        self.assertEqual(proto.build_pause_packets(0x00, mid), [])
        self.assertEqual(proto.build_stop_packets(0x00, mid), [])
        self.assertEqual(proto.build_incline_packets(0x00, mid, 5), [])
        self.assertEqual(proto.build_speed_packets(0x00, mid, 8.5), [])
        self.assertEqual(proto.build_unlock_packets(0x00, mid), [])

        telemetry = TreadmillTelemetry(
            duration_s=10,
            distance_m=50,
            calories_kcal=5,
            heart_rate_bpm=110,
            speed_kmh=5.0,
            incline_pct=1.0,
            raw_state=2,
            warmup_state=3,
        )
        self.assertEqual(proto.build_countdown_confirm_packets(0x00, mid, telemetry), [])

        for pkt in proto.build_init_packets(0x00, mid):
            decoded = decode_packet(pkt)
            self.assertIsNotNone(decoded)
            assert decoded is not None
            self.assertIn(decoded[0], _READ_ONLY_INIT_OPCODES)

        poll_decoded = decode_packet(proto.build_status_poll(0x00, mid))
        self.assertIsNotNone(poll_decoded)
        assert poll_decoded is not None
        self.assertIn(poll_decoded[0], _READ_ONLY_POLL_OPCODES)

    def test_d5_protocol_is_strictly_readonly(self) -> None:
        self._assert_protocol_is_strictly_readonly(TreadmillD5Protocol(), 0xD5)

    def test_unknown_protocol_is_strictly_readonly(self) -> None:
        self._assert_protocol_is_strictly_readonly(TreadmillReadOnlyProtocol(), 0x00)
        self._assert_protocol_is_strictly_readonly(TreadmillReadOnlyProtocol(), 0xD3)


class TestD2Protocol(unittest.TestCase):
    """Verify 00.D2 hardware-verified controls, unlock sequence, countdown guard, and parsing."""

    def setUp(self) -> None:
        self.proto = TreadmillD2Protocol()

    def test_capabilities(self) -> None:
        self.assertFalse(self.proto.supports_start_pause)
        self.assertTrue(self.proto.supports_stop)
        self.assertTrue(self.proto.supports_target_incline)
        self.assertFalse(self.proto.supports_target_speed)
        self.assertTrue(self.proto.requires_disconnect_on_stop)

    def test_unlock_sequence_sends_unlock_value_0x01(self) -> None:
        pkts = self.proto.build_unlock_packets(0x00, 0xD2)
        self.assertEqual(len(pkts), 3)
        self.assertEqual(pkts[-1], bytes.fromhex("F0 AF 01 D3 02 75"))

    def test_countdown_confirm_only_fires_after_countdown_completes(self) -> None:
        during_countdown = TreadmillTelemetry(0, 0, 0, 0, 0.0, 0.0, raw_state=2, warmup_state=1)
        after_countdown = TreadmillTelemetry(0, 0, 0, 0, 1.0, 0.0, raw_state=2, warmup_state=3)

        self.assertEqual(
            self.proto.build_countdown_confirm_packets(0x00, 0xD2, during_countdown), []
        )
        confirm = self.proto.build_countdown_confirm_packets(0x00, 0xD2, after_countdown)
        self.assertEqual(len(confirm), 1)
        self.assertEqual(decode_packet(confirm[0]), (CMD_SET_CONTROL_STATE, [0x00, 0xD2, 0x01]))

    def test_stop_incline_and_no_speed_packets(self) -> None:
        stop_decoded = [decode_packet(p) for p in self.proto.build_stop_packets(0x00, 0xD2)]
        self.assertEqual(
            stop_decoded,
            [
                (CMD_SET_CONTROL_STATE, [0x00, 0xD2, 0x02]),
                (CMD_SET_CONTROL_STATE, [0x00, 0xD2, 0x03]),
                (CMD_SET_CONTROL_STATE, [0x00, 0xD2, 0x03]),
            ],
        )
        incline_pkts = self.proto.build_incline_packets(0x00, 0xD2, 7)
        self.assertEqual(len(incline_pkts), 1)
        self.assertEqual(
            decode_packet(incline_pkts[0]), (CMD_SET_INCLINE, [0x00, 0xD2, 7, 0x63, 0x63])
        )
        self.assertEqual(self.proto.build_speed_packets(0x00, 0xD2, 6.0), [])

    def test_parse_limits_and_status(self) -> None:
        limits = self.proto.parse_limits([0x00, 0xD2, 1, 18, 0, 0, 15])
        self.assertIsNotNone(limits)
        assert limits is not None
        self.assertEqual((limits.min_speed, limits.max_speed), (1.0, 18.0))
        self.assertEqual((limits.min_incline, limits.max_incline), (0.0, 15.0))
        self.assertIsNone(self.proto.parse_limits([0x00, 0xD2]))

        # payload: cid, mid, sec=45, min=2, dist=1*100+23 -> 1230m, kcal=0*100+85,
        # hr=1*100+32=132, speed=(0*100+85)/10=8.5, incline=3, raw_state=2, warmup=3
        tel = self.proto.parse_status([0x00, 0xD2, 45, 2, 1, 23, 0, 85, 1, 32, 0, 85, 3, 2, 3])
        self.assertIsNotNone(tel)
        assert tel is not None
        self.assertEqual(tel.duration_s, 165)
        self.assertEqual(tel.distance_m, 1230)
        self.assertEqual(tel.calories_kcal, 85)
        self.assertEqual(tel.heart_rate_bpm, 132)
        self.assertEqual(tel.speed_kmh, 8.5)
        self.assertEqual(tel.incline_pct, 3.0)
        self.assertEqual((tel.raw_state, tel.warmup_state), (2, 3))
        self.assertIsNone(self.proto.parse_status([0x00, 0xD2]))


class TestD5AndReadOnlyParsing(unittest.TestCase):
    """Verify length-prefixed 00.D5 parsing and unknown fallback probing."""

    def test_d5_parse_limits_and_status(self) -> None:
        proto = TreadmillD5Protocol()
        limits = proto.parse_limits([0x07, 0x00, 0xD5, 1, 20, 0, 0, 12])
        self.assertIsNotNone(limits)
        assert limits is not None
        self.assertEqual((limits.min_speed, limits.max_speed), (1.0, 20.0))
        self.assertEqual((limits.min_incline, limits.max_incline), (0.0, 12.0))

        tel = proto.parse_status([0x0F, 0x00, 0xD5, 30, 1, 0, 50, 0, 42, 1, 20, 0, 65, 2, 2, 3])
        self.assertIsNotNone(tel)
        assert tel is not None
        self.assertEqual(tel.duration_s, 90)
        self.assertEqual(tel.distance_m, 500)
        self.assertEqual(tel.calories_kcal, 42)
        self.assertEqual(tel.heart_rate_bpm, 120)
        self.assertEqual(tel.speed_kmh, 6.5)
        self.assertEqual(tel.incline_pct, 2.0)
        self.assertEqual(proto.parse_control_state([0x03, 0x00, 0xD5, 1]), 1)

    def test_readonly_probes_with_universal_ack_when_unidentified(self) -> None:
        proto = TreadmillReadOnlyProtocol()
        self.assertEqual(
            proto.build_init_packets(0x00, 0x00), [bytes.fromhex("F0 A0 01 01 92")]
        )
        self.assertEqual(
            proto.build_status_poll(0x00, 0x00), bytes.fromhex("F0 A0 01 01 92")
        )


if __name__ == "__main__":
    unittest.main()
