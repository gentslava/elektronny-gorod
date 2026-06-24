"""RTP G.711 сессия для two-way аудио домофона (latching без STUN).

call-answer-model.md: локальный SDP + FreeSWITCH RTP-latching — устройство шлёт
uplink первым (+ keepalive), сервер «защёлкивает» source и шлёт downlink туда.
Поэтому STUN не нужен: достаточно начать слать RTP сразу после 200 OK.
"""
from __future__ import annotations

import asyncio
import random
import struct
from collections.abc import Callable

_RTP_VERSION = 0x80  # version=2, без padding/extension/CSRC
_HEADER_LEN = 12
PTIME_SEC = 0.02  # G.711 8kHz, 20ms кадр
FRAME_BYTES = 160  # 8000 * 0.02


def _pace_step(prev_deadline: float, now: float) -> tuple[float, float]:
    """Дрейф-компенсированный пейсинг RTP-uplink.

    Следующий дедлайн = `prev_deadline + PTIME` (ФИКСИРОВАННАЯ сетка, а не `now + PTIME`)
    → per-iteration overhead не накапливается, средний такт ровно 20мс. Возвращает
    `(next_deadline, sleep_sec)`, где `sleep_sec >= 0` (если отстали — 0, догоняем).

    Раньше uplink был тишиной-keepalive, дрейф не мешал; с реальным микрофоном (Phase C)
    наивный `sleep(PTIME)` копил overhead (~12% медленнее realtime → буфер саттурируется
    → drop-кадры → заикания, доказано PoC D-audio-2)."""
    next_deadline = prev_deadline + PTIME_SEC
    return next_deadline, max(0.0, next_deadline - now)


def build_rtp_packet(
    payload_type: int,
    seq: int,
    timestamp: int,
    ssrc: int,
    payload: bytes,
    marker: bool = False,
) -> bytes:
    """RTP-пакет: 12-байтный заголовок + G.711 payload."""
    b1 = (payload_type & 0x7F) | (0x80 if marker else 0)
    header = struct.pack(
        "!BBHII", _RTP_VERSION, b1,
        seq & 0xFFFF, timestamp & 0xFFFFFFFF, ssrc & 0xFFFFFFFF,
    )
    return header + payload


def parse_rtp_payload(data: bytes) -> bytes | None:
    """Извлечь payload из RTP-пакета (downlink) или None, если пакет слишком мал."""
    if len(data) <= _HEADER_LEN:
        return None
    return data[_HEADER_LEN:]


class RtpSession(asyncio.DatagramProtocol):
    """Двусторонний RTP G.711 поток. `on_downlink(payload)` — кадры от домофона.

    `frame_provider()` поставляет G.711-кадры для uplink (микрофон/трек/тишина);
    None → тишина-кадр (для keepalive latching). Сетевой — тестируется integration.
    """

    def __init__(
        self,
        payload_type: int,
        on_downlink: Callable[[bytes], None] | None = None,
    ) -> None:
        self.payload_type = payload_type
        self.on_downlink = on_downlink
        self.transport: asyncio.DatagramTransport | None = None
        self._silence = bytes([0xFF if payload_type == 0 else 0xD5] * FRAME_BYTES)
        self._ssrc = random.randint(0, 1 << 31)
        self._seq = 0
        self._ts = 0
        self._active = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        self._active = True

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if not self._active or self.on_downlink is None:
            return
        payload = parse_rtp_payload(data)
        if payload:
            self.on_downlink(payload)

    def stop(self) -> None:
        self._active = False
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    async def run_uplink(
        self,
        door_ip: str,
        door_port: int,
        frame_provider: Callable[[], bytes | None],
        stop: asyncio.Event,
    ) -> None:
        """Слать G.711 uplink на домофон 20мс-ритмом, пока stop не выставлен.

        Первый кадр — сразу (активирует latching); затем по PTIME. None от
        provider → тишина (keepalive). marker на первом пакете.
        """
        first = True
        loop = asyncio.get_running_loop()
        next_send = loop.time()  # дрейф-компенсация: целимся в абсолютные дедлайны
        while not stop.is_set() and self.transport is not None:
            frame = frame_provider() or self._silence
            pkt = build_rtp_packet(
                self.payload_type, self._seq, self._ts, self._ssrc, frame, marker=first,
            )
            try:
                self.transport.sendto(pkt, (door_ip, door_port))
            except Exception:  # noqa: BLE001 — сокет мог закрыться
                break
            self._seq += 1
            self._ts += FRAME_BYTES
            first = False
            next_send, sleep_sec = _pace_step(next_send, loop.time())
            await asyncio.sleep(sleep_sec)
