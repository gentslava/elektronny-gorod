"""Аудио-мост two-way: downlink G.711 из SipManager → go2rtc (audio-bridge-design.md).

Slice 1 (downlink): мост поднимает ffmpeg-субпроцесс — читает G.711-кадры гостя из
stdin, отдаёт mpegts/aac по HTTP (`-listen 1`). go2rtc тянет `ffmpeg:http://<host>`
(REST-источник, см. go2rtc.upsert_audio_stream), транскодит в Opus → WebRTC →
Advanced Camera Card. Механизм валидирован на проде (PoC D-audio-1).

Муксинг отдан ffmpeg (не хендроллим mpegts/RTSP в Python). Чистое (ffmpeg-аргументы,
go2rtc-src) — юнит-тестируемо; субпроцесс/feed — сетевой слой, живой звонок.
"""
from __future__ import annotations

import asyncio
import socket

from ..const import LOGGER

# Порог write-буфера stdin ffmpeg: если go2rtc ещё не подключился (ffmpeg не
# дренирует stdin) — дропаем кадры, не копим память. ~1с G.711 = 8000 байт.
_MAX_WRITE_BUFFER = 16000


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
        """Поднять ffmpeg-субпроцесс (HTTP-сервер ждёт подключения go2rtc)."""
        self._proc = await asyncio.create_subprocess_exec(
            *self._ffmpeg_args(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        LOGGER.info("AudioBridge: ffmpeg HTTP-сервер на :%s (src=%s)", self._port, self.go2rtc_src)

    def feed_downlink(self, frame: bytes) -> None:
        """Записать G.711-кадр гостя в stdin ffmpeg (drop при переполнении буфера)."""
        proc = self._proc
        if proc is None or proc.stdin is None or proc.returncode is not None:
            return
        transport = proc.stdin.transport
        # go2rtc ещё не подключился (нет consumer) → ffmpeg не дренирует stdin.
        # Не копим: дропаем, пока пользователь не откроет карту.
        if transport is not None and transport.get_write_buffer_size() > _MAX_WRITE_BUFFER:
            return
        try:
            proc.stdin.write(frame)
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            pass

    async def stop(self) -> None:
        """Остановить ffmpeg-субпроцесс (закрыть stdin, terminate, kill по таймауту)."""
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
