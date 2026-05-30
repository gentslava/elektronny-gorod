"""Constants used by Elektronny Gorod integration."""

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
CONF_GO2RTC_REFRESH_INTERVAL = "go2rtc_refresh_interval"
CONF_GO2RTC_PUBLISH_HIDDEN = "go2rtc_publish_hidden"

DEFAULT_GO2RTC_BASE_URL = "http://127.0.0.1:1984"
DEFAULT_GO2RTC_RTSP_HOST = "127.0.0.1"
DEFAULT_GO2RTC_REFRESH_INTERVAL = 20
DEFAULT_GO2RTC_PUBLISH_HIDDEN = True
GO2RTC_RTSP_PORT = 8554

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

APP_VERSION: Final = {
    "name": "9.7.0",
    "code": "90700000"
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
