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
CONF_OPERATOR_ID: Final = "operator_id"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_SUBSCRIBER_ID: Final = "subscriber_id"
CONF_USER_AGENT: Final = "user_agent"

CONF_WIDTH: Final = 300
CONF_HEIGHT: Final = 300

APP_VERSION: Final = {
    "name": "8.23.0",
    "code": "82300000"
}

ANDROID_OS_VER: Final = "15"
# ANDROID_DEVICES_CSV: Final = "https://storage.googleapis.com/play_public/supported_devices.csv"
ANDROID_DEVICES: Final = [
    {
        "manufacturer": "Google",
        "model": "Pixel 5a",
    },
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
]
