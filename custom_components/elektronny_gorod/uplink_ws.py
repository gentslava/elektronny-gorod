"""WS-команда uplink-микрофона: браузер → HA-WebSocket (binary) → SIP-uplink.

Phase C, ADR-0013 (механизм #1 — HA WS-binary audio). Lovelace-карта снимает
микрофон (`getUserMedia` → Int16 PCM) и шлёт кадры по тому же авторизованному
HA-WebSocket, что и весь UI (без go2rtc/TURN, 4G-friendly). Команда
`elektronny_gorod/intercom_uplink`:

1. Находит контроллер с активным вызовом (DoorbellCallController).
2. Регистрирует binary-handler (`connection.async_register_binary_handler`):
   каждый бинарный кадр → `controller.feed_uplink(pcm, sample_rate)` →
   `UplinkSink` → `SipManager.uplink_provider` → RTP в домофон.
3. `unsub` handler-а кладёт в `connection.subscriptions[msg_id]` — HA снимает
   его автоматически при unsubscribe/disconnect (закрытие вкладки = конец uplink).

Паттерн зеркалит голосовой ассистент HA (`audio-recorder.ts` + bin-handler).
Сетевой слой WS — за этой границей (доказывается живым вызовом, не юнит-тестами).
"""
from __future__ import annotations

import os
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, LOGGER, SIP_DATA as _SIP_DATA

# Дефолтный sample_rate микрофона браузера (AudioContext по умолчанию 48кГц).
# UplinkSink ресемплит к 8кГц G.711 — точное значение важно для качества.
_DEFAULT_SAMPLE_RATE = 48000
# Границы sample_rate: явный отказ на подписке вместо тихого дропа каждого кадра
# в audioop.ratecv (0/отрицательный бросил бы). 8к..192к — разумный аудио-диапазон.
_MIN_SAMPLE_RATE = 8000
_MAX_SAMPLE_RATE = 192000


def _find_active_controller(hass: HomeAssistant) -> Any | None:
    """Контроллер с активным вызовом (отвеченный разговор), или None.

    Приоритет — `active_call_media()` (есть мост + камера). Fallback —
    `_manager.in_call` (мост не поднялся, degrade, но микрофон всё равно важен).
    Multi-entry: перебираем все контроллеры, берём первый с активным вызовом.
    """
    for controller in list(hass.data.get(_SIP_DATA, {}).values()):
        if controller.active_call_media() is not None:
            return controller
        manager = getattr(controller, "_manager", None)
        if manager is not None and getattr(manager, "in_call", False):
            return controller
    return None


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "elektronny_gorod/intercom_uplink",
        vol.Optional("sample_rate", default=_DEFAULT_SAMPLE_RATE): vol.All(
            int, vol.Range(min=_MIN_SAMPLE_RATE, max=_MAX_SAMPLE_RATE)
        ),
    }
)
def ws_intercom_uplink(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Подписка uplink-микрофона: регистрирует binary-handler на активный вызов."""
    controller = _find_active_controller(hass)
    if controller is None:
        connection.send_error(
            msg["id"], "no_active_call", "Нет активного вызова домофона для uplink"
        )
        return

    sample_rate = msg["sample_rate"]

    @callback
    def _on_binary(
        _hass: HomeAssistant,
        _connection: websocket_api.ActiveConnection,
        data: bytes,
    ) -> None:
        """Бинарный кадр микрофона → feed_uplink. Толерантен к битым данным:
        UplinkSink.feed не должен бросать, но оборачиваем на случай регрессии.
        HA-core при исключении в bin-handler снимает ЭТОТ handler целиком
        (`binary_handlers[index]=None`) → uplink молча умрёт до переподписки;
        глушим, чтобы один битый кадр не убил всю сессию микрофона."""
        try:
            controller.feed_uplink(data, sample_rate)
        except Exception:  # noqa: BLE001 — uplink degrade не должен снимать handler
            LOGGER.debug("intercom_uplink: кадр микрофона отброшен (feed упал)")

    handler_id, unsub = connection.async_register_binary_handler(_on_binary)
    # Авто-cleanup: HA снимает unsub при unsubscribe команды / disconnect клиента.
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"handler_id": handler_id})
    LOGGER.info("intercom_uplink: подписка микрофона (handler_id=%s, %dГц)",
                handler_id, sample_rate)


# Флаг-ключ в hass.data: WS-команда регистрируется один раз на интеграцию
# (как сервисы answer/hangup), независимо от числа entry.
_WS_REGISTERED = f"{DOMAIN}_uplink_ws_registered"


@callback
def async_register_uplink_ws_command(hass: HomeAssistant) -> None:
    """Зарегистрировать WS-команду intercom_uplink (один раз на интеграцию)."""
    if hass.data.get(_WS_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_intercom_uplink)
    hass.data[_WS_REGISTERED] = True


# Lovelace-карты (микрофон, экран вызова, история) раздаются статикой из всей www/;
# пользователь добавляет URL как ресурс (Settings → Dashboards → Resources →
# JavaScript Module). Регистрируем директорию, а не отдельный файл, — чтобы
# отдавались все карты (mic-card + call-card + будущие) без правок кода.
STATIC_BASE = "/elektronny_gorod_static"
_WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
CARD_URL = f"{STATIC_BASE}/eg-intercom-mic-card.js"  # mic-card (обратная совместимость)
CALL_CARD_URL = f"{STATIC_BASE}/eg-intercom-call-card.js"  # call + history bundle
_CARD_REGISTERED = f"{DOMAIN}_uplink_card_registered"


async def async_register_uplink_card(hass: HomeAssistant) -> None:
    """Раздать www/ статикой: mic, call-screen и history cards."""
    if hass.data.get(_CARD_REGISTERED):
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_BASE, _WWW_DIR, False)]
    )
    hass.data[_CARD_REGISTERED] = True
