"""Unit-тесты RTP-пакетов (sip/rtp.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

import struct

import pytest

from custom_components.elektronny_gorod.sip.rtp import (
    PTIME_SEC,
    _pace_step,
    build_rtp_packet,
    parse_rtp_payload,
)


# ── дрейф-компенсированный пейсинг (Phase C: uplink с реальным микрофоном) ──
def test_pace_step_on_time() -> None:
    # На дедлайне: следующий дедлайн +PTIME, спим ровно PTIME.
    nd, sleep = _pace_step(1.00, 1.00)
    assert nd == pytest.approx(1.00 + PTIME_SEC)
    assert sleep == pytest.approx(PTIME_SEC)


def test_pace_step_behind_catches_up() -> None:
    # Отстали: дедлайн-сетка ФИКСИРОВАНА (prev+PTIME, НЕ now+PTIME), сон=0 → дрейф не копится.
    nd, sleep = _pace_step(1.00, 1.00 + PTIME_SEC + 0.005)
    assert nd == pytest.approx(1.00 + PTIME_SEC)  # сетка не дрейфует от now
    assert sleep == 0.0


def test_pace_step_far_behind_no_negative_sleep() -> None:
    nd, sleep = _pace_step(1.00, 1.50)
    assert nd == pytest.approx(1.00 + PTIME_SEC)
    assert sleep == 0.0


def test_pace_step_ahead_sleeps_to_deadline() -> None:
    # Опередили (now < дедлайн): спим до дедлайна.
    nd, sleep = _pace_step(1.00, 1.005)
    assert sleep == pytest.approx(1.00 + PTIME_SEC - 1.005)


def test_build_rtp_packet_header_and_payload() -> None:
    pkt = build_rtp_packet(
        payload_type=0, seq=5, timestamp=160, ssrc=0x12345678,
        payload=b"\xff" * 160, marker=True,
    )
    assert len(pkt) == 12 + 160
    assert pkt[0] == 0x80  # version=2
    assert pkt[1] == 0x80 | 0  # marker + pt=0
    assert struct.unpack("!H", pkt[2:4])[0] == 5
    assert struct.unpack("!I", pkt[4:8])[0] == 160
    assert struct.unpack("!I", pkt[8:12])[0] == 0x12345678
    assert pkt[12:] == b"\xff" * 160


def test_build_rtp_packet_no_marker_pt8() -> None:
    pkt = build_rtp_packet(8, 1, 0, 1, b"\x00" * 160)
    assert pkt[1] == 8  # pt=8 без marker


def test_seq_and_ts_wrap() -> None:
    # seq/timestamp оборачиваются по маске (16/32 бит) — без ошибки.
    pkt = build_rtp_packet(0, 0x1FFFF, 0x1FFFFFFFF, 0x1FFFFFFFF, b"\x00")
    assert struct.unpack("!H", pkt[2:4])[0] == 0xFFFF
    assert struct.unpack("!I", pkt[4:8])[0] == 0xFFFFFFFF


def test_parse_rtp_payload() -> None:
    pkt = build_rtp_packet(0, 1, 0, 1, b"\xaa" * 160)
    assert parse_rtp_payload(pkt) == b"\xaa" * 160


def test_parse_rtp_payload_too_short() -> None:
    assert parse_rtp_payload(b"\x00" * 8) is None


# ─── Транспорт: приём звука гостя и отправка своего ─────────────────────────


def _endpoint(on_downlink=None, payload_type: int = 0):
    from custom_components.elektronny_gorod.sip.rtp import RtpSession

    endpoint = RtpSession(payload_type, on_downlink=on_downlink)
    transport = MagicMock()
    endpoint.connection_made(transport)
    return endpoint, transport


def test_guest_audio_reaches_the_bridge() -> None:
    """Полезная нагрузка из пакета домофона доходит до моста."""
    from custom_components.elektronny_gorod.sip.rtp import build_rtp_packet

    heard: list[bytes] = []
    endpoint, _ = _endpoint(on_downlink=heard.append)
    packet = build_rtp_packet(0, 1, 0, 12345, b"\xff" * 160, marker=False)

    endpoint.datagram_received(packet, ("10.0.0.5", 5004))

    assert heard == [b"\xff" * 160]


def test_audio_after_stop_is_ignored() -> None:
    """После отбоя пакеты домофона больше не разбираются.

    Иначе опоздавший пакет уже завершённого разговора попал бы в мост
    следующего звонка.
    """
    from custom_components.elektronny_gorod.sip.rtp import build_rtp_packet

    heard: list[bytes] = []
    endpoint, transport = _endpoint(on_downlink=heard.append)
    endpoint.stop()

    endpoint.datagram_received(build_rtp_packet(0, 1, 0, 1, b"\xff" * 160), ("h", 1))

    assert heard == []
    transport.close.assert_called_once()


def test_stop_is_idempotent() -> None:
    """Повторный отбой не должен падать — его зовут из нескольких мест."""
    endpoint, transport = _endpoint()
    endpoint.stop()
    endpoint.stop()
    transport.close.assert_called_once()


def test_garbage_packet_is_dropped_quietly() -> None:
    heard: list[bytes] = []
    endpoint, _ = _endpoint(on_downlink=heard.append)

    endpoint.datagram_received(b"\x00\x01", ("h", 1))

    assert heard == []


async def test_uplink_marks_the_first_packet_and_keeps_the_rhythm() -> None:
    """Первый пакет помечен маркером, дальше — своя нумерация и метки времени.

    Маркер активирует latching у домофона: без него первый пакет он может
    отбросить, и микрофон не слышно.
    """
    import asyncio

    from custom_components.elektronny_gorod.sip.rtp import FRAME_BYTES

    endpoint, transport = _endpoint()
    stop = asyncio.Event()
    frames = [b"\x01" * FRAME_BYTES, b"\x02" * FRAME_BYTES]

    def provider():
        return frames.pop(0) if frames else stop.set() or None

    await endpoint.run_uplink("10.0.0.5", 5004, provider, stop)

    sent = [call.args[0] for call in transport.sendto.call_args_list]
    assert len(sent) >= 2
    assert sent[0][1] & 0x80, "на первом пакете должен стоять маркер"
    assert not sent[1][1] & 0x80, "на последующих маркера быть не должно"
    assert sent[1][2:4] != sent[0][2:4], "номер пакета должен расти"


async def test_uplink_substitutes_silence_when_there_is_nothing_to_send() -> None:
    """Пауза микрофона не должна обрывать поток — вместо кадра идёт тишина."""
    import asyncio

    endpoint, transport = _endpoint(payload_type=8)
    stop = asyncio.Event()
    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        if calls["n"] > 2:
            stop.set()
        return None

    await endpoint.run_uplink("10.0.0.5", 5004, provider, stop)

    payload = transport.sendto.call_args_list[0].args[0][12:]
    assert set(payload) == {0xD5}, "тишина A-law"


async def test_uplink_stops_when_the_socket_dies() -> None:
    """Обрыв сокета завершает отправку, а не крутит цикл вхолостую."""
    import asyncio

    endpoint, transport = _endpoint()
    transport.sendto.side_effect = OSError("сокет закрыт")

    await endpoint.run_uplink("10.0.0.5", 5004, lambda: None, asyncio.Event())

    transport.sendto.assert_called_once()
