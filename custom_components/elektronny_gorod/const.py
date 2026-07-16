"""Constants used by Elektronny Gorod integration.

Содержит **только** shared / identity константы (см.
[`.claude/rules/constants-locality.md`](../../.claude/rules/constants-locality.md)):

- DOMAIN / LOGGER / BASE_API_URL — identity интеграции и бэкенда.
- CONF_* — config-flow keys (shared между config_flow / coordinator / etc.).
- DEFAULT_GO2RTC_* + GO2RTC_RTSP_PORT — shared между camera.py и go2rtc.py.
- AREA_* — shared между camera.py и lock.py.
- APP_VERSION / ANDROID_* — shared между user_agent и config_flow.

Domain-specific timing (cooldown, poll interval, refresh budget, timeout)
остаётся **в модуле**, который его использует — см. precedents в
`camera.py`, `coordinator.py`, `go2rtc.py`.
"""

import logging
from typing import Final

DOMAIN = "elektronny_gorod"
BASE_API_URL: Final = "myhome.proptech.ru"
LOGGER = logging.getLogger(__name__)

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_PHONE: Final = "phone"
CONF_PASSWORD: Final = "password"
CONF_CONTRACT: Final = "contract"
CONF_SMS: Final = "sms"

# go2rtc configuration
CONF_USE_GO2RTC = "use_go2rtc"
CONF_GO2RTC_BASE_URL = "go2rtc_base_url"
CONF_GO2RTC_RTSP_HOST = "go2rtc_rtsp_host"
CONF_GO2RTC_USERNAME = "go2rtc_username"
CONF_GO2RTC_PASSWORD = "go2rtc_password"
CONF_GO2RTC_KEEP_WARM: Final = "go2rtc_keep_warm"
CONF_GO2RTC_KEEP_WARM_HIDDEN: Final = "go2rtc_keep_warm_hidden"

DEFAULT_GO2RTC_BASE_URL = "http://127.0.0.1:1984"
DEFAULT_GO2RTC_RTSP_HOST = "127.0.0.1"
DEFAULT_GO2RTC_KEEP_WARM: Final = False
DEFAULT_GO2RTC_KEEP_WARM_HIDDEN: Final = False
GO2RTC_RTSP_PORT = 8554

# Per-config-entry CameraStreamManager registry. Kept separate from
# hass.data[DOMAIN][entry_id], whose public shape remains the coordinator.
STREAM_MANAGER_DATA: Final = f"{DOMAIN}_stream_managers"

CONF_OPERATOR_ID: Final = "operator_id"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_SUBSCRIBER_ID: Final = "subscriber_id"
CONF_USER_AGENT: Final = "user_agent"

DEFAULT_SNAPSHOT_WIDTH: Final = 300
DEFAULT_SNAPSHOT_HEIGHT: Final = 300

# Suggested area names — даём пользователю осмысленную дефолтную группировку.
# suggested_area работает только при создании device; existing devices можно
# переназначить в UI или через API. Имена локализованы для русскоязычного
# оператора «Электронный город».
AREA_INTERCOM: Final = "Домофоны"
AREA_INDOOR_CAM: Final = "Камеры дома"
AREA_PUBLIC_CAM: Final = "Городские камеры"

# Realtime doorbell-call signal: fcm.py (sender) → event.py (entity listener).
# Shared cross-module → в const.py (см. constants-locality.md).
SIGNAL_DOORBELL: Final = f"{DOMAIN}_doorbell"

# Реестр SIP-контроллеров per-entry в hass.data: __init__ (setup/unload) пишет,
# uplink_ws (WS-команда микрофона) читает. Shared cross-module → в const.py.
SIP_DATA: Final = f"{DOMAIN}_sip"

# Окно ответа на вызов, если payload `CallInvalidated` отсутствует/невалиден
# (домофон сам сбрасывает на ~30-й секунде). Shared cross-module: event.py
# (авто-`ended`) + sip/call_controller.py (guard answer) — единый источник
# «времени на ответ», иначе значения разъедутся (constants-locality.md).
DOORBELL_CALL_WINDOW_FALLBACK_SEC: Final = 35.0

# Bus-событие состояния вызова: sip/call_controller.py (sender) → sensor.*_call_state
# (listener). Идёт ПАРАЛЛЕЛЬНО EVENT_SIP_CALL (тот гоняет input_boolean dismiss и не
# трогается). Bus-event, а не dispatcher: консистентно с `_fire_call_state` и работает
# с MagicMock-hass в юнит-тестах контроллера. Shared cross-module → в const.py.
EVENT_CALL_STATE: Final = f"{DOMAIN}_call_state"
CALL_STATE_IDLE: Final = "idle"
CALL_STATE_RINGING: Final = "ringing"
CALL_STATE_CONNECTING: Final = "connecting"
CALL_STATE_ACTIVE: Final = "active"
CALL_STATE_ENDED: Final = "ended"
CALL_STATE_ERROR: Final = "error"

# Persisted FCM-credentials (firebase-messaging) — в entry.data, чтобы FCM-токен
# был стабилен между рестартами (как access_token/refresh_token).
CONF_FCM_CREDENTIALS: Final = "fcm_credentials"

# Firebase/FCM конфиг приложения «Мой Дом / NTK» (project ntk-myhome).
# Публичные идентификаторы из APK (как BASE_API_URL) — НЕ секреты: Firebase
# API key дизайнерски публичен (защита — package+SHA1 restriction). Нужны для
# серверной регистрации устройства в FCM. См. ADR-0011, mirror-app-behavior.
FCM_PROJECT_ID: Final = "ntk-myhome"
FCM_APP_ID: Final = "1:369367231553:android:323a999f9f228a40"
FCM_SENDER_ID: Final = "369367231553"
FCM_API_KEY: Final = "AIzaSyB_26K8ZB7iu7qZBpBf5c4NLgvTC3Yrgpk"
FCM_BUNDLE_ID: Final = "ru.inetra.intercom"

APP_VERSION: Final = {
    "name": "9.9.0",
    "code": "90900020"
}

ANDROID_OS_VER: Final = "16"
# ANDROID_DEVICES_CSV: Final = "https://storage.googleapis.com/play_public/supported_devices.csv"
ANDROID_DEVICES: Final = [
    {
        "manufacturer": "Google",
        "model": "Pixel 6",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 6 Pro",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 6a",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 7",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 7 Pro",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 7a",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 8",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 8 Pro",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 8a",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 9",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 9 Pro",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 9 Pro XL",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 9a",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 10",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 10 Pro",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 10 Pro XL",
    },
]
