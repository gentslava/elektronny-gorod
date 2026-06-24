"""UplinkSink — приём аудио микрофона (любой транспорт) → G.711-кадры для RTP-uplink.

Механизм-независимая граница (uplink-mic-design.md §2): транспорт микрофона зовёт
feed(pcm, rate); SipManager.uplink_provider зовёт next_frame() каждые 20мс. Чистая
логика (ресемпл/кодек/джиттер-буфер) — тестируема юнитами; сеть/транспорт — за этой
границей (живой звонок/PoC). Зеркало downlink-AudioBridge, обратная ветка.
"""
from __future__ import annotations

import audioop
from collections import deque

from .audio import pcm_to_g711

_TARGET_RATE = 8000
_SAMPLE_WIDTH = 2  # 16-bit signed linear PCM
_CHANNELS = 1
_FRAME_BYTES = 160  # G.711 8кГц, 20мс (== rtp.FRAME_BYTES)
MAX_FRAMES = 50  # джиттер-буфер ~1с; переполнение → drop-oldest (low-latency)


class UplinkSink:
    """Аудио микрофона → resample 8к → G.711 → джиттер-буфер кадрами 160B/20мс."""

    def __init__(self, payload_type: int) -> None:
        self._pt = payload_type
        self._ratecv_state = None  # persistent state audioop.ratecv (бесшовная склейка)
        self._accum = bytearray()  # G.711-байты, ещё не нарезанные в полный кадр
        self._frames: deque[bytes] = deque()

    def feed(self, pcm: bytes, sample_rate: int) -> None:
        """int16 mono PCM @ sample_rate → resample 8к → G.711 → накопитель G.711-байт → кадры 160B в буфер."""
        if not pcm:
            return
        if len(pcm) % _SAMPLE_WIDTH:
            # 16-bit PCM выровнен по 2 байта; truncated/misaligned WS-кадр (нечётная
            # длина) иначе бросил бы audioop.error. Дропаем висячий байт (defensive —
            # WS-handler тоже ловит, но sink не должен полагаться на чистоту входа).
            pcm = pcm[: len(pcm) - (len(pcm) % _SAMPLE_WIDTH)]
            if not pcm:
                return
        if sample_rate != _TARGET_RATE:
            pcm, self._ratecv_state = audioop.ratecv(
                pcm, _SAMPLE_WIDTH, _CHANNELS, sample_rate, _TARGET_RATE, self._ratecv_state
            )
        self._accum += pcm_to_g711(pcm, self._pt)
        while len(self._accum) >= _FRAME_BYTES:
            if len(self._frames) >= MAX_FRAMES:
                self._frames.popleft()  # drop-oldest перед append
            self._frames.append(bytes(self._accum[:_FRAME_BYTES]))
            del self._accum[:_FRAME_BYTES]

    def next_frame(self) -> bytes | None:
        """Один G.711-кадр 160B для uplink, или None (буфер пуст → тишина-keepalive)."""
        return self._frames.popleft() if self._frames else None

    def clear(self) -> None:
        """Сброс буфера/ресемпл-состояния на teardown вызова."""
        self._ratecv_state = None
        self._accum.clear()
        self._frames.clear()
