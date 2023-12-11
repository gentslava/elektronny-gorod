from homeassistant.core import HomeAssistant
import logging
import aiohttp

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

        return await self.request(api_url)
        response = await requests.get(api_url, headers=self.headers)

        _LOGGER.info("Elekrony gorod: Response is %s", response)
        if response.status_code == 200:
            return response.json()
        else:
            return []

    async def request_sms_code(self, contract):
        """Request SMS code for the selected contract."""
        api_url = f"{self.base_url}/request_sms_code"
        self.headers['Content-Type'] = "application/json; charset=UTF-8"
        data = {"contract_id": contract}

        return await self.request(api_url, data, method="POST")
        response = await requests.post(api_url, data)

        return response.status_code == 200

    async def verify_sms_code(self, code):
        """Verify the SMS code."""
        api_url = f"{self.base_url}/verify_sms_code"
        data = {"code": code}

        return await self.request(api_url, data, method="POST")
        response = await requests.post(api_url, data)

        return response.status_code == 200

    async def request(
        self,
        url: str,
        data: object | None=None,
        method: str="GET"
    ):
        """Make a HTTP request"""
        _LOGGER.info("Sending API request")
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                response = session.get(url, headers=self.headers)
            elif method == "POST":
                response = session.post(url, data, headers=self.headers)

            if response.status == 200 or response.status == 300:
                _LOGGER.debug(f"{await response.text()}")
                return await response.json()
            else:
                raise aiohttp.ClientError(response.status, await response.text())
