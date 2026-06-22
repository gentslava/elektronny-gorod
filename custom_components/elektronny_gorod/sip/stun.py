"""STUN Binding Response parse — публичный RTP-адрес за NAT для SDP `c=`.

Источник логики — probe_sip_media.py `_parse_stun`. Поддержка XOR-MAPPED-ADDRESS
(0x0020, RFC 5389) и legacy MAPPED-ADDRESS (0x0001). Magic cookie 0x2112A442.
"""
from __future__ import annotations

import socket
import struct

_MAGIC = 0x2112A442


def parse_stun_binding_response(data: bytes) -> tuple[str, int] | None:
    """Разобрать STUN Binding Response -> (public_ip, public_port) или None."""
    if len(data) < 20:
        return None
    i = 20
    while i + 4 <= len(data):
        atype, alen = struct.unpack("!HH", data[i : i + 4])
        i += 4
        val = data[i : i + alen]
        i += alen + ((4 - alen % 4) % 4)
        if atype in (0x0020, 0x0001) and len(val) >= 8:
            if atype == 0x0020:  # XOR-MAPPED-ADDRESS
                port = struct.unpack("!H", val[2:4])[0] ^ (_MAGIC >> 16)
                addr = struct.unpack("!I", val[4:8])[0] ^ _MAGIC
            else:  # MAPPED-ADDRESS (legacy)
                port = struct.unpack("!H", val[2:4])[0]
                addr = struct.unpack("!I", val[4:8])[0]
            return socket.inet_ntoa(struct.pack("!I", addr)), port
    return None
