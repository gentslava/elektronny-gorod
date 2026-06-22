"""SDP parse (offer домофона) + build G.711 answer (200 OK). Из probe_sip_media.py.

Домофон шлёт audio-only G.711 (PCMU/PCMA) + telephone-event; видео — отдельно
через go2rtc (design.md §2). SDP-answer объявляет наш публичный RTP-адрес (STUN)
для latching за NAT.
"""
from __future__ import annotations

from typing import Any

_CRLF = "\r\n"


def parse_sdp(body: str) -> dict[str, Any]:
    """Грубый разбор SDP: connection IP, media-линии, rtpmap."""
    info: dict[str, Any] = {"conn_ip": None, "media": [], "rtpmap": {}}
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("c=IN IP4 "):
            info["conn_ip"] = ln.split()[2]
        elif ln.startswith("m="):
            parts = ln[2:].split()
            info["media"].append(
                {
                    "type": parts[0],
                    "port": int(parts[1]),
                    "proto": parts[2],
                    "fmts": parts[3:],
                }
            )
        elif ln.startswith("a=rtpmap:"):
            pt, _, codec = ln[len("a=rtpmap:") :].partition(" ")
            info["rtpmap"][pt] = codec.strip()
    return info


def build_g711_answer(
    media_ip: str,
    media_port: int,
    payload_type: int,
    codec: str,
    session_id: int = 0,
) -> str:
    """SDP-answer (тело 200 OK) для G.711 audio-only.

    `media_ip`/`media_port` — публичный RTP-адрес (STUN) для `c=`/`m=`, чтобы
    downlink дошёл за symmetric NAT через latching. `session_id` детерминирован
    (параметр, не random) — воспроизводимость и тестируемость.
    """
    return _CRLF.join(
        [
            "v=0",
            f"o=- {session_id} 1 IN IP4 {media_ip}",
            "s=elektronny_gorod",
            f"c=IN IP4 {media_ip}",
            "t=0 0",
            f"m=audio {media_port} RTP/AVP {payload_type}",
            f"a=rtpmap:{payload_type} {codec}",
            "a=sendrecv",
            "",
        ]
    )
