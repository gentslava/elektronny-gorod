"""Unit-тесты SipManager.accept() на malformed SDP из сети (P1-1).

INVITE body — untrusted network input. accept() обязан **degrade** (release held +
return False) на битом SDP, а не бросать ValueError/IndexError: иначе исключение
всплывает в DoorbellCallController.async_answer → AudioBridge (ffmpeg + HTTP-сервер)
течёт, а потреблённый _held не даёт повторить ответ.

Сетевой happy-path accept() (RTP latching) проверяется probe/живым звонком —
здесь только degrade-ветка, которая срабатывает ДО любого socket-I/O.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.elektronny_gorod.sip.manager import SipManager


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
