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

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

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

# PushType (FCM) → event_type сущности. Таксономия `ended`/`reason` — в
# docs/architecture/api-reference.md (раздел «Вызов домофона»).
_PUSH_TYPE_EVENT = {
    "CALL_INCOMING": "ring",
    "CALL_END_ANSWERED_MOBILE": "ended",
}

# Watchdog: интервал контроля живости FCM-сокета. С
# abort_on_sequential_error_count=None библиотека не умирает от сетевых сбоев,
# но watchdog ловит фатальную смерть клиента (или провал первичного checkin) и
# поднимает заново — иначе пуши о вызове молча отвалятся (инцидент 2026-06-24:
# сетевой блип → 3 ошибки подряд → receiver выключился, юзер не узнал).
FCM_WATCHDOG_INTERVAL = timedelta(minutes=2)


class DoorbellFcmListener:
    """Держит FCM-соединение и рассылает событие вызова через dispatcher."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: ElektronnyGorodAPI
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._api = api
        self._client: Any = None
        # Watchdog: unsub периодического контроля живости + guard от
        # перекрытия повторных переподнятий.
        self._watchdog_unsub: Any = None
        self._reconnecting = False
        # FCM push-токен (после checkin_or_register). Нужен SIP-ответу для
        # push-params REGISTER (pn-tok=...) — см. sip/call_controller.py.
        self.fcm_token: str | None = None

    async def async_start(self) -> None:
        """Первичный коннект + запуск watchdog'а (контроль живости сокета)."""
        await self._async_connect()
        if self._watchdog_unsub is None:
            self._watchdog_unsub = async_track_time_interval(
                self._hass, self._async_watchdog, FCM_WATCHDOG_INTERVAL
            )

    async def _async_connect(self) -> None:
        """checkin/register → привязка токена у оператора → start MTalk-сокет.

        `abort_on_sequential_error_count=None` — библиотека НЕ выключает receiver
        после N подряд ошибок соединения (дефолт 3), а продолжает переподключаться.
        """
        try:
            from firebase_messaging import (
                FcmPushClient,
                FcmPushClientConfig,
                FcmRegisterConfig,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "FCM: firebase-messaging недоступна (%s) — событие вызова отключено", err
            )
            return

        try:
            register_config = FcmRegisterConfig(
                project_id=FCM_PROJECT_ID,
                app_id=FCM_APP_ID,
                api_key=FCM_API_KEY,
                messaging_sender_id=FCM_SENDER_ID,
                bundle_id=FCM_BUNDLE_ID,
            )
            credentials = self._entry.data.get(CONF_FCM_CREDENTIALS)
            self._client = FcmPushClient(
                self._on_notification,
                register_config,
                credentials,
                self._on_credentials_updated,
                config=FcmPushClientConfig(abort_on_sequential_error_count=None),
            )
            fcm_token = await self._client.checkin_or_register()
            self.fcm_token = fcm_token
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

    async def _async_watchdog(self, _now: Any = None) -> None:
        """Периодически: если push-receiver неактивен — переподнять listener.

        Ловит фатальную смерть клиента и провал первичного checkin (client=None).
        Guard `_reconnecting` — против перекрытия с предыдущим переподнятием.
        """
        if self._reconnecting:
            return
        client = self._client
        if client is not None and client.is_started():
            return
        # is_started()==False = receiver мёртв ЛИБО ещё в фазе MCS-login.
        # Интервал watchdog (2 мин) ≫ времени login (секунды) → к тику живой
        # клиент уже STARTED; не-STARTED на тике = реально залип/умер →
        # переподнимаем (grace-период не нужен и лишь задержал бы восстановление
        # действительно зависшего login).
        self._reconnecting = True
        try:
            LOGGER.warning("FCM: push-receiver неактивен — переподнимаю listener")
            await self._async_disconnect()
            await self._async_connect()
        finally:
            self._reconnecting = False

    async def _async_disconnect(self) -> None:
        """Остановить текущий MTalk-сокет (watchdog НЕ трогаем)."""
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.stop()
            except Exception:  # noqa: BLE001
                pass

    async def async_stop(self) -> None:
        """Полная остановка на unload entry: отменить watchdog + закрыть сокет."""
        if self._watchdog_unsub is not None:
            self._watchdog_unsub()
            self._watchdog_unsub = None
        await self._async_disconnect()

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
            # Не дропаем молча: если оператор шлёт end-пуш на сброс/таймаут
            # неизвестным типом — увидим его здесь и замаппим в следующем слайсе.
            LOGGER.debug("FCM: PushType %s не обрабатывается — пропуск", push_type)
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
