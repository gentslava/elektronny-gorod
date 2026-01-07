"""The Elektronny Gorod API."""
import json
from .http import HTTP
from .user_agent import UserAgent

class ElektronnyGorodAPI:
    def __init__(
        self,
        user_agent: UserAgent,
        access_token: str | None = None,
        refresh_token: str | None = None,
        operator: str | None = None,
    ) -> None:
        self.http: HTTP = HTTP(
            user_agent,
            access_token,
            refresh_token,
            operator,
        )
        self._phone: str | None = None

    async def query_contracts(self, phone: str) -> dict:
        """Query the list of contracts for the given phone number."""
        self._phone = phone
        api_url = f"/auth/v2/login/{self._phone}"

        try:
            response = await self.http.get(api_url)
            if response.status == 300:
                contracts = await response.json()
                return {
                    "password": False,
                    "contracts": contracts,
                }
            if response.status == 200:
                return {
                    "password": True,
                    "contracts": [],
                }
            if response.status == 204:
                raise ValueError("unregistered")
        except Exception as e:
            response = e.args[0]
            if (response.status == 400):
                raise ValueError("invalid_login")
        raise ValueError("unknown_status")

    async def verify_password(self, timestamp: str, hash1: str, hash2: str) -> dict:
        """Password auth."""
        api_url = f"/auth/v2/auth/{self._phone}/password"

        data = json.dumps(
            {
                "login": self._phone,
                "timestamp": timestamp,
                "hash1": hash1,
                "hash2": hash2,
            }
        )
        try:
            response = await self.http.post(api_url, data)
            return await response.json()
        except Exception as e:
            response = e.args[0]
            if (response.status == 400):
                raise ValueError("invalid_password")
            raise ValueError("unknown_status")

    async def request_sms_code(self, contract: dict) -> None:
        """Request SMS code for the selected contract."""
        api_url = f"/auth/v2/confirmation/{self._phone}"

        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "address": contract["address"],
                "operatorId": contract["operatorId"],
                "subscriberId": str(contract["subscriberId"]),
                "placeId": contract["placeId"],
            }
        )
        try:
            return await self.http.post(api_url, data)
        except Exception as e:
            response = e.args[0]
            if (response.status == 429):
                raise ValueError("limit_exceeded")
            raise ValueError("unknown_status")

    async def verify_sms_code(self, contract: dict, code: str) -> dict:
        """Verify the SMS code."""
        api_url = f"/auth/v3/auth/{self._phone}/confirmation"

        data = json.dumps(
            {
                "accountId": contract["accountId"],
                "confirm1": code,
                "confirm2": code,
                "login": self._phone,
                "operatorId": contract["operatorId"],
                "subscriberId": str(contract["subscriberId"]),
            }
        )
        try:
            response = await self.http.post(api_url, data)
            return await response.json()
        except Exception as e:
            response = e.args[0]
            if (response.status == 406):
                raise ValueError("invalid_format")
            raise ValueError("unknown_status")

    async def query_profile(self) -> dict:
        """Query the profile data for subscriber."""
        api_url = f"/rest/v1/subscribers/profiles"

        try:
            response = await self.http.get(api_url)
            profile = await response.json()
            return profile["data"] if profile else {}
        except Exception as e:
            response = e.args[0]
            if (response.status == 401):
                raise ValueError("unauthorized")
            raise ValueError("unknown_status")

    async def query_balance(self, place_id) -> dict:
        """Query the profile data for subscriber."""
        api_url = f"/api/mh-payment/mobile/v1/finance?placeId={place_id}"

        response = await self.http.get(api_url)
        finance = await response.json()
        return finance["data"] if finance else {}

    async def query_places(self, place_id="") -> list:
        """Query the list of places for subscriber."""
        api_url = f"/rest/v3/subscriber-places{"?placeId=" + place_id if place_id else ""}"

        response = await self.http.get(api_url)
        places = await response.json()
        return places["data"] if places else []

    async def query_access_controls(self, place_id) -> list:
        """Query the list of access controls for subscriber."""
        api_url = f"/rest/v1/places/{place_id}/accesscontrols"

        response = await self.http.get(api_url)
        access_controls = await response.json()
        return access_controls["data"] if access_controls else []

    async def query_cameras(self) -> list:
        """Query the list of cameras for access token."""
        api_url = f"/rest/v1/forpost/cameras"

        response = await self.http.get(api_url)
        cameras = await response.json()
        return cameras["data"] if cameras else []

    async def query_public_cameras(self, place_id) -> list:
        """Query the list of cameras for access token."""
        api_url = f"/rest/v2/places/{place_id}/public/cameras"

        response = await self.http.get(api_url)
        cameras = await response.json()
        return cameras["data"] if cameras else []

    async def query_camera_stream(self, id) -> str | None:
        """Query the stream url of camera for the id."""
        api_url = f"/rest/v1/forpost/cameras/{id}/video?&LightStream=0"

        try:
            response = await self.http.get(api_url)
            camera_stream = await response.json()
            return camera_stream["data"]["URL"] if camera_stream else None
        except Exception as e:
            return None

    async def query_camera_snapshot(self, id, width, height) -> bytes:
        """Query the camera snapshot for the id."""
        api_url = f"/rest/v1/forpost/cameras/{id}/snapshots?width={width}&height={height}"

        return await self.http.get(api_url, binary = True)

    async def open_lock(self, place_id, access_control_id, entrance_id) -> None:
        """Request for open lock."""
        api_url = f"/rest/v1/places/{place_id}/accesscontrols/{access_control_id}/entrances/{entrance_id}/actions"

        data = json.dumps(
            {
                "name": "accessControlOpen"
            }
        )
        await self.http.post(api_url, data)
