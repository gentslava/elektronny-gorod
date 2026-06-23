"""Unit-тесты чистой логики аудио-моста (sip/bridge.py).

Механизм (audio-bridge-design.md §6.1): мост поднимает ffmpeg-субпроцесс (G.711
stdin → mpegts/aac в stdout), наш персистентный HTTP-сервер раздаёт поток, go2rtc
тянет `ffmpeg:http://`. Тестируем чистое: построение ffmpeg-аргументов (mulaw/alaw)
+ go2rtc-src. Сервер/субпроцесс/feed — сетевой слой, проверяется живым звонком.
"""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.bridge import AudioBridge


def test_ffmpeg_args_pcmu_mulaw() -> None:
    b = AudioBridge("192.168.1.100", 40020, payload_type=0)
    args = b._ffmpeg_args()
    # PCMU(0) → вход mulaw из stdin, выход mpegts/aac в stdout (раздаёт наш сервер).
    assert "mulaw" in args
    assert "pipe:0" in args
    assert "mpegts" in args
    assert "pipe:1" in args
    assert args[0] == "ffmpeg"


def test_ffmpeg_args_pcma_alaw() -> None:
    b = AudioBridge("h", 1, payload_type=8)
    args = b._ffmpeg_args()
    assert "alaw" in args
    assert "mulaw" not in args


def test_go2rtc_src_is_ffmpeg_http_aac_and_opus() -> None:
    b = AudioBridge("192.168.1.100", 40020, payload_type=0)
    # Два кодека (как камеры): AAC для мгновенного MSE + opus для WebRTC.
    assert b.go2rtc_src == "ffmpeg:http://192.168.1.100:40020#audio=aac#audio=opus"


def test_feed_downlink_noop_when_not_started() -> None:
    # До start() (нет процесса) feed не падает — просто игнор.
    b = AudioBridge("h", 40020, payload_type=0)
    b.feed_downlink(b"\xff" * 160)  # не должно бросить
