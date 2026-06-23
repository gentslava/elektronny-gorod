"""Юнит-тесты UplinkSink (sip/uplink.py) — чистая логика обратной ветки uplink.

Транспорт микрофона зовёт feed(pcm, rate); SipManager.uplink_provider зовёт
next_frame() каждые 20мс. Сеть/транспорт — за этой границей (живой звонок/PoC).
"""
from __future__ import annotations

import audioop

from custom_components.elektronny_gorod.sip.uplink import MAX_FRAMES, UplinkSink

_PCMU = 0
_PCMA = 8


def test_feed_8k_silence_yields_one_pcmu_frame():
    # 160 сэмплов 16-бит тишины @ 8кГц = 320 байт → 1 кадр G.711 (µ-law тишина = 0xFF).
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 160, 8000)
    frame = sink.next_frame()
    assert frame == b"\xff" * 160
    assert sink.next_frame() is None  # буфер опустел


def test_feed_8k_silence_yields_one_pcma_frame():
    sink = UplinkSink(_PCMA)
    sink.feed(b"\x00\x00" * 160, 8000)
    assert sink.next_frame() == b"\xd5" * 160  # A-law тишина


def test_next_frame_none_when_empty():
    assert UplinkSink(_PCMU).next_frame() is None


def test_partial_frame_accumulates_across_feeds():
    # 80 сэмплов (160 байт PCM @ 8к) → пол-кадра G.711 (80 байт) → ещё нет кадра.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 80, 8000)
    assert sink.next_frame() is None  # < 160 байт G.711 накоплено
    sink.feed(b"\x00\x00" * 80, 8000)  # ещё 80 → суммарно 160 → 1 кадр
    assert sink.next_frame() == b"\xff" * 160
    assert sink.next_frame() is None


def test_fifo_order_multiple_frames():
    # Два разных кадра: тишина (0x00→0xFF), затем max-амплитуда → разный G.711.
    sink = UplinkSink(_PCMU)
    loud = audioop.lin2ulaw(b"\x00\x7f" * 160, 2)  # ненулевой PCM → не 0xFF
    sink.feed(b"\x00\x00" * 160, 8000)            # кадр A (тишина)
    sink.feed(b"\x00\x7f" * 160, 8000)            # кадр B (громкий)
    assert sink.next_frame() == b"\xff" * 160      # A первым (FIFO)
    assert sink.next_frame() == loud               # B вторым
    assert sink.next_frame() is None


def test_resample_48k_to_8k_produces_frames():
    # 48кГц → 8к: 9600 сэмплов (0.2с) → ~1600 сэмплов 8к → ~10 кадров по 160.
    # Допуск ±1 кадр (прайминг фильтра ratecv); без ресемпла было бы ~60 кадров.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 9600, 48000)
    frames = []
    while (f := sink.next_frame()) is not None:
        frames.append(f)
    assert 9 <= len(frames) <= 11  # ресемпл произошёл (не 60)
    assert all(len(f) == 160 for f in frames)


def test_resample_state_persists_across_feeds():
    # Тот же вход одним куском vs двумя — ресемпл со state даёт тот же суммарный поток.
    one = UplinkSink(_PCMU)
    one.feed(b"\x11\x11" * 9600, 48000)
    out_one = b""
    while (f := one.next_frame()) is not None:
        out_one += f

    two = UplinkSink(_PCMU)
    two.feed(b"\x11\x11" * 4800, 48000)
    two.feed(b"\x11\x11" * 4800, 48000)
    out_two = b""
    while (f := two.next_frame()) is not None:
        out_two += f

    assert out_one == out_two  # persistent ratecv state → бесшовная склейка


def test_overflow_drops_oldest():
    # Буфер ограничен MAX_FRAMES; переполнение выкидывает старейшие (low-latency).
    sink = UplinkSink(_PCMU)
    # Кадр-маркеры: первый блок тишина (0xFF), последний — громкий (не 0xFF).
    sink.feed(b"\x00\x00" * 160 * (MAX_FRAMES + 5), 8000)   # тишина: переполнит буфер
    sink.feed(b"\x00\x7f" * 160, 8000)                      # 1 громкий кадр в конец
    drained = []
    while (f := sink.next_frame()) is not None:
        drained.append(f)
    assert len(drained) == MAX_FRAMES          # не больше предела
    assert drained[-1] == audioop.lin2ulaw(b"\x00\x7f" * 160, 2)  # новейший уцелел
    assert drained[0] == b"\xff" * 160          # старейшие (тишина) частично сброшены, но FIFO


def test_feed_odd_length_pcm_drops_dangling_byte():
    # Нечётная длина (truncated/misaligned WS-кадр) → висячий байт дропается,
    # audioop.error НЕ бросается. После — нормальный feed работает.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00\x00", 8000)  # 1 сэмпл + висячий байт
    assert sink.next_frame() is None  # <160B, без исключения
    sink.feed(b"\x00\x00" * 160, 8000)  # добиваем кадр
    assert sink.next_frame() == b"\xff" * 160


def test_feed_single_byte_pcm_no_crash():
    # Один байт (всё, что осталось после truncation) → дроп, без падения.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x7f", 8000)
    assert sink.next_frame() is None


def test_clear_resets_buffer_and_state():
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 160, 8000)
    sink.clear()
    assert sink.next_frame() is None
