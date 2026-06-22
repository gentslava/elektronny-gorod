"""FCM listener — серверный приём realtime-пуша о вызове домофона.

Эмулирует регистрацию Android-устройства в FCM (firebase-messaging, project
ntk-myhome), привязывает токен у оператора (api.register_push_device) и держит
MTalk-сокет. На CALL_INCOMING / CALL_END_ANSWERED_MOBILE рассылает SIGNAL_DOORBELL
→ event-сущность (event.py).

⚠️ Флоу опирается на приватные API Google (ADR-0011) — весь он под graceful
degradation: при любом сбое логируем warning, интеграция продолжает работать
(polling-данные), событие вызова просто не стреляет. Setup entry не падает.

Источник канала и payload — research/intercom-call-probe/FINDINGS.md.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import ElektronnyGorodAPI
from .const import (
    CONF_FCM_CREDENTIALS,
    FCM_API_KEY,
    FCM_APP_ID,
    FCM_BUNDLE_ID,
    FCM_PROJECT_ID,
    FCM_SENDER_ID,
    LOGGER,
    SIGNAL_DOORBELL,
)

# PushType (FCM) → event_type сущности.
_PUSH_TYPE_EVENT = {
    "CALL_INCOMING": "ring",
    "CALL_END_ANSWERED_MOBILE": "ended",
}


class DoorbellFcmListener:
    """Держит FCM-соединение и рассылает событие вызова через dispatcher."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: ElektronnyGorodAPI
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._api = api
        self._client: Any = None

    async def async_start(self) -> None:
        """checkin/register → привязка токена у оператора → start MTalk-сокет."""
        try:
            from firebase_messaging import FcmPushClient, FcmRegisterConfig
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "FCM: firebase-messaging недоступна (%s) — событие вызова отключено", err
            )
            return

        try:
            config = FcmRegisterConfig(
                project_id=FCM_PROJECT_ID,
                app_id=FCM_APP_ID,
                api_key=FCM_API_KEY,
                messaging_sender_id=FCM_SENDER_ID,
                bundle_id=FCM_BUNDLE_ID,
            )
            credentials = self._entry.data.get(CONF_FCM_CREDENTIALS)
            self._client = FcmPushClient(
                self._on_notification,
                config,
                credentials,
                self._on_credentials_updated,
            )
            fcm_token = await self._client.checkin_or_register()
            if not await self._api.register_push_device(fcm_token):
                LOGGER.warning(
                    "FCM: привязка push-токена у оператора не удалась — пуши могут не прийти"
                )
            await self._client.start()
            LOGGER.info("FCM doorbell listener запущен")
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "FCM: не удалось запустить listener (%s) — событие вызова отключено", err
            )
            self._client = None

    async def async_stop(self) -> None:
        """Остановить MTalk-сокет (вызывается на unload entry)."""
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.stop()
            except Exception:  # noqa: BLE001
                pass

    @callback
    def _on_credentials_updated(self, credentials: dict, *_: Any) -> None:
        """Персист FCM-creds в entry.data — стабильный токен между рестартами."""
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_FCM_CREDENTIALS: credentials},
        )

    @callback
    def _on_notification(self, notification: dict, persistent_id: str, *_: Any) -> None:
        """Callback firebase-messaging: парсит push → SIGNAL_DOORBELL."""
        data = (notification or {}).get("data") or {}
        push_type = data.get("PushType") or data.get("google.c.a.m_l")
        event_type = _PUSH_TYPE_EVENT.get(push_type)
        if not event_type:
            return
        attributes: dict[str, Any] = {
            "gate_name": data.get("GateName"),
            "apartment": data.get("Apartment"),
            "call_id": data.get("Call-ID"),
            "allow_open": data.get("AllowOpen"),
            "call_started": data.get("CallStarted"),
            "call_invalidated": data.get("CallInvalidated"),
        }
        if event_type == "ended":
            attributes["reason"] = "answered_elsewhere"
        async_dispatcher_send(
            self._hass,
            SIGNAL_DOORBELL,
            {
                "event_type": event_type,
                "place_id": str(data.get("PlaceId") or ""),
                "access_control_id": str(data.get("AccessControlId") or ""),
                "attributes": attributes,
            },
        )
