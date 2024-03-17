"""Constants used by Elektronny Gorod integration."""
import logging
from typing import Final

DOMAIN = "elektronny_gorod"
BASE_API_URL: Final = "api-mh.ertelecom.ru"
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

APP_VERSION: Final = "6.16.5 (build 1)"
iOS_11: Final = ["iOS 11.0", "iOS 11.0.1", "iOS 11.0.2", "iOS 11.0.3", "iOS 11.1", "iOS 11.1.1", "iOS 11.1.2", "iOS 11.2", "iOS 11.2.1", "iOS 11.2.2", "iOS 11.2.5", "iOS 11.2.6", "iOS 11.3", "iOS 11.3.1", "iOS 11.4", "iOS 11.4.1"]
iOS_12: Final = ["iOS 12.0", "iOS 12.0.1", "iOS 12.1", "iOS 12.1.1", "iOS 12.1.2", "iOS 12.1.3", "iOS 12.1.4", "iOS 12.2", "iOS 12.3", "iOS 12.3.1", "iOS 12.3.2", "iOS 12.4", "iOS 12.4.1"]
iOS_13: Final = ["iOS 13.0", "iOS 13.1", "iOS 13.1.1", "iOS 13.1.2", "iOS 13.1.3", "iOS 13.2", "iOS 13.2.2", "iOS 13.2.3", "iOS 13.3", "iOS 13.3.1", "iOS 13.4", "iOS 13.4.1", "iOS 13.5", "iOS 13.5.1", "iOS 13.6", "iOS 13.6.1", "iOS 13.6.1", "iOS 13.7"]
iOS_14: Final = ["iOS 14.0", "iOS 14.0.1", "iOS 14.1", "iOS 14.2", "iOS 14.2.1", "iOS 14.3", "iOS 14.4", "iOS 14.4.1", "iOS 14.4.2", "iOS 14.5", "iOS 14.5.1", "iOS 14.6", "iOS 14.7", "iOS 14.7.1", "iOS 14.8", "iOS 14.8.1"]
iOS_15: Final = ["iOS 15.0", "iOS 15.0.1", "15.0.2", "iOS 15.1", "iOS 15.2", "iOS 15.2.1", "iOS 15.3", "iOS 15.3.1", "iOS 15.4", "iOS 15.4.1", "iOS 15.5", "iOS 15.6", "iOS 15.6.1", "iOS 15.7", "iOS 15.7.1", "iOS 15.7.2", "iOS 15.7.3", "iOS 15.7.4", "iOS 15.7.5", "iOS 15.7.6", "iOS 15.7.7", "iOS 15.7.8", "iOS 15.7.9", "iOS 15.8"]
iOS_16: Final = ["iOS 16.0", "iOS 16.0.1", "iOS 16.0.2", "iOS 16.0.3", "iOS 16.1", "iOS 16.1.1", "iOS 16.2", "iOS 16.3", "iOS 16.3.1", "iOS 16.4", "iOS 16.4.1", "iOS 16.5", "iOS 16.6", "iOS 16.6.1", "iOS 16.7", "iOS 16.7.1", "iOS 16.7.2", "iOS 16.7.3", "iOS 16.7.4", "iOS 16.7.5", "iOS 16.7.6"]
iOS_17: Final = ["iOS 17.0", "iOS 17.0.1", "iOS 17.0.2", "iOS 17.0.3", "iOS 17.1", "iOS 17.1.1", "iOS 17.1.2", "iOS 17.2", "iOS 17.2.1", "iOS 17.3", "iOS 17.3.1", "iOS 17.4"]
iPHONE_iOS_CODES: Final = [
	{
		"name": "iPhone 8/X",
		"code": ["iPhone10,1", "iPhone10,2", "iPhone10,3", "iPhone10,4", "iPhone10,5", "iPhone10,6"],
		"os": [*iOS_11, *iOS_12, *iOS_13, *iOS_14, *iOS_15, *iOS_16]
	},
	{
		"name": "iPhone XS/XR",
		"code": ["iPhone11,2", "iPhone11,4", "iPhone11,6", "iPhone11,8"],
		"os": [*iOS_12, *iOS_13, *iOS_14, *iOS_15, *iOS_16, *iOS_17]
	},
	{
		"name": "iPhone 11/SE 2",
		"code": ["iPhone12,1", "iPhone12,3", "iPhone12,5", "iPhone12,8"],
		"os": [*iOS_13, *iOS_14, *iOS_15, *iOS_16, *iOS_17]
	},
	{
		"name": "iPhone 12",
		"code": ["iPhone13,1", "iPhone13,2", "iPhone13,3", "iPhone13,4"],
		"os": [*iOS_14, *iOS_15, *iOS_16, *iOS_17]
	},
	{
		"name": "iPhone 13/SE 3",
		"code": ["iPhone14,2", "iPhone14,3", "iPhone14,4", "iPhone14,5", "iPhone14,6"],
		"os": [*iOS_15, *iOS_16, *iOS_17]
	},
	{
		"name": "iPhone 14",
		"code": ["iPhone14,7", "iPhone14,8", "iPhone15,2", "iPhone15,3"],
		"os": [*iOS_16, *iOS_17]
	},
	{
		"name": "iPhone 15",
		"code": ["iPhone15,4", "iPhone15,5", "iPhone16,1", "iPhone16,2"],
		"os": [*iOS_17]
	},
]
