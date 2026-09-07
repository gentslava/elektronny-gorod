"""Разбор входящих SIP-сообщений: вызов, отмена, отбой, авторизация.

Профиль регистрации покрыт в `test_sip_protocol.py`. Здесь — то, что
происходит уже во время звонка. Ошибка на этом слое означает пропущенный
вызов домофона или экран, который не гаснет после того, как гость ушёл.
"""
from __future__ import annotations

import asyncio

import pytest

from custom_components.elektronny_gorod.sip.protocol import SipProtocol

_CREDS = {"login": "000", "password": "secret", "realm": "r.example"}


class _Transport:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple | None]] = []
        self.closed = False

    def get_extra_info(self, name: str):
        return ("10.0.0.2", 5066) if name == "sockname" else None

    def sendto(self, data: bytes, addr: tuple | None = None) -> None:
        self.sent.append((data, addr))

    def close(self) -> None:
        self.closed = True


def _protocol(**kwargs) -> tuple[SipProtocol, _Transport]:
    protocol = SipProtocol(_CREDS, "10.0.0.2", "FCM", "Myhome/android", **kwargs)
    transport = _Transport()
    protocol.connection_made(transport)  # type: ignore[arg-type]
    transport.sent.clear()  # REGISTER при подключении нас здесь не интересует
    return protocol, transport


def _request(method: str, *, extra: str = "") -> bytes:
    return (
        f"{method} sip:000@r.example SIP/2.0\r\n"
        "Via: SIP/2.0/UDP 10.0.0.9:5060;branch=z9hG4bKdoor\r\n"
        "From: <sip:door@r.example>;tag=doortag\r\n"
        "To: <sip:000@r.example>\r\n"
        "Call-ID: call-42\r\n"
        f"CSeq: 1 {method}\r\n"
        f"{extra}"
        "Content-Length: 0\r\n\r\n"
    ).encode()


def _sent_text(transport: _Transport) -> str:
    return "".join(data.decode() for data, _ in transport.sent)


# ─── Входящий вызов ─────────────────────────────────────────────────────────


async def test_incoming_invite_is_handed_over() -> None:
    """Звонок домофона доезжает до ожидающего его кода."""
    protocol, transport = _protocol()
    protocol.invite = asyncio.get_running_loop().create_future()

    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))

    assert protocol.invite.done()
    message, addr = protocol.invite.result()
    assert message.start_line.startswith("INVITE")
    assert addr == ("10.0.0.9", 5060)


async def test_second_invite_does_not_break_the_first() -> None:
    """Повтор INVITE (домофон дублирует по UDP) не роняет обработку."""
    protocol, _ = _protocol()
    protocol.invite = asyncio.get_running_loop().create_future()

    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))
    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))

    assert protocol.invite.done()


def test_trying_keeps_the_call_ringing() -> None:
    """`100 Trying` удерживает вызов, не отвечая на него.

    Без этого домофон считает, что мы не отвечаем, и снимает звонок раньше,
    чем человек успеет нажать «Ответить».
    """
    protocol, transport = _protocol()
    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))
    transport.sent.clear()

    protocol.send_trying()

    assert "100 Trying" in _sent_text(transport)


def test_trying_without_a_call_sends_nothing() -> None:
    protocol, transport = _protocol()
    protocol.send_trying()
    assert transport.sent == []


# ─── Отмена и отбой ─────────────────────────────────────────────────────────


def test_cancel_ends_the_ringing_and_notifies() -> None:
    """Гость ушёл до ответа: подтверждаем отмену и гасим экран вызова.

    `487` на удерживаемый вызов обязателен — иначе домофон продолжает считать
    вызов активным.
    """
    cancelled: list[bool] = []
    protocol, transport = _protocol(on_cancel=lambda: cancelled.append(True))
    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))
    transport.sent.clear()

    protocol.datagram_received(_request("CANCEL"), ("10.0.0.9", 5060))

    text = _sent_text(transport)
    assert "200 OK" in text and "487" in text
    assert cancelled == [True]


def test_bye_ends_the_conversation() -> None:
    """Домофон повесил трубку — подтверждаем и сообщаем наверх."""
    ended: list[bool] = []
    protocol, transport = _protocol(on_bye=lambda: ended.append(True))

    protocol.datagram_received(_request("BYE"), ("10.0.0.9", 5060))

    assert "200 OK" in _sent_text(transport)
    assert ended == [True]


@pytest.mark.parametrize("method", ["OPTIONS", "NOTIFY", "INFO"])
def test_service_requests_are_acknowledged(method: str) -> None:
    """Служебные запросы подтверждаем, иначе домофон считает нас мёртвыми."""
    protocol, transport = _protocol()

    protocol.datagram_received(_request(method), ("10.0.0.9", 5060))

    assert "200 OK" in _sent_text(transport)


def test_unknown_method_is_ignored() -> None:
    protocol, transport = _protocol()
    protocol.datagram_received(_request("MESSAGE"), ("10.0.0.9", 5060))
    assert transport.sent == []


def test_broken_packet_does_not_kill_the_socket() -> None:
    """Битый пакет не должен обрывать приём вызовов.

    Сокет один на всё время ожидания звонка: исключение здесь означало бы,
    что домофон больше не дозвонится до конца сессии.
    """
    def explode() -> None:
        raise RuntimeError("обработчик упал")

    protocol, transport = _protocol(on_bye=explode)

    # Пакет разбирается, но обработчик бросает — именно этот путь и защищён.
    protocol.datagram_received(_request("BYE"), ("10.0.0.9", 5060))

    # Сокет жив: следующий вызов по-прежнему доезжает.
    protocol.datagram_received(_request("OPTIONS"), ("10.0.0.9", 5060))
    assert "200 OK" in _sent_text(transport)


# ─── Авторизация регистрации ────────────────────────────────────────────────


def _challenge(code: str, params: str) -> bytes:
    return (
        f"SIP/2.0 {code} Unauthorized\r\n"
        "Via: SIP/2.0/UDP 10.0.0.2:5066\r\n"
        "From: <sip:000@r.example>;tag=local\r\n"
        "To: <sip:000@r.example>\r\n"
        "Call-ID: reg-1\r\n"
        "CSeq: 1 REGISTER\r\n"
        f"WWW-Authenticate: Digest {params}\r\n"
        "Content-Length: 0\r\n\r\n"
    ).encode()


@pytest.mark.parametrize("code", ["401", "407"])
def test_challenge_is_answered_with_credentials(code: str) -> None:
    """На запрос пароля отвечаем повторной регистрацией с подписью."""
    protocol, transport = _protocol()

    protocol.datagram_received(
        _challenge(code, 'realm="r.example", nonce="abc123"'), ("10.0.0.9", 5060)
    )

    text = _sent_text(transport)
    assert "REGISTER" in text and "Authorization: Digest" in text
    assert "secret" not in text, "пароль уходит только подписью"


def test_challenge_without_nonce_is_not_answered() -> None:
    """Без одноразового значения подписать нечем — молчим, а не шлём мусор."""
    protocol, transport = _protocol()

    protocol.datagram_received(_challenge("401", 'realm="r.example"'), ("10.0.0.9", 5060))

    assert transport.sent == []


async def test_successful_registration_is_reported() -> None:
    protocol, _ = _protocol()
    protocol.registered = asyncio.get_running_loop().create_future()

    protocol.datagram_received(
        b"SIP/2.0 200 OK\r\nCSeq: 1 REGISTER\r\nContent-Length: 0\r\n\r\n",
        ("10.0.0.9", 5060),
    )

    assert protocol.registered.result() is True


async def test_unrelated_response_is_ignored() -> None:
    """Ответ не на регистрацию не должен трогать её состояние."""
    protocol, _ = _protocol()
    protocol.registered = asyncio.get_running_loop().create_future()

    protocol.datagram_received(
        b"SIP/2.0 200 OK\r\nCSeq: 1 INVITE\r\nContent-Length: 0\r\n\r\n",
        ("10.0.0.9", 5060),
    )

    assert not protocol.registered.done()


async def test_registration_failure_leaves_us_waiting() -> None:
    """Отказ регистрации не выдаётся за успех."""
    protocol, _ = _protocol()
    protocol.registered = asyncio.get_running_loop().create_future()

    protocol.datagram_received(
        b"SIP/2.0 403 Forbidden\r\nCSeq: 1 REGISTER\r\nContent-Length: 0\r\n\r\n",
        ("10.0.0.9", 5060),
    )

    assert not protocol.registered.done()


# ─── Ответ на вызов и завершение ────────────────────────────────────────────


def test_answering_sends_media_details_and_remembers_the_dialog() -> None:
    """В ответе уходят адрес и порт для звука, а диалог запоминается для отбоя."""
    protocol, transport = _protocol()
    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))
    message = protocol._invite_msg
    transport.sent.clear()

    protocol.answer(message, ("10.0.0.9", 5060), "10.0.0.2", 40000, 0, "PCMU")

    text = _sent_text(transport)
    assert "200 OK" in text and "40000" in text and "PCMU" in text
    assert protocol.dialog is not None, "без диалога отбой отправить не выйдет"


def test_hangup_without_a_dialog_sends_nothing() -> None:
    protocol, transport = _protocol()
    protocol.send_bye()
    assert transport.sent == []


def test_hangup_uses_the_remembered_dialog() -> None:
    protocol, transport = _protocol()
    protocol.datagram_received(_request("INVITE"), ("10.0.0.9", 5060))
    protocol.answer(protocol._invite_msg, ("10.0.0.9", 5060), "10.0.0.2", 40000, 0, "PCMU")
    transport.sent.clear()

    protocol.send_bye()

    assert "BYE" in _sent_text(transport)


def test_close_releases_the_socket() -> None:
    protocol, transport = _protocol()
    protocol.close()
    assert transport.closed and protocol.transport is None
    protocol.close()  # повторный отбой не должен падать
