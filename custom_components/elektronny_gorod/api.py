from aiohttp import ClientSession, ClientError
import json
from .helpers import is_json
from .const import (
    LOGGER,
    BASE_API_URL,
)
from .user_agent import UserAgent

class ElektronnyGorodAPI:
    def __init__(
        self,
        user_agent: UserAgent,
        access_token: str | None = None,
        refresh_token: str | None = None,
        headers: dict = {},
    ) -> None:
        self.base_url: str = f"https://{BASE_API_URL}"
        self.user_agent: UserAgent = user_agent
        self.headers: dict = {
            **{
                "Host": BASE_API_URL,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
            },
            **headers
        }
        self.phone: str | None = None
        self.access_token: str | None = access_token
        self.refresh_token: str | None = refresh_token

    async def query_contracts(self, phone: str):
        """Query the list of contracts for the given phone number."""
        self.phone = phone
        api_url = f"{self.base_url}/auth/v2/login/{self.phone}"

        contracts = await self.request(api_url)
        return contracts if contracts else []

    async def request_sms_code(self, contract: dict):
        """Request SMS code for the selected contract."""
        api_url = f"{self.base_url}/auth/v2/confirmation/{self.phone}"
        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "address": contract["address"],
                "operatorId": contract["operatorId"],
                "subscriberId": str(contract["subscriberId"]),
                "placeId": contract["placeId"],
            }
        )
        return await self.request(api_url, data, method="POST")

    async def verify_sms_code(self, contract: dict, code: str) -> dict:
        """Verify the SMS code."""
        api_url = f"{self.base_url}/auth/v3/auth/{self.phone}/confirmation"
        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "confirm1": code,
                "confirm2": code,
                "login": self.phone,
                "operatorId": contract["operatorId"],
                "subscriberId": str(contract["subscriberId"]),
            }
        )
        return await self.request(api_url, data, method="POST")

    async def update_access_token(self, access_token) -> None:
        self.access_token = access_token

    async def query_profile(self) -> dict:
        """Query the profile data for subscriber."""
        api_url = f"{self.base_url}/rest/v1/subscribers/profiles"

        profile = await self.request(api_url)
        return profile["data"] if profile else {}

    async def query_places(self, place_id) -> list:
        """Query the list of places for subscriber."""
        api_url = f"{self.base_url}/rest/v3/subscriber-places{"?placeId=" + place_id if place_id else ""}"

        places = await self.request(api_url)
        return places["data"] if places else []

    async def query_cameras(self) -> list:
        """Query the list of cameras for access token."""
        api_url = f"{self.base_url}/rest/v1/forpost/cameras"

        cameras = await self.request(api_url)
        return cameras["data"] if cameras else []

    async def query_camera_stream(self, id) -> str | None:
        """Query the stream url of camera for the id."""
        api_url = f"{self.base_url}/rest/v1/forpost/cameras/{id}/video?&LightStream=0"

        camera_stream = await self.request(api_url)
        return camera_stream["data"]["URL"] if camera_stream else None

    async def query_camera_snapshot(self, id, width, height) -> bytes:
        """Query the camera snapshot for the id."""
        api_url = f"{self.base_url}/rest/v1/forpost/cameras/{id}/snapshots?width={width}&height={height}"
        return await self.request(api_url, binary = True)

    async def open_lock(self, place_id, access_control_id, entrance_id) -> list:
        """Query the list of places for subscriber."""
        api_url = f"{self.base_url}/rest/v1/places/{place_id}/accesscontrols/{access_control_id}/entrances/{entrance_id}/actions"
        data = json.dumps(
            {
                "name": "accessControlOpen"
            }
        )
        return await self.request(api_url, data, method = "POST")

    async def request(
        self,
        url: str,
        data: object | None = None,
        method: str = "GET",
        binary: bool = False
    ):
        """Make a HTTP request."""
        if self.access_token is not None: self.headers["Authorization"] = f"Bearer {self.access_token}"
        self.headers["User-Agent"] = str(self.user_agent)
        if method == "POST":
            self.headers["Content-Type"] = "application/json; charset=UTF-8"

        async with ClientSession() as session:
            LOGGER.info("Sending API request to %s with headers=%s and data=%s", url, self.headers, data)
            if method == "GET":
                response = await session.get(url, headers = self.headers)
            elif method == "POST":
                response = await session.post(url, data = data, headers = self.headers)

            if binary: return await response.read()

            text = await response.text()
            if response.status in (200, 300):
                LOGGER.info("Response is %s - %s", response.status, text)
                return await response.json() if is_json(text) else text
            else:
                LOGGER.error("Could not get data from API: %s - %s", response, text)
                raise ClientError(response.status, text)
