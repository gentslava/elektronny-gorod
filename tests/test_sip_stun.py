"""Unit-тесты STUN Binding Response parse (sip/stun.py)."""
from __future__ import annotations

import socket
import struct

from custom_components.elektronny_gorod.sip.stun import parse_stun_binding_response

_MAGIC = 0x2112A442


def _build_xor_mapped_response(ip: str, port: int) -> bytes:
    # XOR-MAPPED-ADDRESS (0x0020): reserved(1) family(1=IPv4) X-Port(2) X-Addr(4).
    xport = port ^ (_MAGIC >> 16)
    xaddr = struct.unpack("!I", socket.inet_aton(ip))[0] ^ _MAGIC
    value = struct.pack("!BBHI", 0, 0x01, xport, xaddr)
    attr = struct.pack("!HH", 0x0020, len(value)) + value
    header = struct.pack("!HHI", 0x0101, len(attr), _MAGIC) + b"\x00" * 12
    return header + attr


def test_parse_xor_mapped_address() -> None:
    assert parse_stun_binding_response(
        _build_xor_mapped_response("203.0.113.5", 40016)
    ) == ("203.0.113.5", 40016)


def test_parse_returns_none_on_short_packet() -> None:
    assert parse_stun_binding_response(b"\x00" * 10) is None


def test_parse_returns_none_without_address_attribute() -> None:
    header = struct.pack("!HHI", 0x0101, 0, _MAGIC) + b"\x00" * 12
    assert parse_stun_binding_response(header) is None
