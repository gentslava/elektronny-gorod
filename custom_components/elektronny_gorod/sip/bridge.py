"""Аудио-мост two-way: downlink G.711 из SipManager → go2rtc (audio-bridge-design.md).

Slice 1 (downlink): мост поднимает ffmpeg-субпроцесс — читает G.711-кадры гостя из
stdin, отдаёт mpegts/aac по HTTP (`-listen 1`). go2rtc тянет `ffmpeg:http://<host>`
(REST-источник, см. go2rtc.upsert_audio_stream), транскодит в Opus → WebRTC →
Advanced Camera Card. Механизм валидирован на проде (PoC D-audio-1).

🔴 Тишина-keepalive: `ffmpeg -i pipe:0 -listen 1` открывает HTTP-listener только
когда на stdin пошли данные. До latching (первого downlink-кадра) stdin пуст →
listener закрыт → go2rtc ловит `Connection refused`. Поэтому мост шлёт тишину с
самого старта и в паузах downlink — ffmpeg всегда имеет вход и держит listener.

Муксинг отдан ffmpeg (не хендроллим протокол). Чистое (ffmpeg-args, go2rtc-src) —
юнит-тестируемо; субпроцесс/feed — сетевой слой, живой звонок.
"""
from __future__ import annotations

import asyncio
import socket

from ..const import LOGGER

_FRAME_BYTES = 160  # G.711 8кГц, 20мс
_KEEPALIVE_GAP_SEC = 0.04  # нет реального кадра дольше → подкладываем тишину


def detect_lan_ip() -> str:
    """Primary LAN IP хоста HA — адрес, по которому go2rtc (в контейнере) дотянется
    до моста. Как `_outbound_ip`, но к публичному IP → отдаёт LAN-интерфейс."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class AudioBridge:
    """ffmpeg-мост downlink: G.711-кадры → mpegts/aac HTTP → go2rtc."""

    def __init__(self, host_ip: str, port: int, payload_type: int) -> None:
        self._host_ip = host_ip
        self._port = port
        self._pt = payload_type
        self._proc: asyncio.subprocess.Process | None = None
        # G.711 «тишина»: µ-law=0xFF, A-law=0xD5.
        self._silence = bytes([0xFF if payload_type == 0 else 0xD5] * _FRAME_BYTES)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._keepalive: asyncio.Task | None = None
        self._last_write = 0.0

    @property
    def go2rtc_src(self) -> str:
        """go2rtc REST-источник: тянет наш ffmpeg-HTTP, выводит opus в WebRTC."""
        return f"ffmpeg:http://{self._host_ip}:{self._port}#audio=opus"

    def _ffmpeg_args(self) -> list[str]:
        """ffmpeg: G.711 (mulaw/alaw) из stdin → mpegts/aac HTTP-сервер на нашем порту."""
        fmt = "mulaw" if self._pt == 0 else "alaw"
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", fmt, "-ar", "8000", "-ac", "1", "-i", "pipe:0",
            "-c:a", "aac", "-f", "mpegts",
            "-listen", "1", "-multiple_requests", "1",
            f"http://0.0.0.0:{self._port}",
        ]

    async def start(self) -> None:
        """Поднять ffmpeg-субпроцесс + keepalive-тишину (listener открывается сразу)."""
        self._proc = await asyncio.create_subprocess_exec(
            *self._ffmpeg_args(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._loop = asyncio.get_running_loop()
        self._last_write = 0.0  # → keepalive сразу прайм-тишиной откроет listener
        self._keepalive = self._loop.create_task(self._keepalive_loop())
        LOGGER.info("AudioBridge: ffmpeg HTTP-сервер на :%s (src=%s)", self._port, self.go2rtc_src)

    def _write(self, frame: bytes) -> None:
        proc = self._proc
        if (
            proc is None or proc.stdin is None
            or proc.returncode is not None or proc.stdin.is_closing()
        ):
            return
        try:
            proc.stdin.write(frame)
            if self._loop is not None:
                self._last_write = self._loop.time()
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            pass

    def feed_downlink(self, frame: bytes) -> None:
        """G.711-кадр гостя → stdin ffmpeg (немедленно, без буферизации)."""
        self._write(frame)

    async def _keepalive_loop(self) -> None:
        """Тишина в паузах downlink (старт/до latching/между кадрами) — держит вход
        ffmpeg непрерывным, чтобы HTTP-listener был открыт (иначе go2rtc refused)."""
        try:
            while self._proc is not None and self._proc.returncode is None:
                if self._loop is not None and self._loop.time() - self._last_write > _KEEPALIVE_GAP_SEC:
                    self._write(self._silence)
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Остановить keepalive + ffmpeg (закрыть stdin, terminate, kill по таймауту)."""
        keepalive, self._keepalive = self._keepalive, None
        if keepalive is not None:
            keepalive.cancel()
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            pass
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        LOGGER.info("AudioBridge: ffmpeg остановлен")
