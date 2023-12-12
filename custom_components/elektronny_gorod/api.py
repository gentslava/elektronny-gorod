from aiohttp import ClientSession, ClientError
import json
from .helpers import is_json
from .const import (
    LOGGER,
    BASE_API_URL,
)


class ElektronnyGorodAPI:
    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        headers: dict = {}
    ):
        self.base_url: str = BASE_API_URL
        self.headers: object = {**{
            "User-Agent": "Android-7.1.1-1.0.0-ONEPLUS | ntk | 6.2.0 (6020005) |  | 0 | bee3aeb0602e82fb"
        }, **headers}
        self.phone: str | None = None
        self.access_token: str | None = access_token
        self.refresh_token: str | None = refresh_token

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

    async def verify_sms_code(self, contract:object, code:str) -> dict:
        """Verify the SMS code."""
        api_url = f"{self.base_url}/auth/v2/auth/{self.phone}/confirmation"
        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "confirm1": code,
                "confirm2": code,
                "login": self.phone,
                "operatorId": contract["operatorId"],
                "subscriberId": contract["subscriberId"],
            }
        )
        return await self.request(api_url, data, method="POST")

    async def query_cameras(self) -> list:
        """Query the list of cameras for access token."""
        api_url = f"{self.base_url}/rest/v1/forpost/cameras"

        cameras = await self.request(api_url)
        return cameras["data"] if cameras else []

    async def query_camera_snapshot(self, id) -> bytes:
        """Query the camera snapshot for the id."""
        api_url = f"{self.base_url}/rest/v1/forpost/cameras/{id}/snapshots"
        return await self.request(api_url, binary=True)

    async def request(
        self,
        url: str,
        data: object | None = None,
        method: str = "GET",
        binary: bool = False
    ):
        """Make a HTTP request."""
        if self.access_token is not None: self.headers["Authorization"] = f"Bearer {self.access_token}"

        async with ClientSession() as session:
            LOGGER.info("Sending API request to %s with headers=%s and data=%s", url, self.headers, data)
            if method == "GET":
                response = await session.get(url, headers=self.headers)
            elif method == "POST":
                response = await session.post(url, data=data, headers=self.headers)

            if binary: return await response.read()

            text = await response.text()
            if response.status in (200, 300):
                LOGGER.info("Response is %s - %s", response.status, text)
                return await response.json() if is_json(text) else text
            else:
                LOGGER.error("Could not get data from API: %s - %s", response, text)
                raise ClientError(response.status, text)
