"""The Elektronny Gorod API."""
import json
from .http import HTTP

class ElektronnyGorodAPI:
    def __init__(
        self,
        user_agent: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        headers: dict = {},
    ) -> None:
        self.http: HTTP = HTTP(
            user_agent,
            access_token,
            refresh_token,
            headers,
        )
        self.phone: str | None = None

    async def query_contracts(self, phone: str):
        """Query the list of contracts for the given phone number."""
        self.phone = phone
        api_url = f"/auth/v2/login/{self.phone}"

        contracts = await self.http.get(api_url)
        return contracts if contracts else []

    async def request_sms_code(self, contract: dict):
        """Request SMS code for the selected contract."""
        api_url = f"/auth/v2/confirmation/{self.phone}"
        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "address": contract["address"],
                "operatorId": contract["operatorId"],
                "subscriberId": str(contract["subscriberId"]),
                "placeId": contract["placeId"],
            }
        )
        return await self.http.post(api_url, data)

    async def verify_sms_code(self, contract: dict, code: str) -> dict:
        """Verify the SMS code."""
        api_url = f"/auth/v3/auth/{self.phone}/confirmation"
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
        return await self.http.post(api_url, data)

    async def query_profile(self) -> dict:
        """Query the profile data for subscriber."""
        api_url = f"/rest/v1/subscribers/profiles"

        profile = await self.http.get(api_url)
        return profile["data"] if profile else {}

    async def query_places(self, place_id="") -> list:
        """Query the list of places for subscriber."""
        api_url = f"/rest/v3/subscriber-places{"?placeId=" + place_id if place_id else ""}"

        places = await self.http.get(api_url)
        return places["data"] if places else []

    async def query_access_controls(self, place_id) -> list:
        """Query the list of access controls for subscriber."""
        api_url = f"/rest/v1/places/{place_id}/accesscontrols"

        places = await self.http.get(api_url)
        return places["data"] if places else []

    async def query_cameras(self) -> list:
        """Query the list of cameras for access token."""
        api_url = f"/rest/v1/forpost/cameras"

        cameras = await self.http.get(api_url)
        return cameras["data"] if cameras else []

    async def query_public_cameras(self, place_id) -> list:
        """Query the list of cameras for access token."""
        api_url = f"/rest/v2/places/{place_id}/public/cameras"

        cameras = await self.http.get(api_url)
        return cameras["data"] if cameras else []

    async def query_camera_stream(self, id) -> str | None:
        """Query the stream url of camera for the id."""
        api_url = f"/rest/v1/forpost/cameras/{id}/video?&LightStream=0"

        camera_stream = await self.http.get(api_url)
        return camera_stream["data"]["URL"] if camera_stream else None

    async def query_camera_snapshot(self, id, width, height) -> bytes:
        """Query the camera snapshot for the id."""
        api_url = f"/rest/v1/forpost/cameras/{id}/snapshots?width={width}&height={height}"
        return await self.http.get(api_url, binary = True)

    async def open_lock(self, place_id, access_control_id, entrance_id) -> list:
        """Query the list of places for subscriber."""
        api_url = f"/rest/v1/places/{place_id}/accesscontrols/{access_control_id}/entrances/{entrance_id}/actions"
        data = json.dumps(
            {
                "name": "accessControlOpen"
            }
        )
        return await self.http.post(api_url, data)
