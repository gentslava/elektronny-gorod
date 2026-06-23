"""Аудио-мост two-way: downlink G.711 из SipManager → go2rtc (audio-bridge-design.md).

Slice 1 (downlink): мост поднимает ffmpeg-субпроцесс — читает G.711-кадры гостя из
stdin, выдаёт mpegts/aac в **stdout**, а наш персистентный asyncio-HTTP-сервер на
`:port` раздаёт этот поток клиентам. go2rtc тянет `ffmpeg:http://<host>` (REST-
источник, см. go2rtc.upsert_audio_stream), транскодит в Opus → WebRTC → карту.

🔴 Почему свой сервер, а не `ffmpeg -listen 1`: live-доказано (2026-06-23), что
`ffmpeg -listen 1 -multiple_requests 1` **выходит на первом же отключении**
потребителя (`Connection reset by peer` → ffmpeg die). go2rtc при MSE/WebRTC-
negotiation подключается-отключается-переподключается → первое отключение убивало
мост → reconnect ловил `Connection refused`. Наш сервер переживает любые
подключения/пробы/реконнекты: ffmpeg и listener живут весь разговор.

🔴 Тишина-keepalive: ffmpeg должен иметь непрерывный вход, иначе stdout пустеет и
клиент не получает PAT/PMT для декодирования. Мост шлёт тишину с старта и в паузах
downlink. mpegts-аудио self-keyframing: клиент, подключившийся в середине, ловит
PAT/PMT (~раз в 0.1с) и декодирует AAC сразу.

Муксинг отдан ffmpeg (не хендроллим протокол). Чистое (ffmpeg-args, go2rtc-src) —
юнит-тестируемо; сервер/субпроцесс/feed — сетевой слой, живой звонок.
"""
from __future__ import annotations

import asyncio
import socket

from ..const import LOGGER

_FRAME_BYTES = 160  # G.711 8кГц, 20мс
_KEEPALIVE_GAP_SEC = 0.04  # нет реального кадра дольше → подкладываем тишину
_CHUNK = 4096  # размер чтения mpegts из stdout ffmpeg
_DRAIN_TIMEOUT = 2.0  # медленный/мёртвый клиент дольше → выкидываем


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
    """ffmpeg-мост downlink: G.711-кадры → mpegts/aac stdout → персистентный HTTP."""

    def __init__(self, host_ip: str, port: int, payload_type: int) -> None:
        self._host_ip = host_ip
        self._port = port
        self._pt = payload_type
        self._proc: asyncio.subprocess.Process | None = None
        # G.711 «тишина»: µ-law=0xFF, A-law=0xD5.
        self._silence = bytes([0xFF if payload_type == 0 else 0xD5] * _FRAME_BYTES)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._keepalive: asyncio.Task | None = None
        self._broadcast: asyncio.Task | None = None
        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._last_write = 0.0

    @property
    def go2rtc_src(self) -> str:
        """go2rtc REST-источник: тянет наш HTTP-мост, выводит opus в WebRTC."""
        return f"ffmpeg:http://{self._host_ip}:{self._port}#audio=opus"

    def _ffmpeg_args(self) -> list[str]:
        """ffmpeg: G.711 (mulaw/alaw) из stdin → mpegts/aac в stdout (pipe:1)."""
        fmt = "mulaw" if self._pt == 0 else "alaw"
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", fmt, "-ar", "8000", "-ac", "1", "-i", "pipe:0",
            "-c:a", "aac", "-f", "mpegts", "pipe:1",
        ]

    async def start(self) -> None:
        """ffmpeg (stdout-mpegts) + HTTP-сервер на нашем порту + keepalive-тишина."""
        self._proc = await asyncio.create_subprocess_exec(
            *self._ffmpeg_args(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._loop = asyncio.get_running_loop()
        self._last_write = 0.0  # → keepalive сразу прайм-тишиной даст ffmpeg вход
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port
        )
        self._broadcast = self._loop.create_task(self._broadcast_loop())
        self._keepalive = self._loop.create_task(self._keepalive_loop())
        LOGGER.info("AudioBridge: HTTP-сервер на :%s (src=%s)", self._port, self.go2rtc_src)

    # ---- HTTP-сервер: раздача mpegts go2rtc ----
    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Один потребитель (go2rtc-ffmpeg): проглотить HTTP-запрос → 200 + mpegts.

        Отключение/повторное подключение клиента НЕ трогает ffmpeg — переживаем
        любой negotiation-цикл go2rtc. Данные пушит `_broadcast_loop`.
        """
        try:
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, OSError):
            pass  # пробы без полного запроса всё равно обслуживаем
        try:
            writer.write(
                b"HTTP/1.0 200 OK\r\n"
                b"Content-Type: video/mp2t\r\n"
                b"Connection: close\r\n\r\n"
            )
            await writer.drain()
        except (ConnectionError, OSError):
            self._safe_close(writer)
            return
        self._clients.add(writer)
        try:
            while (
                not writer.is_closing()
                and self._proc is not None
                and self._proc.returncode is None
            ):
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            self._clients.discard(writer)
            self._safe_close(writer)

    async def _broadcast_loop(self) -> None:
        """Читать mpegts из stdout ffmpeg → веером во всех клиентов; мёртвых выкинуть."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while proc.returncode is None:
                chunk = await proc.stdout.read(_CHUNK)
                if not chunk:
                    break
                for w in list(self._clients):
                    try:
                        w.write(chunk)
                        await asyncio.wait_for(w.drain(), timeout=_DRAIN_TIMEOUT)
                    except (ConnectionError, OSError, RuntimeError, asyncio.TimeoutError):
                        self._clients.discard(w)
                        self._safe_close(w)
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _safe_close(writer: asyncio.StreamWriter) -> None:
        try:
            if not writer.is_closing():
                writer.close()
        except (ConnectionError, OSError, RuntimeError):
            pass

    # ---- кормление downlink + keepalive ----
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
        ffmpeg непрерывным, чтобы stdout-поток (PAT/PMT+AAC) не прерывался."""
        try:
            while self._proc is not None and self._proc.returncode is None:
                if (
                    self._loop is not None
                    and self._loop.time() - self._last_write > _KEEPALIVE_GAP_SEC
                ):
                    self._write(self._silence)
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Остановить keepalive/broadcast/сервер/клиентов + ffmpeg (graceful → kill)."""
        for task in (self._keepalive, self._broadcast):
            if task is not None:
                task.cancel()
        self._keepalive = self._broadcast = None
        server, self._server = self._server, None
        if server is not None:
            server.close()
        for w in list(self._clients):
            self._safe_close(w)
        self._clients.clear()
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
