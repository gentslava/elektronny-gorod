"""Жизненный цикл вызова: удержание, ответ, отбой и отмена с той стороны.

Разбор SDP покрыт в `test_sip_manager.py`. Здесь — состояние вызова: кто
отвечает, что снимается при отбое и что происходит, когда гость уходит сам.
Ошибка на этом слое даёт зависший экран вызова или занятую линию, из-за
которой следующий звонок не пройдёт.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.sip.manager import (
    ActiveCall,
    HeldCall,
    SipManager,
    _outbound_ip,
)

_MODULE = "custom_components.elektronny_gorod.sip.manager"


def _held(manager: SipManager) -> MagicMock:
    """Подставить держимый вызов, не поднимая настоящих сокетов."""
    held = MagicMock(spec=HeldCall)
    manager._held = held
    return held


def _active(manager: SipManager) -> MagicMock:
    active = MagicMock(spec=ActiveCall)
    active.teardown = AsyncMock()
    manager._active = active
    return active


# ─── Локальный адрес для SDP ────────────────────────────────────────────────


def test_outbound_ip_is_the_interface_towards_the_intercom() -> None:
    """В SDP уходит адрес того интерфейса, через который виден домофон.

    Ошибка здесь — звук уходит в никуда: домофон шлёт RTP по адресу из SDP.
    """
    sock = MagicMock()
    sock.getsockname.return_value = ("192.168.1.50", 5060)
    with patch(f"{_MODULE}.socket.socket", return_value=sock):
        assert _outbound_ip("10.0.0.9") == "192.168.1.50"
    sock.close.assert_called_once()


def test_outbound_ip_closes_the_socket_even_on_failure() -> None:
    sock = MagicMock()
    sock.connect.side_effect = OSError("нет маршрута")
    with patch(f"{_MODULE}.socket.socket", return_value=sock):
        with pytest.raises(OSError):
            _outbound_ip("10.0.0.9")
    sock.close.assert_called_once()


# ─── Состояние ──────────────────────────────────────────────────────────────


def test_fresh_manager_has_no_call() -> None:
    manager = SipManager("FCM")
    assert not manager.in_call and not manager.holding


def test_state_reflects_held_and_active() -> None:
    manager = SipManager("FCM")
    _held(manager)
    assert manager.holding and not manager.in_call

    _active(manager)
    assert manager.in_call


async def test_detach_silences_callbacks_of_a_superseded_call() -> None:
    """Отвязанный вызов не должен дёргать контроллер поздним отбоем.

    Второй звонок смещает первый; если у смещённого остались колбэки, его
    запоздавший `BYE` погасил бы экран уже нового вызова.
    """
    ended, cancelled = [], []
    manager = SipManager("FCM", on_ended=ended.append, on_cancelled=cancelled.append)
    manager.detach()

    _active(manager)
    manager._on_remote_bye()
    await asyncio.sleep(0)
    _held(manager)
    manager._on_remote_cancel()

    assert ended == [] and cancelled == []


# ─── Отбой с нашей стороны ──────────────────────────────────────────────────


async def test_hangup_of_an_answered_call_says_goodbye() -> None:
    """Завершая разговор, мы сообщаем об этом домофону."""
    manager = SipManager("FCM")
    active = _active(manager)

    await manager.async_hangup()

    active.teardown.assert_awaited_once_with(send_bye=True)
    assert not manager.in_call


async def test_hangup_before_answering_just_releases_the_line() -> None:
    """Отклонённый вызов снимается без прощания — отвечать было нечего."""
    manager = SipManager("FCM")
    held = _held(manager)

    await manager.async_hangup()

    held.release.assert_called_once()
    assert not manager.holding


async def test_hangup_without_a_call_is_harmless() -> None:
    """Отбой на пустом месте зовут из нескольких мест — падать нельзя."""
    await SipManager("FCM").async_hangup()


async def test_hangup_prefers_the_answered_call() -> None:
    """Если есть и держимый, и активный, снимаются оба, а прощание одно."""
    manager = SipManager("FCM")
    active, held = _active(manager), _held(manager)

    await manager.async_hangup()

    active.teardown.assert_awaited_once()
    held.release.assert_not_called()
    assert not manager.in_call and not manager.holding


# ─── Завершение с той стороны ───────────────────────────────────────────────


async def test_remote_goodbye_ends_the_call_without_replying() -> None:
    """Домофон повесил трубку: снимаем вызов, но `BYE` в ответ не шлём."""
    ended = []
    manager = SipManager("FCM", on_ended=lambda: ended.append(True))
    active = _active(manager)

    manager._on_remote_bye()
    await asyncio.sleep(0)

    assert not manager.in_call
    assert ended == [True]
    active.teardown.assert_awaited_once_with(send_bye=False)


async def test_remote_goodbye_without_a_call_is_ignored() -> None:
    ended = []
    manager = SipManager("FCM", on_ended=lambda: ended.append(True))

    manager._on_remote_bye()

    assert ended == []


def test_guest_leaving_before_answer_dismisses_the_screen() -> None:
    """Гость ушёл, не дождавшись: линия снимается, экран гасится сразу."""
    cancelled = []
    manager = SipManager("FCM", on_cancelled=lambda: cancelled.append(True))
    held = _held(manager)

    manager._on_remote_cancel()

    held.release.assert_called_once()
    assert not manager.holding
    assert cancelled == [True]


def test_cancel_without_a_held_call_is_ignored() -> None:
    cancelled = []
    manager = SipManager("FCM", on_cancelled=lambda: cancelled.append(True))

    manager._on_remote_cancel()

    assert cancelled == []


# ─── Микрофон ───────────────────────────────────────────────────────────────


def test_uplink_without_a_source_sends_nothing() -> None:
    """Без микрофона провайдер отдаёт `None` — транспорт подставит тишину."""
    assert SipManager("FCM")._frame_provider() is None


def test_uplink_passes_microphone_frames_through() -> None:
    manager = SipManager("FCM", uplink_provider=lambda: b"mic")
    assert manager._frame_provider() == b"mic"


# ─── Хэндлы вызова ──────────────────────────────────────────────────────────


async def test_answered_call_teardown_releases_everything() -> None:
    """Завершение разговора снимает и звук, и сигнализацию, и задачу отправки."""
    sip, sip_transport = MagicMock(), MagicMock()
    rtp_transport = MagicMock()
    stop = asyncio.Event()
    task = asyncio.get_running_loop().create_task(asyncio.sleep(3600))

    await ActiveCall(sip, sip_transport, rtp_transport, task, stop).teardown()

    assert stop.is_set()
    sip.send_bye.assert_called_once()
    assert task.cancelled() or task.cancelling()
    rtp_transport.close.assert_called_once()
    sip.close.assert_called_once()
    sip_transport.close.assert_called_once()


async def test_teardown_can_skip_the_goodbye() -> None:
    """При отбое с той стороны прощание уже пришло — второе не нужно."""
    sip = MagicMock()
    task = asyncio.get_running_loop().create_task(asyncio.sleep(3600))

    await ActiveCall(sip, MagicMock(), MagicMock(), task, asyncio.Event()).teardown(
        send_bye=False
    )

    sip.send_bye.assert_not_called()


def test_held_call_release_closes_both_sockets() -> None:
    sip, transport = MagicMock(), MagicMock()

    HeldCall(sip, transport, MagicMock(), ("10.0.0.9", 5060), "10.0.0.2").release()

    sip.close.assert_called_once()
    transport.close.assert_called_once()
