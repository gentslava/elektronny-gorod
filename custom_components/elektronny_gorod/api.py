"""The Elektronny Gorod API."""

from __future__ import annotations

import json
import uuid
from typing import Any

from aiohttp import ClientResponse

from homeassistant.core import HomeAssistant

from .http import HTTP
from .user_agent import UserAgent

# Эндпоинты привязки push-токена (зеркало приложения, см. FINDINGS §FCM).
_DEVICE_INSTALLATIONS = (
    "/api/mh-customer-device/mobile/public/v1/customers/device-installations"
)
_SUBSCRIBER_NOTIFICATIONS = "/rest/v1/subscriberNotifications"


def _device_id(installation_id: str) -> str:
    """Стабильный 16-hex deviceId, производный от installationId (UA.uuid)."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"eg-fcm-{installation_id}").hex[:16]


class ElektronnyGorodAPI:
    """Elektronny Gorod HTTP API wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        user_agent: UserAgent,
        access_token: str | None = None,
        refresh_token: str | None = None,
        operator: str | None = None,
    ) -> None:
        self.http: HTTP = HTTP(
            hass,
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

    async def query_old_cameras(self) -> list[dict[str, Any]]:
        """Query the list of cameras for the current access token."""
        api_url = "/rest/v1/forpost/cameras"

        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            cameras = await response.json()
            data = cameras.get("data") if cameras else []
            return data
        except Exception:
            return []

    async def query_cameras(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of cameras for the current access token."""
        api_url = f"/rest/v1/places/{place_id}/cameras"

        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            cameras = await response.json()
            data = cameras.get("data") if cameras else []
            return data
        except Exception:
            return []

    async def query_public_cameras(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of public cameras for a place."""
        api_url = f"/rest/v2/places/{place_id}/public/cameras"

        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            cameras = await response.json()
            data = cameras.get("data") if cameras else []
            return data
        except Exception:
            return []

    async def query_sections(self, place_id: str) -> list[dict[str, Any]]:
        """Query the list of cameras for the current access token."""
        api_url = f"/rest/v1/places/{place_id}/screen-sections"

        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")

            cameras = await response.json()
            data = cameras.get("sections") if cameras else []
            return data
        except Exception:
            return []

    async def query_screens_settings(self, place_id: str) -> dict[str, Any]:
        """Пользовательские настройки видимости из приложения оператора.

        Возвращает dict вида:
            {"screens": [
                {"type": "ACCESS_CONTROLS",
                 "entities": [{"id", "type", "order"}, ...],  # видимые
                 "hidden":   [...]},                          # скрытые юзером
                {"type": "PUBLIC_CAMERAS",
                 "entities": [...],
                 "hidden":   [...]},
            ]}

        `hidden` — НЕ категория («городские» или «лифт»), а user preference
        (юзер нажал «скрыть» в приложении). Интеграция уважает это: entity
        для hidden получает `_attr_entity_registry_enabled_default = False`
        (только для НОВЫХ registry-записей; existing сохраняют выбор юзера
        в HA).

        Если ответ `{}` — пользователь ничего не настраивал, всё видимо.
        """
        api_url = (
            f"/api/mh-customer/mobile/v1/customers/places/{place_id}/settings/screens"
        )
        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")
            data = await response.json()
            return data or {}
        except Exception:
            return {}

    async def query_dnd_settings(self, place_id: str) -> list[dict[str, Any]]:
        """Get Do Not Disturb settings for a place.

        Response shape (см. api-reference §settings/do_not_disturb):
            {"do_not_disturb": [
                {"type": "DO_NOT_DISTURB_ROOT",       "name": ..., "status": bool, "hint": ..., "editable": bool},
                {"type": "INTERCOM_CALLS",            "name": ..., "status": bool, ...},
                {"type": "MANAGEMENT_COMPANY_CALLS",  "name": ..., "status": bool, ...}
            ]}

        Returns plain list (внутренности `do_not_disturb`), либо `[]` на ошибку.
        """
        api_url = (
            f"/api/mh-customer/mobile/v1/customers/places/{place_id}/settings/do_not_disturb"
        )
        try:
            response = await self.http.get(api_url)
            if not isinstance(response, ClientResponse):
                raise TypeError(f"Unexpected response type: {type(response)!r}")
            data = await response.json()
            return (data or {}).get("do_not_disturb") or []
        except Exception:
            return []

    async def post_dnd_settings(
        self,
        place_id: str,
        items: list[dict[str, Any]],
    ) -> bool:
        """Update Do Not Disturb settings for a place.

        Body — массив объектов того же shape что GET-response (без обёртки
        `{do_not_disturb: ...}`), с обновлёнными `status`. Response: пустое
        тело (200).

        Returns True если backend принял (HTTP 2xx), False иначе.
        """
        api_url = (
            f"/api/mh-customer/mobile/v1/customers/places/{place_id}/settings/do_not_disturb"
        )
        try:
            response = await self.http.post(api_url, json.dumps(items))
            return isinstance(response, ClientResponse) and response.ok
        except Exception:
            return False

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

    def _push_body(self, fcm_token: str) -> dict[str, Any]:
        """Тело привязки push-токена — зеркало приложения (FINDINGS §FCM)."""
        ua = self.http.user_agent
        return {
            "appVersionCode": int(ua.app_version["code"]),
            "installationId": ua.uuid,
            "appId": 2,
            "appVersion": ua.app_version["name"],
            "platform": "google",
            "pushToken": fcm_token,
            "isDevelop": False,
            "deviceManufacturer": ua.phone_manufacturer,
            "deviceModelName": ua.phone_model,
            "osVersion": ua.android_ver,
            "deviceId": _device_id(ua.uuid),
            "deviceType": "MOBILE_APPLICATION",
        }

    async def register_push_device(self, fcm_token: str) -> bool:
        """Привязать FCM push-токен у оператора.

        Шлёт тело-зеркало на device-installations + subscriberNotifications.
        `http.post` бросает на не-2xx, поэтому успех = оба без исключения.
        Возвращает True/False. `pushToken` в логи не пишется (http.py логирует
        только размер тела, см. no-secret-logs).
        """
        body = json.dumps(self._push_body(fcm_token))
        try:
            for endpoint in (_DEVICE_INSTALLATIONS, _SUBSCRIBER_NOTIFICATIONS):
                await self.http.post(endpoint, body)
            return True
        except Exception:
            return False

    async def unregister_push_device(self) -> bool:
        """Отписать устройство от push (DELETE subscriberNotifications)."""
        try:
            await self.http.delete(_SUBSCRIBER_NOTIFICATIONS)
            return True
        except Exception:
            return False
