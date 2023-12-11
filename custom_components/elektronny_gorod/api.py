from homeassistant.core import HomeAssistant
import logging
import aiohttp
import json
from .helpers import is_json

_LOGGER = logging.getLogger(__name__)


class ElektronnyGorodAPI:
    def __init__(self, base_url: str, hass: HomeAssistant):
        self.base_url: str = base_url
        self.hass: HomeAssistant = hass
        self.headers: object = {
            "User-Agent": "Android-7.1.1-1.0.0-ONEPLUS | ntk | 6.2.0 (6020005) |  | 0 | bee3aeb0602e82fb"
        }
        self.phone: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    async def query_contracts(self, phone: str):
        """Query the list of contracts for the given phone number."""
        self.phone = phone
        api_url = f"{self.base_url}/auth/v2/login/{self.phone}"

        contracts = await self.request(api_url)
        return contracts if contracts else []

    async def request_sms_code(self, contract: object):
        """Request SMS code for the selected contract."""
        api_url = f"{self.base_url}/auth/v2/confirmation/{self.phone}"
        self.headers["Content-Type"] = "application/json; charset=UTF-8"
        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "address": contract["address"],
                "operatorId": contract["operatorId"],
                "subscriberId": contract["subscriberId"],
            }
        )

        return await self.request(api_url, data, method="POST")

    async def verify_sms_code(self, code):
        """Verify the SMS code."""
        api_url = f"{self.base_url}/verify_sms_code"
        data = {"code": code}

        return await self.request(api_url, data, method="POST")

    async def request(
        self,
        url: str,
        data: object | None=None,
        method: str="GET"
    ):
        """Make a HTTP request."""
        _LOGGER.info("Sending API request to %s with data=%s", url, data)
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                response = await session.get(url, headers=self.headers)
            elif method == "POST":
                response = await session.post(url, data=data, headers=self.headers)

            text = await response.text()
            if response.status in (200, 300):
                _LOGGER.info("Response is %s - %s", response.status, text)
                return await response.json() if is_json(text) else text
            else:
                _LOGGER.error("Could not get data from API: %s", response)
                raise aiohttp.ClientError(response.status, text)
