"""SDP parse (offer домофона) + build G.711 answer (200 OK). Из probe_sip_media.py.

Домофон шлёт audio-only G.711 (PCMU/PCMA) + telephone-event; видео — отдельно
через go2rtc (design.md §2). SDP-answer объявляет наш публичный RTP-адрес (STUN)
для latching за NAT.
"""
from __future__ import annotations

from typing import Any

_CRLF = "\r\n"


def parse_sdp(body: str) -> dict[str, Any]:
    """Грубый разбор SDP: connection IP, media-линии, rtpmap.

    SDP-offer приходит из сети (INVITE body) — untrusted input. Битые строки
    (нечисловой порт, усечённые `m=`/`c=`) **пропускаются**, а не валят разбор:
    иначе ValueError/IndexError всплыл бы в accept() → утечка AudioBridge.
    """
    info: dict[str, Any] = {"conn_ip": None, "media": [], "rtpmap": {}}
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("c=IN IP4 "):
            parts = ln.split()
            if len(parts) >= 3:
                info["conn_ip"] = parts[2]
        elif ln.startswith("m="):
            parts = ln[2:].split()
            if len(parts) < 3:
                continue  # усечённая m=-строка (нет порта/proto) — пропускаем
            try:
                port = int(parts[1])
            except ValueError:
                continue  # нечисловой порт — битая m=-строка, пропускаем
            info["media"].append(
                {
                    "type": parts[0],
                    "port": port,
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
