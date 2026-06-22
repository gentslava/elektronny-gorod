"""Тесты FCM-listener (fcm.py).

Без реального Google: парсинг пуша → SIGNAL_DOORBELL; старт регистрирует токен;
сбой checkin не валит (graceful degradation). firebase-messaging замокан.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.elektronny_gorod.const import SIGNAL_DOORBELL
from custom_components.elektronny_gorod.fcm import DoorbellFcmListener


def _listener(hass: HomeAssistant):
    entry = MagicMock()
    entry.data = {}
    api = MagicMock()
    api.register_push_device = AsyncMock(return_value=True)
    return DoorbellFcmListener(hass, entry, api), api


def _capture(hass: HomeAssistant) -> list:
    got: list = []
    async_dispatcher_connect(hass, SIGNAL_DOORBELL, lambda p: got.append(p))
    return got


async def test_call_incoming_dispatches_ring(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {
        "PushType": "CALL_INCOMING", "PlaceId": "P1", "AccessControlId": "AC1",
        "GateName": "Подъезд 1", "Apartment": "143", "Call-ID": "C1", "AllowOpen": "true",
    }}, "pid")
    await hass.async_block_till_done()
    assert len(got) == 1
    payload = got[0]
    assert payload["event_type"] == "ring"
    assert payload["place_id"] == "P1"
    assert payload["access_control_id"] == "AC1"
    assert payload["attributes"]["call_id"] == "C1"
    assert payload["attributes"]["gate_name"] == "Подъезд 1"


async def test_call_end_dispatches_ended(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {
        "PushType": "CALL_END_ANSWERED_MOBILE", "PlaceId": "P1",
        "AccessControlId": "AC1", "Call-ID": "C1",
    }}, "pid")
    await hass.async_block_till_done()
    assert got[0]["event_type"] == "ended"
    assert got[0]["attributes"]["reason"] == "answered_elsewhere"


async def test_unknown_push_type_ignored(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {"PushType": "SOMETHING_ELSE"}}, "pid")
    await hass.async_block_till_done()
    assert got == []


async def test_async_start_registers_token(hass: HomeAssistant):
    listener, api = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(return_value="FCMTOKEN")
    fake_client.start = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    api.register_push_device.assert_awaited_once_with("FCMTOKEN")
    fake_client.start.assert_awaited_once()


async def test_async_start_graceful_on_error(hass: HomeAssistant):
    """Сбой checkin не бросает (setup entry не падает), client сброшен."""
    listener, _ = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(side_effect=RuntimeError("google down"))
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    assert listener._client is None
