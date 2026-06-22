"""Unit-тесты SDP parse + build G.711 answer (sip/sdp.py)."""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.sdp import build_g711_answer, parse_sdp

# Реальная форма offer-а домофона: audio-only G.711 (PCMA/PCMU) + telephone-event.
_OFFER = (
    "v=0\r\n"
    "o=- 1 1 IN IP4 10.0.0.1\r\n"
    "s=call\r\n"
    "c=IN IP4 10.0.0.1\r\n"
    "t=0 0\r\n"
    "m=audio 7078 RTP/AVP 8 0 101\r\n"
    "a=rtpmap:8 PCMA/8000\r\n"
    "a=rtpmap:0 PCMU/8000\r\n"
    "a=rtpmap:101 telephone-event/8000\r\n"
    "a=ptime:20\r\n"
)


def test_parse_sdp_extracts_conn_media_rtpmap() -> None:
    info = parse_sdp(_OFFER)
    assert info["conn_ip"] == "10.0.0.1"
    audio = info["media"][0]
    assert audio["type"] == "audio"
    assert audio["port"] == 7078
    assert audio["fmts"] == ["8", "0", "101"]
    assert info["rtpmap"]["8"] == "PCMA/8000"
    assert info["rtpmap"]["101"] == "telephone-event/8000"


def test_build_g711_answer_is_audio_only_g711() -> None:
    sdp = build_g711_answer("203.0.113.5", 40016, 8, "PCMA/8000", session_id=42)
    assert "m=audio 40016 RTP/AVP 8\r\n" in sdp
    assert "a=rtpmap:8 PCMA/8000\r\n" in sdp
    assert "c=IN IP4 203.0.113.5\r\n" in sdp
    assert "a=sendrecv" in sdp
    assert "o=- 42 1 IN IP4 203.0.113.5" in sdp
    # audio-only — без видео-линии
    assert "m=video" not in sdp


def test_build_g711_answer_is_deterministic() -> None:
    # одинаковые аргументы -> одинаковый SDP (важно для воспроизводимости/тестов).
    args = ("203.0.113.5", 40016, 0, "PCMU/8000")
    assert build_g711_answer(*args, session_id=7) == build_g711_answer(*args, session_id=7)
