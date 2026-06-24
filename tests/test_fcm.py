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
        "GateName": "Подъезд 1", "Apartment": "57", "Call-ID": "C1", "AllowOpen": "true",
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
    fake_client.stop = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    api.register_push_device.assert_awaited_once_with("FCMTOKEN")
    fake_client.start.assert_awaited_once()
    await listener.async_stop()


async def test_async_start_graceful_on_error(hass: HomeAssistant):
    """Сбой checkin не бросает (setup entry не падает), client сброшен."""
    listener, _ = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(side_effect=RuntimeError("google down"))
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    assert listener._client is None
    await listener.async_stop()


async def test_async_start_disables_abort_count(hass: HomeAssistant):
    """abort_on_sequential_error_count=None — receiver не умирает после N ошибок."""
    listener, _ = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(return_value="T")
    fake_client.start = AsyncMock()
    fake_client.stop = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"), \
         patch("firebase_messaging.FcmPushClientConfig") as cfg_cls:
        await listener.async_start()
        cfg_cls.assert_called_once_with(abort_on_sequential_error_count=None)
        await listener.async_stop()


async def test_watchdog_reconnects_dead_client(hass: HomeAssistant):
    """Watchdog видит мёртвый receiver (is_started=False) → переподнимает."""
    listener, _ = _listener(hass)
    dead = MagicMock()
    dead.checkin_or_register = AsyncMock(return_value="T1")
    dead.start = AsyncMock()
    dead.stop = AsyncMock()
    dead.is_started = MagicMock(return_value=False)
    fresh = MagicMock()
    fresh.checkin_or_register = AsyncMock(return_value="T2")
    fresh.start = AsyncMock()
    fresh.stop = AsyncMock()
    fresh.is_started = MagicMock(return_value=True)
    with patch("firebase_messaging.FcmPushClient", side_effect=[dead, fresh]), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
        assert listener._client is dead
        await listener._async_watchdog()
        assert listener._client is fresh
        dead.stop.assert_awaited_once()
        fresh.start.assert_awaited_once()
        await listener.async_stop()


async def test_watchdog_skips_healthy_client(hass: HomeAssistant):
    """Watchdog при живом receiver (is_started=True) — ничего не делает."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.checkin_or_register = AsyncMock(return_value="T")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.is_started = MagicMock(return_value=True)
    with patch("firebase_messaging.FcmPushClient", return_value=client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
        await listener._async_watchdog()
        client.stop.assert_not_awaited()
        assert listener._client is client
        await listener.async_stop()


async def test_async_start_idempotent_single_watchdog(hass: HomeAssistant):
    """Повторный async_start не плодит второй watchdog-таймер."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.checkin_or_register = AsyncMock(return_value="T")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.is_started = MagicMock(return_value=True)
    with patch("firebase_messaging.FcmPushClient", return_value=client), \
         patch("firebase_messaging.FcmRegisterConfig"), \
         patch(
             "custom_components.elektronny_gorod.fcm.async_track_time_interval",
             return_value=MagicMock(),
         ) as track:
        await listener.async_start()
        await listener.async_start()
        track.assert_called_once()
        await listener.async_stop()
