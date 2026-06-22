"""Unit-тесты RTP-пакетов (sip/rtp.py)."""
from __future__ import annotations

import struct

from custom_components.elektronny_gorod.sip.rtp import (
    build_rtp_packet,
    parse_rtp_payload,
)


def test_build_rtp_packet_header_and_payload() -> None:
    pkt = build_rtp_packet(
        payload_type=0, seq=5, timestamp=160, ssrc=0x12345678,
        payload=b"\xff" * 160, marker=True,
    )
    assert len(pkt) == 12 + 160
    assert pkt[0] == 0x80  # version=2
    assert pkt[1] == 0x80 | 0  # marker + pt=0
    assert struct.unpack("!H", pkt[2:4])[0] == 5
    assert struct.unpack("!I", pkt[4:8])[0] == 160
    assert struct.unpack("!I", pkt[8:12])[0] == 0x12345678
    assert pkt[12:] == b"\xff" * 160


def test_build_rtp_packet_no_marker_pt8() -> None:
    pkt = build_rtp_packet(8, 1, 0, 1, b"\x00" * 160)
    assert pkt[1] == 8  # pt=8 без marker


def test_seq_and_ts_wrap() -> None:
    # seq/timestamp оборачиваются по маске (16/32 бит) — без ошибки.
    pkt = build_rtp_packet(0, 0x1FFFF, 0x1FFFFFFFF, 0x1FFFFFFFF, b"\x00")
    assert struct.unpack("!H", pkt[2:4])[0] == 0xFFFF
    assert struct.unpack("!I", pkt[4:8])[0] == 0xFFFFFFFF


def test_parse_rtp_payload() -> None:
    pkt = build_rtp_packet(0, 1, 0, 1, b"\xaa" * 160)
    assert parse_rtp_payload(pkt) == b"\xaa" * 160


def test_parse_rtp_payload_too_short() -> None:
    assert parse_rtp_payload(b"\x00" * 8) is None
