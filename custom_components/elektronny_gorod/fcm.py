"""FCM listener — серверный приём realtime-пуша о вызове домофона.

Эмулирует регистрацию Android-устройства в FCM (firebase-messaging, project
ntk-myhome), привязывает токен у оператора (api.register_push_device) и держит
MTalk-сокет. На CALL_INCOMING / CALL_END_ANSWERED_MOBILE рассылает SIGNAL_DOORBELL
→ event-сущность (event.py).

⚠️ Флоу опирается на приватные API Google (ADR-0011) и работает под graceful
degradation: сбой подключения логируется warning'ом, setup entry не падает,
polling-данные (камеры, замки, баланс, история) продолжают работать — не
стреляет только событие вызова. Единственное исключение из «сбой не мешает
ничему» — неподтверждённая остановка receiver'а при выгрузке: `async_stop()`
вернёт False, `async_unload_entry` в `__init__.py` тоже вернёт False, и HA
сообщит, что нужен рестарт. Так мы не оставляем два живых receiver'а на один
аккаунт — см. `docs/specs/2026-08-10-fcm-circuit-breaker-design.md`.

Источник канала и payload — research/intercom-call-probe/FINDINGS.md.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .api import ElektronnyGorodAPI
from .const import (
    CONF_FCM_CREDENTIALS,
    DOMAIN,
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

# Предохранитель самой firebase-messaging: после N подряд ошибок соединения
# библиотека сама останавливает receiver (`_terminate()` → run_state STOPPING).
#
# Его нельзя отключать (`None`). При `None` проверка в `_try_increment_error_count`
# становится всегда-ложной, `_terminate()` недостижим, и `_listen` бесконечно
# перечитывает мёртвый StreamReader: `readexactly` мгновенно перевыбрасывает
# сохранённый `_exception`, дописывая фрейм в его traceback, а библиотека на
# каждой итерации печатает его целиком через `_logger.exception`. Петля живёт в
# общем event loop, поэтому HA подвисает, а стоимость форматирования растёт
# квадратично (инцидент 2026-08-12, issue #77).
#
# Счётчик CONNECTION обнуляется только реальным сообщением от сервера
# (`_handle_message`, после раннего `return` для LoginResponse), поэтому на
# здоровом сокете heartbeat'ы каждые 10-20 с держат его на нуле, а петля
# «connect → login → разрыв» упирается в лимит и честно гасит receiver.
# Дальше подхватывает watchdog ниже: мёртвый клиент = `is_started() == False`.
FCM_ABORT_AFTER_ERRORS = 3

# Watchdog: интервал контроля живости FCM-сокета. Ловит остановленный
# библиотекой receiver и провал первичного checkin (`client is None`) —
# иначе пуши о вызове молча отвалятся (инцидент 2026-06-24). Восстановление
# ограничено: см. `_async_watchdog` и backoff ниже.
FCM_WATCHDOG_INTERVAL = timedelta(minutes=2)

# Пауза между пробами после того, как circuit разомкнут. Последнее значение
# повторяется бесконечно.
FCM_RETRY_BACKOFFS = (
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
)

_FCM_REPAIR_ISSUE_PREFIX = "fcm_receiver_unavailable"


def fcm_repair_issue_id(entry_id: str) -> str:
    """Вернуть стабильный Repairs issue ID для config entry."""
    return f"{_FCM_REPAIR_ISSUE_PREFIX}_{entry_id}"


@callback
def async_create_fcm_repair_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Show one persistent degraded-FCM issue for a config entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        fcm_repair_issue_id(entry.entry_id),
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="fcm_receiver_unavailable",
        translation_placeholders={"entry_title": entry.title},
    )


@callback
def async_delete_fcm_repair_issue(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Удалить persistent FCM issue одного config entry."""
    ir.async_delete_issue(hass, DOMAIN, fcm_repair_issue_id(entry_id))


class _FcmRecoveryPhase(StrEnum):
    """Per-entry FCM recovery phase."""

    HEALTHY = "healthy"
    SUSPECT = "suspect"
    VERIFYING = "verifying"
    OPEN = "open"


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
        self._transition_lock = asyncio.Lock()
        self._stopping = False
        self._recovery_phase = _FcmRecoveryPhase.HEALTHY
        self._next_probe_at: datetime | None = None
        self._backoff_index = 0
        # FCM push-токен (после checkin_or_register). Нужен SIP-ответу для
        # push-params REGISTER (pn-tok=...) — см. sip/call_controller.py.
        self.fcm_token: str | None = None

    async def async_start(self) -> None:
        """Первичный коннект + запуск watchdog'а (контроль живости сокета)."""
        async with self._transition_lock:
            if self._stopping or self._watchdog_unsub is not None:
                return
            await self._async_connect()
            if self._stopping:
                # Выгрузка успела начаться уже после успешного start() —
                # здесь клиент реальный и его надо закрыть.
                await self._async_disconnect()
                return
            self._watchdog_unsub = async_track_time_interval(
                self._hass, self._async_watchdog, FCM_WATCHDOG_INTERVAL
            )

    async def _async_connect(self) -> None:
        """checkin/register → привязка токена у оператора → start MTalk-сокет.

        Полностью contained: любая ошибка здесь — warning, `self._client`
        остаётся `None`, и watchdog разбирается дальше по своей state machine.
        Клиент публикуется в `self._client` только после успешного `start()`.
        """
        try:
            from firebase_messaging import (
                FcmPushClient,
                FcmPushClientConfig,
                FcmRegisterConfig,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "FCM: firebase-messaging недоступна (%s) — событие вызова отключено",
                type(err).__name__,
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
            # Keep the candidate local until start(): firebase-messaging 0.4.5
            # creates stopping_lock in start(), so stop() is unsafe beforehand.
            client = FcmPushClient(
                self._on_notification,
                register_config,
                credentials,
                self._on_credentials_updated,
                config=FcmPushClientConfig(
                    abort_on_sequential_error_count=FCM_ABORT_AFTER_ERRORS
                ),
                http_client_session=async_get_clientsession(self._hass),
            )
            fcm_token = await client.checkin_or_register()
            self.fcm_token = fcm_token
            # Начатую выгрузку видно только здесь: `async_stop()` выставляет
            # флаг до захвата lock'а и ждёт нас. Нестартовавший клиент просто
            # отбрасываем — `stop()` до `start()` упадёт на `stopping_lock`.
            if self._stopping:
                return
            if not await self._api.register_push_device(fcm_token):
                LOGGER.warning(
                    "FCM: привязка push-токена у оператора не удалась — пуши могут не прийти"
                )
            if self._stopping:
                return
            await client.start()
            self._client = client
            LOGGER.info("FCM doorbell listener запущен")
        except Exception as err:  # noqa: BLE001
            # Текст исключения зависимости может нести credentials/payload —
            # логируем только класс (ADR-0004).
            LOGGER.warning(
                "FCM: не удалось запустить listener (%s) — событие вызова отключено",
                type(err).__name__,
            )

    @callback
    def _async_mark_healthy(self) -> None:
        """Сбросить recovery-state после подтверждённого healthy-тика."""
        recovered = self._recovery_phase in {
            _FcmRecoveryPhase.VERIFYING,
            _FcmRecoveryPhase.OPEN,
        }
        self._recovery_phase = _FcmRecoveryPhase.HEALTHY
        self._next_probe_at = None
        self._backoff_index = 0
        async_delete_fcm_repair_issue(self._hass, self._entry.entry_id)
        if recovered:
            LOGGER.info("FCM: push-receiver восстановлен")

    @callback
    def _async_open_circuit(self, now: datetime) -> None:
        """Назначить следующую пробу и показать persistent Repairs issue."""
        if self._stopping:
            return
        delay = FCM_RETRY_BACKOFFS[self._backoff_index]
        self._backoff_index = min(
            self._backoff_index + 1, len(FCM_RETRY_BACKOFFS) - 1
        )
        self._next_probe_at = now + delay
        self._recovery_phase = _FcmRecoveryPhase.OPEN
        async_create_fcm_repair_issue(self._hass, self._entry)
        LOGGER.warning(
            "FCM: частые попытки восстановления приостановлены; "
            "следующая проверка через %s",
            delay,
        )

    async def _async_reconnect(self) -> bool:
        """Выполнить один защищённый disconnect/connect цикл."""
        if not await self._async_disconnect():
            return False
        if self._stopping:
            return False
        await self._async_connect()
        if not self._stopping:
            self._recovery_phase = _FcmRecoveryPhase.VERIFYING
        return True

    async def _async_watchdog(self, _now: datetime | None = None) -> None:
        """Наблюдать receiver и выполнять bounded automatic recovery.

        Один тик = один переход. Живой клиент всегда возвращает в HEALTHY;
        мёртвый идёт HEALTHY → SUSPECT → VERIFYING → OPEN, где OPEN пробует
        восстановиться по backoff-расписанию.
        """
        if self._stopping or self._transition_lock.locked():
            return
        async with self._transition_lock:
            if self._stopping:
                return
            client = self._client
            if client is not None and client.is_started():
                self._async_mark_healthy()
                return

            now = _now or dt_util.utcnow()

            match self._recovery_phase:
                case _FcmRecoveryPhase.HEALTHY:
                    # Первая неактивность — только наблюдаем: даём библиотеке
                    # тик на самостоятельное переподключение.
                    self._recovery_phase = _FcmRecoveryPhase.SUSPECT

                case _FcmRecoveryPhase.SUSPECT:
                    LOGGER.warning(
                        "FCM: push-receiver неактивен — выполняю одну попытку восстановления"
                    )
                    if not await self._async_reconnect():
                        self._async_open_circuit(now)

                case _FcmRecoveryPhase.VERIFYING:
                    # Замена не ожила к следующему тику — размыкаем circuit.
                    await self._async_disconnect()
                    self._async_open_circuit(now)

                case _FcmRecoveryPhase.OPEN:
                    if self._next_probe_at is not None and now < self._next_probe_at:
                        return
                    LOGGER.info("FCM: выполняю пробную попытку восстановления")
                    if not await self._async_reconnect():
                        self._async_open_circuit(now)

    async def _async_disconnect(self) -> bool:
        """Остановить текущий MTalk-сокет (watchdog НЕ трогаем)."""
        client = self._client
        if client is None:
            return True
        try:
            await client.stop()
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "FCM: не удалось остановить listener (%s)",
                type(err).__name__,
            )
            return False
        if self._client is client:
            self._client = None
        return True

    async def async_stop(self) -> bool:
        """Полная остановка на unload entry: отменить watchdog + закрыть сокет."""
        self._stopping = True
        if self._watchdog_unsub is not None:
            self._watchdog_unsub()
            self._watchdog_unsub = None
        async with self._transition_lock:
            stopped = await self._async_disconnect()
        if stopped and self._entry.disabled_by is not None:
            async_delete_fcm_repair_issue(self._hass, self._entry.entry_id)
        return stopped

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
        if self._stopping:
            return
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
