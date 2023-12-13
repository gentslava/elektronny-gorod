import logging
from typing import Final
"""Constants for the Elektronny Gorod integration."""

DOMAIN = "elektronny_gorod"
BASE_API_URL: Final = "https://api-mh.ertelecom.ru"
LOGGER = logging.getLogger(__name__)

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_PHONE: Final = "phone"
CONF_CONTRACT: Final = "contract"
CONF_SMS: Final = "sms"
CONF_OPERATOR_ID: Final = "operatorId"
