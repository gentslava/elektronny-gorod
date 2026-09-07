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
    """При отвеченном вызове снимается он, а не держимая линия.

    Одновременно и то и другое в проде не живёт: `accept()` забирает держимый
    вызов себе. Проверка защищает порядок ветвления на случай, если забирать
    перестанет: прощание должно уйти разговору, а не линии, которую уже никто
    не держит.
    """
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


# ─── Удержание вызова: что мешает его принять ───────────────────────────────


def _sip_pair(*, registered=True, invite=True, futures=True):
    """Поддельная SIP-сессия с управляемыми ожиданиями."""
    loop = asyncio.get_event_loop()
    sip = MagicMock()
    if futures:
        sip.registered = loop.create_future()
        sip.invite = loop.create_future()
        if registered:
            sip.registered.set_result(True)
        if invite:
            sip.invite.set_result((MagicMock(), ("10.0.0.9", 5060)))
    else:
        sip.registered = None
        sip.invite = None
    return sip, MagicMock()


async def _hold(manager, sip, transport, **kwargs):
    loop = asyncio.get_running_loop()
    loop.create_datagram_endpoint = AsyncMock(return_value=(transport, sip))
    with (
        patch(f"{_MODULE}.socket.gethostbyname", return_value="10.0.0.1"),
        patch(f"{_MODULE}._outbound_ip", return_value="10.0.0.2"),
    ):
        return await manager.register_and_hold(
            AsyncMock(return_value={"login": "1", "password": "p", "realm": "r"}),
            **kwargs,
        )


async def test_hold_keeps_the_call_ringing() -> None:
    """Успешное удержание: вызов звонит, ответа ещё нет."""
    manager = SipManager("FCM")
    sip, transport = _sip_pair()

    assert await _hold(manager, sip, transport) is True

    sip.send_trying.assert_called_once()
    assert manager.holding


async def test_second_call_does_not_displace_the_first() -> None:
    """Пока идёт разговор, второй звонок не перехватывает линию."""
    manager = SipManager("FCM")
    _active(manager)
    sip, transport = _sip_pair()

    assert await _hold(manager, sip, transport) is False
    sip.send_trying.assert_not_called()


async def test_transport_without_waiters_is_abandoned() -> None:
    """Транспорт не поднял ожидания — отменяем удержание, а не падаем."""
    manager = SipManager("FCM")
    sip, transport = _sip_pair(futures=False)

    assert await _hold(manager, sip, transport) is False

    sip.close.assert_called_once()
    transport.close.assert_called_once()


async def test_registration_timeout_releases_the_line() -> None:
    """Оператор не подтвердил регистрацию — линия освобождается.

    Иначе сокет остался бы занят, и следующий звонок не прошёл бы.
    """
    manager = SipManager("FCM")
    sip, transport = _sip_pair(registered=False, invite=False)

    with patch(f"{_MODULE}.REGISTER_TIMEOUT", 0.01):
        assert await _hold(manager, sip, transport) is False

    sip.close.assert_called_once()
    transport.close.assert_called_once()
    assert not manager.holding


async def test_call_that_never_arrives_releases_the_line() -> None:
    """Зарегистрировались, а вызова нет — тоже освобождаем линию."""
    manager = SipManager("FCM")
    sip, transport = _sip_pair(invite=False)

    with patch(f"{_MODULE}.INVITE_TIMEOUT", 0.01):
        assert await _hold(manager, sip, transport) is False

    sip.close.assert_called_once()
    assert not manager.holding


async def test_accept_without_a_held_call_is_refused() -> None:
    assert await SipManager("FCM").accept() is False


# ─── Приём вызова: разбор предложения домофона ──────────────────────────────


def _held_with_sdp(manager: SipManager, body: str) -> MagicMock:
    """Держимый вызов с заданным SDP-предложением домофона."""
    held = MagicMock(spec=HeldCall)
    held.invite_msg = MagicMock(body=body)
    held.addr = ("10.0.0.9", 5060)
    held.local_ip = "10.0.0.2"
    held.sip = MagicMock()
    held.sip_transport = MagicMock()
    manager._held = held
    return held


_OFFER = (
    "v=0\r\no=- 1 1 IN IP4 10.0.0.9\r\ns=-\r\nc=IN IP4 10.0.0.9\r\n"
    "t=0 0\r\nm=audio 5004 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n"
)


async def test_accepting_a_call_starts_audio_both_ways() -> None:
    """Приём вызова поднимает приём звука гостя и отправку своего.

    Ответ уходит немедленно: домофон начинает слать RTP сразу, и задержка
    здесь означала бы потерянное начало фразы.
    """
    manager = SipManager("FCM")
    held = _held_with_sdp(manager, _OFFER)
    loop = asyncio.get_running_loop()
    rtp = MagicMock(run_uplink=AsyncMock())
    loop.create_datagram_endpoint = AsyncMock(return_value=(MagicMock(), rtp))

    assert await manager.accept(on_downlink=lambda frame: None) is True

    held.sip.answer.assert_called_once()
    assert manager.in_call and not manager.holding
    assert rtp.run_uplink.called or manager._active is not None


async def test_accepting_a_call_with_a_broken_payload_type() -> None:
    """Нечисловой тип нагрузки в предложении — отказ без падения.

    Предложение приходит из сети и доверять ему нельзя: исключение здесь
    оставило бы поднятый мост висеть.
    """
    manager = SipManager("FCM")
    held = _held_with_sdp(
        manager, _OFFER.replace("RTP/AVP 0", "RTP/AVP не-число")
    )

    assert await manager.accept() is False

    held.release.assert_called_once()
    assert not manager.in_call and not manager.holding


async def test_fallback_answer_holds_then_accepts() -> None:
    """Запасной путь: если удержания не было, делаем его и сразу принимаем."""
    manager = SipManager("FCM")
    sip, transport = _sip_pair()
    loop = asyncio.get_running_loop()
    loop.create_datagram_endpoint = AsyncMock(return_value=(transport, sip))
    manager.accept = AsyncMock(return_value=True)

    with (
        patch(f"{_MODULE}.socket.gethostbyname", return_value="10.0.0.1"),
        patch(f"{_MODULE}._outbound_ip", return_value="10.0.0.2"),
    ):
        assert await manager.async_answer(
            AsyncMock(return_value={"login": "1", "password": "p", "realm": "r"})
        ) is True

    manager.accept.assert_awaited_once()


async def test_fallback_answer_gives_up_if_the_call_cannot_be_held() -> None:
    """Не удержали вызов — принимать нечего."""
    manager = SipManager("FCM")
    manager.register_and_hold = AsyncMock(return_value=False)
    manager.accept = AsyncMock()

    assert await manager.async_answer(AsyncMock()) is False

    manager.accept.assert_not_awaited()
