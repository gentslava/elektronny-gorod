"""Unit-тесты SipManager.accept() на malformed SDP из сети (P1-1).

INVITE body — untrusted network input. accept() обязан **degrade** (release held +
return False) на битом SDP, а не бросать ValueError/IndexError: иначе исключение
всплывает в DoorbellCallController.async_answer → AudioBridge (ffmpeg + HTTP-сервер)
течёт, а потреблённый _held не даёт повторить ответ.

Сетевой happy-path accept() (RTP latching) проверяется probe/живым звонком —
здесь только degrade-ветка, которая срабатывает ДО любого socket-I/O.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.sip.manager import RTP_LOCAL_PORT, SipManager


def _held_with_body(body: str) -> MagicMock:
    """Фейковый HeldCall: только invite_msg.body нужен для degrade-ветки accept()."""
    held = MagicMock()
    held.invite_msg.body = body
    return held


def _manager_holding(body: str) -> tuple[SipManager, MagicMock]:
    mgr = SipManager(fcm_token="TOK")
    held = _held_with_body(body)
    mgr._held = held
    return mgr, held


async def test_accept_degrades_on_non_numeric_media_port() -> None:
    # m=audio с нечисловым портом → release + False, без socket-I/O и без ValueError.
    mgr, held = _manager_holding(
        "v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio NOTANUMBER RTP/AVP 0\r\n"
    )
    assert await mgr.accept() is False
    held.release.assert_called_once()
    assert mgr._held is None


async def test_accept_degrades_on_truncated_media_line() -> None:
    # m=audio без порта → release + False, без IndexError.
    mgr, held = _manager_holding("v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio\r\n")
    assert await mgr.accept() is False
    held.release.assert_called_once()
    assert mgr._held is None


async def test_accept_degrades_on_empty_payload_types() -> None:
    # m=audio 7078 RTP/AVP с пустым списком payload → int(fmts[0]) бы кинул IndexError.
    mgr, held = _manager_holding("v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio 7078 RTP/AVP\r\n")
    assert await mgr.accept() is False
    held.release.assert_called_once()
    assert mgr._held is None


async def test_accept_without_held_returns_false() -> None:
    # Без держимого вызова accept() — игнор (регресс-страховка существующего поведения).
    mgr = SipManager(fcm_token="TOK")
    assert await mgr.accept() is False


async def test_register_and_hold_uses_official_app_registration_profile() -> None:
    """FCM ring registration mirrors the stock Android SIP Contact and headers."""
    registered = asyncio.get_running_loop().create_future()
    registered.set_result(True)
    invite = asyncio.get_running_loop().create_future()
    invite.set_result((MagicMock(), ("192.0.2.1", 5060)))
    protocol = MagicMock(registered=registered, invite=invite)
    transport = MagicMock()

    async def _open_endpoint(factory, **_kwargs):
        assert factory() is protocol
        return transport, protocol

    loop = asyncio.get_running_loop()
    with patch(
        "custom_components.elektronny_gorod.sip.manager.socket.gethostbyname",
        return_value="192.0.2.1",
    ), patch(
        "custom_components.elektronny_gorod.sip.manager._outbound_ip",
        return_value="192.0.2.2",
    ), patch(
        "custom_components.elektronny_gorod.sip.manager.SipProtocol",
        return_value=protocol,
    ) as protocol_cls, patch.object(
        loop, "create_datagram_endpoint", AsyncMock(side_effect=_open_endpoint)
    ):
        manager = SipManager(fcm_token="FCM")
        held = await manager.register_and_hold(
            AsyncMock(
                return_value={"login": "user", "password": "secret", "realm": "sip.test"}
            ),
            fcm_call_id="FCM-CALL",
        )

    assert held is True
    assert protocol_cls.call_args.kwargs["fcm_call_id"] == "FCM-CALL"
    assert protocol_cls.call_args.kwargs["accept_sdp"] is True
    assert protocol_cls.call_args.kwargs["include_contact_transport"] is False


@pytest.mark.parametrize(
    "body",
    [
        "v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio NOTANUMBER RTP/AVP 0\r\n",
        "v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio\r\n",
        "v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio 7078 RTP/AVP\r\n",
        "",  # пустой body
    ],
)
async def test_accept_never_raises_on_malformed_sdp(body: str) -> None:
    # Никакой malformed body не должен бросать исключение наружу (утечка моста).
    mgr, _ = _manager_holding(body)
    result = await mgr.accept()
    assert result is False


# --- async_end: завершить вызов на панели (200 OK → ACK → BYE) -----------------

_OFFER_PCMU = "v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio 4000 RTP/AVP 0\r\n"


def _end_manager(acked: asyncio.Future | None) -> tuple[SipManager, MagicMock, MagicMock]:
    """Менеджер с держимым вызовом; `parent` пишет порядок answer → send_bye → release."""
    mgr, held = _manager_holding(_OFFER_PCMU)
    held.sip.acked = acked
    parent = MagicMock()
    parent.attach_mock(held.sip.answer, "answer")
    parent.attach_mock(held.sip.send_bye, "send_bye")
    parent.attach_mock(held.release, "release")
    return mgr, held, parent


async def test_end_answers_then_hangs_up_held_call() -> None:
    acked = asyncio.get_running_loop().create_future()
    acked.set_result(None)
    mgr, held, parent = _end_manager(acked)

    await mgr.async_end()

    names = [c[0] for c in parent.mock_calls]
    assert names == ["answer", "send_bye", "release"]
    answer_args = held.sip.answer.call_args.args
    assert answer_args[:2] == (held.invite_msg, held.addr)
    assert answer_args[2] == held.local_ip
    assert answer_args[3] == RTP_LOCAL_PORT
    assert answer_args[4] == 0
    assert answer_args[5] == "PCMU/8000"
    assert mgr.holding is False


async def test_end_sends_bye_even_without_ack() -> None:
    pending = asyncio.get_running_loop().create_future()
    mgr, held, parent = _end_manager(pending)

    with patch("custom_components.elektronny_gorod.sip.manager.ACK_TIMEOUT", 0.01):
        await mgr.async_end()

    assert [c[0] for c in parent.mock_calls] == ["answer", "send_bye", "release"]
    assert mgr.holding is False


async def test_end_skips_ack_wait_when_transport_closed() -> None:
    # answer() вернулся рано (транспорт закрыт) → acked остался None → не ждём.
    mgr, held, parent = _end_manager(None)

    await mgr.async_end()

    assert [c[0] for c in parent.mock_calls] == ["answer", "send_bye", "release"]


async def test_end_releases_silently_on_malformed_offer() -> None:
    mgr, held = _manager_holding("v=0\r\nc=IN IP4 10.0.0.1\r\n")

    await mgr.async_end()

    held.sip.answer.assert_not_called()
    held.sip.send_bye.assert_not_called()
    held.release.assert_called_once()
    assert mgr.holding is False


async def test_end_hangs_up_active_call() -> None:
    mgr = SipManager(fcm_token="TOK")
    active = MagicMock()
    active.teardown = AsyncMock()
    mgr._active = active

    await mgr.async_end()

    active.teardown.assert_awaited_once_with(send_bye=True)
    assert mgr.in_call is False


async def test_end_without_call_is_noop() -> None:
    mgr = SipManager(fcm_token="TOK")
    await mgr.async_end()
    assert mgr.in_call is False
    assert mgr.holding is False


async def test_end_waits_for_ack_before_bye() -> None:
    # BYE не должен уходить, пока ACK не пришёл (и не истёк ACK_TIMEOUT).
    loop = asyncio.get_running_loop()
    acked = loop.create_future()
    mgr, held, parent = _end_manager(acked)

    task = loop.create_task(mgr.async_end())
    await asyncio.sleep(0.05)
    assert not task.done()
    held.sip.answer.assert_called_once()
    held.sip.send_bye.assert_not_called()
    held.release.assert_not_called()

    acked.set_result(None)
    await task

    assert [c[0] for c in parent.mock_calls] == ["answer", "send_bye", "release"]


async def test_end_releases_held_call_when_cancelled_during_ack_wait() -> None:
    loop = asyncio.get_running_loop()
    mgr, held, _parent = _end_manager(loop.create_future())

    task = loop.create_task(mgr.async_end())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    held.release.assert_called_once()
    assert mgr.holding is False


async def test_end_releases_held_call_when_answer_raises() -> None:
    mgr, held, _parent = _end_manager(None)
    held.sip.answer.side_effect = OSError("boom")

    with pytest.raises(OSError):
        await mgr.async_end()

    held.release.assert_called_once()
    assert mgr.holding is False
