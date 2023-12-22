"""Constants used by Elektronny Gorod integration."""
import logging
from typing import Final

DOMAIN = "elektronny_gorod"
BASE_API_URL: Final = "https://api-mh.ertelecom.ru"
LOGGER = logging.getLogger(__name__)

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_PHONE: Final = "phone"
CONF_CONTRACT: Final = "contract"
CONF_SMS: Final = "sms"
CONF_OPERATOR_ID: Final = "operator_id"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_SUBSCRIBER_ID: Final = "subscriber_id"

CONF_WIDTH: Final = 300
CONF_HEIGHT: Final = 300
