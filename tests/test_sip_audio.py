"""Unit-тесты G.711 (PCMU/PCMA) <-> PCM транскода (sip/audio.py)."""
from __future__ import annotations

import pytest

from custom_components.elektronny_gorod.sip.audio import (
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
    g711_to_pcm,
    pcm_to_g711,
)


@pytest.mark.parametrize("pt", [PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE])
def test_g711_roundtrip_reaches_fixed_point(pt: int) -> None:
    # G.711 lossy: первый decode->encode может канонизировать избыточный код
    # (µ-law: 0x7F и 0xFF оба декодируются в 0 -> канон 0xFF). Но второй проход
    # уже стабилен — транскод не дрейфует при повторной переупаковке, что и важно
    # для аудио-пути (downlink/uplink не накапливают искажения).
    g711 = bytes(range(256))  # все кодовые точки
    once = pcm_to_g711(g711_to_pcm(g711, pt), pt)
    twice = pcm_to_g711(g711_to_pcm(once, pt), pt)
    assert twice == once


@pytest.mark.parametrize("pt", [PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE])
def test_decode_doubles_byte_width(pt: int) -> None:
    # 8-bit G.711 -> 16-bit linear PCM = вдвое больше байт.
    assert len(g711_to_pcm(bytes(160), pt)) == 320


def test_unsupported_payload_type_raises() -> None:
    with pytest.raises(ValueError):
        g711_to_pcm(b"\x00", 99)
    with pytest.raises(ValueError):
        pcm_to_g711(b"\x00\x00", 99)


@pytest.mark.parametrize("pt", [PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE])
def test_pcm_to_g711_odd_length_truncates_dangling_byte(pt: int) -> None:
    # Defensive (Area A P2-1): нечётная длина PCM (truncated/misaligned кадр)
    # не должна бросать audioop.error — висячий байт обрезается, кодируется
    # чётная часть (1 G.711-байт на 2 байта PCM = 1 sample).
    odd = pcm_to_g711(b"\x00\x00\x00", pt)
    even = pcm_to_g711(b"\x00\x00", pt)
    assert odd == even
    assert len(odd) == 1
