"""G.711 (PCMU/PCMA) <-> 16-bit linear PCM транскод для SIP-аудио домофона.

Домофон оператора шлёт только G.711 (PCMU pt=0 / PCMA pt=8); voip-utils хардкодит
Opus — поэтому транскод наш слой (design.md §3.1). `audioop` удалён из stdlib в
Python 3.13 (PEP 594) → зависимость `audioop-lts` (manifest) возвращает модуль.

`pcm_to_g711` используется в рантайме `sip/uplink.py` (uplink-микрофон → G.711 →
RTP). `g711_to_pcm` (downlink G.711→PCM) — резерв; downlink-транскод сейчас делает
ffmpeg в `bridge.py`, прямой вызов появится при оптимизации одинарного транскода.
"""
from __future__ import annotations

import audioop  # audioop-lts на py3.13+

PCMU_PAYLOAD_TYPE = 0
PCMA_PAYLOAD_TYPE = 8
_SAMPLE_WIDTH = 2  # 16-bit signed linear PCM


def g711_to_pcm(data: bytes, payload_type: int) -> bytes:
    """G.711 байты -> 16-bit linear PCM (downlink: звук гостя)."""
    if payload_type == PCMU_PAYLOAD_TYPE:
        return audioop.ulaw2lin(data, _SAMPLE_WIDTH)
    if payload_type == PCMA_PAYLOAD_TYPE:
        return audioop.alaw2lin(data, _SAMPLE_WIDTH)
    raise ValueError(f"unsupported G.711 payload type: {payload_type}")


def pcm_to_g711(pcm: bytes, payload_type: int) -> bytes:
    """16-bit linear PCM -> G.711 байты (uplink: микрофон -> домофон)."""
    if payload_type == PCMU_PAYLOAD_TYPE:
        return audioop.lin2ulaw(pcm, _SAMPLE_WIDTH)
    if payload_type == PCMA_PAYLOAD_TYPE:
        return audioop.lin2alaw(pcm, _SAMPLE_WIDTH)
    raise ValueError(f"unsupported G.711 payload type: {payload_type}")
