"""Тесты WS-команды intercom_uplink (uplink_ws.py).

Phase C, ADR-0013 (механизм #1 — HA WS-binary): авторизованный HA-WebSocket
доставляет микрофон браузера в интеграцию. Команда `elektronny_gorod/intercom_uplink`:
- находит контроллер с активным вызовом → регистрирует binary-handler;
- бинарный payload → controller.feed_uplink(payload, sample_rate);
- нет активного вызова → send_error;
- unsub в connection.subscriptions[msg_id] (авто-cleanup при disconnect).

Connection замокан — сетевой слой HA WS не юнит-тестируем (доказывается интеграцией).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from unittest.mock import patch

from custom_components.elektronny_gorod.const import DOMAIN
from custom_components.elektronny_gorod.uplink_ws import (
    _SIP_DATA,
    async_register_uplink_ws_command,
    ws_intercom_uplink,
)

_UWS = "custom_components.elektronny_gorod.uplink_ws"


def _connection() -> MagicMock:
    """Мок WS-connection: register_binary_handler отдаёт (handler_id, unsub)."""
    conn = MagicMock()
    conn.unsub = MagicMock()
    conn.async_register_binary_handler = MagicMock(
        return_value=(7, conn.unsub)
    )
    conn.subscriptions = {}
    return conn


def _hass_with_controller(controller) -> MagicMock:
    hass = MagicMock()
    hass.data = {_SIP_DATA: {"entry1": controller}}
    return hass


def _active_controller() -> MagicMock:
    """Контроллер с активным вызовом (active_call_media() не None)."""
    c = MagicMock()
    c.active_call_media.return_value = ("cam", MagicMock())
    return c


def _idle_controller() -> MagicMock:
    c = MagicMock()
    c.active_call_media.return_value = None
    c._manager = None
    return c


def test_ws_registers_binary_handler_for_active_call():
    controller = _active_controller()
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 5, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)

    conn.async_register_binary_handler.assert_called_once()
    conn.send_result.assert_called_once()
    assert conn.send_result.call_args.args[0] == 5
    assert conn.send_result.call_args.args[1] == {"handler_id": 7}
    conn.send_error.assert_not_called()


def test_ws_no_active_call_sends_error():
    controller = _idle_controller()
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 5, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args.args[0] == 5
    assert conn.send_error.call_args.args[1] == "no_active_call"
    conn.async_register_binary_handler.assert_not_called()


def test_ws_binary_payload_routed_to_feed_uplink():
    controller = _active_controller()
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 5, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 16000}

    ws_intercom_uplink(hass, conn, msg)

    # bin-handler — первый позиционный аргумент async_register_binary_handler.
    handler = conn.async_register_binary_handler.call_args.args[0]
    handler(hass, conn, b"\x00\x01\x02\x03")
    controller.feed_uplink.assert_called_once_with(b"\x00\x01\x02\x03", 16000)


def test_ws_handler_does_not_raise_on_bad_payload():
    # feed_uplink бросил (регрессия UplinkSink) → handler глушит, WS не падает.
    controller = _active_controller()
    controller.feed_uplink.side_effect = ValueError("bad pcm")
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 5, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)
    handler = conn.async_register_binary_handler.call_args.args[0]
    handler(hass, conn, b"\xff\xfe")  # не должно бросить


def test_ws_unsub_stored_in_subscriptions():
    controller = _active_controller()
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 5, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)

    # unsub binary-handler положен в subscriptions[msg_id] → авто-cleanup на disconnect.
    assert 5 in conn.subscriptions
    conn.subscriptions[5]()
    conn.unsub.assert_called_once()


def test_ws_prefers_active_call_media_then_in_call():
    # active_call_media None, но менеджер in_call (мост не поднялся, degrade) →
    # всё равно регистрируем handler (микрофон важнее видео-моста).
    controller = MagicMock()
    controller.active_call_media.return_value = None
    controller._manager = MagicMock()
    controller._manager.in_call = True
    hass = _hass_with_controller(controller)
    conn = _connection()
    msg = {"id": 9, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)
    conn.async_register_binary_handler.assert_called_once()
    conn.send_error.assert_not_called()


def test_ws_picks_active_controller_among_many():
    # multi-entry: выбирается контроллер с активным вызовом, не первый попавшийся.
    idle = _idle_controller()
    active = _active_controller()
    hass = MagicMock()
    hass.data = {_SIP_DATA: {"e1": idle, "e2": active}}
    conn = _connection()
    msg = {"id": 1, "type": "elektronny_gorod/intercom_uplink", "sample_rate": 48000}

    ws_intercom_uplink(hass, conn, msg)
    handler = conn.async_register_binary_handler.call_args.args[0]
    handler(hass, conn, b"\x01\x02")
    active.feed_uplink.assert_called_once_with(b"\x01\x02", 48000)
    idle.feed_uplink.assert_not_called()


def test_ws_schema_rejects_out_of_range_sample_rate():
    # HA-dispatcher валидирует msg по _ws_schema до вызова handler-а: range отвергает
    # sample_rate вне [8000,192000] → явный отказ на подписке (не тихий дроп кадров).
    import voluptuous as vol

    schema = ws_intercom_uplink._ws_schema
    base = {"id": 5, "type": "elektronny_gorod/intercom_uplink"}
    with pytest.raises(vol.Invalid):
        schema({**base, "sample_rate": 0})
    with pytest.raises(vol.Invalid):
        schema({**base, "sample_rate": 1_000_000})
    # Валидный rate проходит, дефолт подставляется.
    assert schema({**base, "sample_rate": 48000})["sample_rate"] == 48000
    assert schema(base)["sample_rate"] == 48000


def test_register_command_idempotent():
    # Регистрация один раз на интеграцию (multi-entry не дублирует команду).
    hass = MagicMock()
    hass.data = {}
    with patch(f"{_UWS}.websocket_api.async_register_command") as reg:
        async_register_uplink_ws_command(hass)
        async_register_uplink_ws_command(hass)  # второй entry — no-op
    reg.assert_called_once()
