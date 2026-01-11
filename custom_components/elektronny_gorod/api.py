"""The Elektronny Gorod API."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import ClientResponse

from .http import HTTP
from .user_agent import UserAgent


class ElektronnyGorodAPI:
    """Elektronny Gorod HTTP API wrapper."""

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

    def _ensure_phone(self) -> str:
        """Return phone if it is known, otherwise raise a setup error."""
        if not self._phone:
            raise ValueError("missing_phone")
        return self._phone

    async def query_contracts(self, phone: str) -> dict[str, Any]:
        """Query the list of contracts for the given phone number."""
        self._phone = phone
        api_url = f"/auth/v2/login/{phone}"

        try:
            response = await self.http.get(api_url)

            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            if response.status == 300:
                contracts = await response.json()
                return {"password": False, "contracts": contracts}

            if response.status == 200:
                return {"password": True, "contracts": []}

            if response.status == 204:
                raise ValueError("unregistered")

            raise ValueError("unknown_status")

        except Exception as e:
            if isinstance(e.args[0], ClientResponse) and e.args[0].status == 400:
                raise ValueError("invalid_login")
            if isinstance(e, ValueError):
                raise
            raise ValueError("unknown_status")

    async def verify_password(self, timestamp: str, hash1: str, hash2: str) -> dict[str, Any]:
        """Authenticate using password."""
        phone = self._ensure_phone()
        api_url = f"/auth/v2/auth/{phone}/password"

        payload = {
            "login": phone,
            "timestamp": timestamp,
            "hash1": hash1,
            "hash2": hash2,
        }

        try:
            response = await self.http.post(api_url, json.dumps(payload))

            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            return await response.json()

        except Exception as e:
            if isinstance(e.args[0], ClientResponse) and e.args[0].status == 400:
                raise ValueError("invalid_password")
            raise ValueError("unknown_status")

    async def request_sms_code(self, contract: dict[str, Any]) -> None:
        """Request SMS code for the selected contract."""
        phone = self._ensure_phone()
        api_url = f"/auth/v2/confirmation/{phone}"

        payload = {
            "accountId": contract["accountId"],
            "address": contract["address"],
            "operatorId": contract["operatorId"],
            "subscriberId": str(contract["subscriberId"]),
            "placeId": contract["placeId"],
        }

        try:
            response = await self.http.post(api_url, json.dumps(payload))

            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            return

        except Exception as e:
            if isinstance(e.args[0], ClientResponse) and e.args[0].status == 429:
                raise ValueError("limit_exceeded")
            raise ValueError("unknown_status")

    async def verify_sms_code(self, contract: dict[str, Any], code: str) -> dict[str, Any]:
        """Verify the SMS code."""
        phone = self._ensure_phone()
        api_url = f"/auth/v3/auth/{phone}/confirmation"

        payload = {
            "accountId": contract["accountId"],
            "confirm1": code,
            "confirm2": code,
            "login": phone,
            "operatorId": contract["operatorId"],
            "subscriberId": str(contract["subscriberId"]),
        }

        try:
            response = await self.http.post(api_url, json.dumps(payload))

            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            return await response.json()

        except Exception as e:
            if isinstance(e.args[0], ClientResponse) and e.args[0].status == 406:
                raise ValueError("invalid_format")
            raise ValueError("unknown_status")

    async def query_profile(self) -> dict[str, Any]:
        """Query the subscriber profile."""
        api_url = "/rest/v1/subscribers/profiles"

        try:
            response = await self.http.get(api_url)

            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            profile = await response.json()
            return profile.get("data") if profile else {}

        except Exception as e:
            if isinstance(e.args[0], ClientResponse) and e.args[0].status == 401:
                raise ValueError("unauthorized")
            raise ValueError("unknown_status")

    async def query_balance(self, place_id: str) -> dict[str, Any]:
        """Query the balance/finance info for a place."""
        api_url = f"/api/mh-payment/mobile/v1/finance?placeId={place_id}"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        finance = await response.json()
        return finance.get("data") if finance else {}

    async def query_places(self, place_id: str = "") -> list[dict[str, Any]]:
        """Query the list of places for the subscriber."""
        suffix = f"?placeId={place_id}" if place_id else ""
        api_url = f"/rest/v3/subscriber-places{suffix}"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        places = await response.json()
        data = places.get("data") if places else []
        return data

    async def query_access_controls(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of access controls for a place."""
        api_url = f"/rest/v1/places/{place_id}/accesscontrols"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        access_controls = await response.json()
        data = access_controls.get("data") if access_controls else []
        return data

    async def query_cameras(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of cameras for the current access token."""
        api_url = f"/rest/v1/places/{place_id}/cameras"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        cameras = await response.json()
        data = cameras.get("data") if cameras else []
        return data

    async def query_public_cameras(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of public cameras for a place."""
        api_url = f"/rest/v2/places/{place_id}/public/cameras"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        cameras = await response.json()
        data = cameras.get("data") if cameras else []
        return data

    async def query_sections(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of cameras for the current access token."""
        api_url = f"/rest/v1/places/{place_id}/screen-sections"

        response = await self.http.get(api_url)
        if not isinstance(response, ClientResponse):
            raise TypeError(f"Unexpected response type: {type(response)!r}")

        cameras = await response.json()
        data = cameras.get("sections") if cameras else []
        return data

    async def query_camera_stream(self, camera_id: str) -> str | None:
        """Query the stream URL for the given camera."""
        api_url = f"/rest/v1/forpost/cameras/{camera_id}/video?&LightStream=0"

        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            camera_stream = await response.json()
            return camera_stream["data"]["URL"] if camera_stream else None

        except Exception:
            return None

    async def query_camera_snapshot(
        self,
        camera_id: str,
        width: int | None,
        height: int | None,
    ) -> bytes:
        """Query the camera snapshot bytes for the given camera."""
        api_url = f"/rest/v1/forpost/cameras/{camera_id}/snapshots?width={width}&height={height}"

        result = await self.http.get(api_url, binary=True)

        if isinstance(result, (bytes, bytearray)):
            return bytes(result)

        if isinstance(result, ClientResponse):
            return await result.read()

        raise TypeError(f"Unexpected response type: {type(result)!r}")

    async def open_lock(self, place_id: str, access_control_id: str, entrance_id: str | None) -> None:
        """Send a request to open a lock."""
        if entrance_id is None:
            api_url = f"/rest/v1/places/{place_id}/accesscontrols/{access_control_id}/actions"
        else:
            api_url = f"/rest/v1/places/{place_id}/accesscontrols/{access_control_id}/entrances/{entrance_id}/actions"

        payload = {"name": "accessControlOpen"}
        await self.http.post(api_url, json.dumps(payload))
