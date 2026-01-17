from __future__ import annotations

from collections.abc import Callable
import json
import traceback
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElektronnyGorodAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DEFAULT_SNAPSHOT_WIDTH,
    DOMAIN,
    LOGGER,
)
from .helpers import find, dedupe_by_id
from .user_agent import UserAgent


class ElektronnyGorodUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Elektronny Gorod data."""

    def __init__(self, hass: HomeAssistant, *, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        user_agent = UserAgent()
        user_agent.from_json(json.loads(entry.data[CONF_USER_AGENT]))

        self._api = ElektronnyGorodAPI(
            user_agent,
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            operator=str(entry.data[CONF_OPERATOR_ID]),
        )

        self._subscriber_places: list[dict[str, Any]] = []

        LOGGER.info(f"Integration loading: {entry.data[CONF_NAME]}")

        # Unsubscribe callback for dispatcher listener (called on unload)
        self._unsub_notifications: Callable[[], None] = async_dispatcher_connect(
            hass,
            persistent_notification.SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
            self._notification_dismiss_listener,
        )

        super().__init__(hass, LOGGER, name=DOMAIN)

    @callback
    def _notification_dismiss_listener(self, _type: Any, _data: Any) -> None:
        """Handle HA persistent notification updates (optional hook)."""
        return

    async def _async_update_data(self) -> None:
        """Fetch initial data once when the integration is set up."""
        try:
            LOGGER.info("Integration starting")
            self._subscriber_places = await self._api.query_places()
        except Exception as ex:
            LOGGER.error("Integration start failed: %s", traceback.format_exc())
            raise UpdateFailed(ex) from ex

    def async_unsubscribe(self) -> None:
        """Unsubscribe internal listeners (called from async_unload_entry)."""
        if hasattr(self, "_unsub_notifications") and callable(self._unsub_notifications):
            self._unsub_notifications()

    async def get_cameras_info(self) -> list[dict[str, Any]]:
        """Fetch cameras list."""
        LOGGER.info("Getting cameras info")

        cameras: list[dict[str, Any]] = []

        for subscriber_place in self._subscriber_places:
            place = subscriber_place.get("place") or {}
            place_id = place.get("id")
            if not place_id:
                continue

            self._api.http.user_agent.place_id = place_id
        
            access_controls = await self._api.query_access_controls(place_id)
            for access_control in access_controls:
                if not access_control.get("externalCameraId"):
                    continue

                camera = {
                    "id": access_control.get("externalCameraId"),
                    "name": access_control.get("name"),
                }
                cameras.append(camera)

            available_public_cameras = await self._api.query_public_cameras(place_id)
            for public_camera in available_public_cameras:
                camera = {
                    "id": public_camera.get("externalCameraId") or public_camera.get("id"),
                    "name": public_camera.get("name"),
                }
                cameras.append(camera)

            available_sections = await self._api.query_sections(place_id)

            available_cameras = await self._api.query_cameras(place_id)
            for available_camera in available_cameras:
                camera = {
                    "id": available_camera.get("externalCameraId") or available_camera.get("id"),
                    "name": available_camera.get("name"),
                }
                cameras.append(camera)

        return dedupe_by_id(cameras) if cameras else []

    async def get_camera_stream(self, camera_id: str) -> str | None:
        """Fetch a single-use camera stream URL."""
        LOGGER.info("Getting camera stream")
        return await self._api.query_camera_stream(camera_id)

    async def get_camera_snapshot(
        self,
        camera_id: str,
        width: int | None,
        height: int | None,
    ) -> bytes:
        """Fetch camera snapshot bytes."""
        w = width or DEFAULT_SNAPSHOT_WIDTH
        h = height or round(w / 16 * 9)

        LOGGER.info("Getting camera %s snapshot with size %sx%s", camera_id, w, h)
        return await self._api.query_camera_snapshot(camera_id, w, h)

    async def update_camera_state(self, camera_id: str) -> dict[str, Any]:
        """Refresh and return camera state for a given camera."""
        LOGGER.info("Updating camera %s state", camera_id)

        cameras: list[dict[str, Any]] = []

        for subscriber_place in self._subscriber_places:
            place = subscriber_place.get("place") or {}
            place_id = place.get("id")
            if not place_id:
                continue

            self._api.http.user_agent.place_id = place_id
        
            access_controls = await self._api.query_access_controls(place_id)
            for access_control in access_controls:
                if not access_control.get("externalCameraId"):
                    continue

                camera = {
                    "id": access_control.get("externalCameraId"),
                    "name": access_control.get("name"),
                }
                cameras.append(camera)

            available_public_cameras = await self._api.query_public_cameras(place_id)
            for public_camera in available_public_cameras:
                camera = {
                    "id": public_camera.get("externalCameraId") or public_camera.get("id"),
                    "name": public_camera.get("name"),
                }
                cameras.append(camera)

            available_sections = await self._api.query_sections(place_id)

            available_cameras = await self._api.query_cameras(place_id)
            for available_camera in available_cameras:
                camera = {
                    "id": available_camera.get("externalCameraId") or available_camera.get("id"),
                    "name": available_camera.get("name"),
                }
                cameras.append(camera)

        camera = find(cameras, lambda c: c.get("ID") == camera_id)

        if camera is None:
            raise UpdateFailed(f"Camera {camera_id} not found")

        return camera

    async def get_locks_info(self) -> list[dict[str, Any]]:
        """Build locks list from subscriber places/access controls."""
        LOGGER.info("Getting locks info")

        locks: list[dict[str, Any]] = []

        for subscriber_place in self._subscriber_places:
            place = subscriber_place.get("place") or {}
            place_id = place.get("id")
            if not place_id:
                continue

            self._api.http.user_agent.place_id = place_id
            access_controls = await self._api.query_access_controls(place_id)

            for access_control in access_controls:
                entrances = access_control.get("entrances") or []

                for entrance in entrances:
                    locks.append({
                        "place_id": place_id,
                        "access_control_id": access_control.get("id"),
                        "entrance_id": entrance.get("id"),
                        "name": entrance.get("name"),
                        "openable": entrance.get("allowOpen"),
                    })

                if not entrances:
                    locks.append({
                        "place_id": place_id,
                        "access_control_id": access_control.get("id"),
                        "entrance_id": None,
                        "name": access_control.get("name"),
                        "openable": access_control.get("allowOpen"),
                    })
        return locks

    async def update_lock_state(
        self,
        place_id: str,
        access_control_id: str,
        entrance_id: str | None,
    ) -> dict[str, Any]:
        """Refresh and return lock state."""
        LOGGER.info("Updating lock %s_%s_%s state", place_id, access_control_id, entrance_id)

        access_controls = await self._api.query_access_controls(place_id)
        access_control = find(
            access_controls,
            lambda ac: ac.get("id") == access_control_id,
        )
        if access_control is None:
            raise UpdateFailed(f"Access control {access_control_id} not found")

        if entrance_id is None:
            return {
                "place_id": place_id,
                "access_control_id": access_control.get("id"),
                "entrance_id": None,
                "name": access_control.get("name"),
                "openable": access_control.get("allowOpen"),
            }

        entrances = access_control.get("entrances") or []

        entrance = find(entrances, lambda e: e.get("id") == entrance_id)
        if entrance is None:
            raise UpdateFailed(f"Entrance {entrance_id} not found")

        return {
            "place_id": place_id,
            "access_control_id": access_control.get("id"),
            "entrance_id": entrance.get("id"),
            "name": entrance.get("name"),
            "openable": entrance.get("allowOpen"),
        }

    async def open_lock(self, place_id: str, access_control_id: str, entrance_id: str | None) -> None:
        """Send open lock command."""
        LOGGER.info(
            "Opening lock place_id=%s, access_control_id=%s, entrance_id=%s",
            place_id,
            access_control_id,
            entrance_id,
        )
        await self._api.open_lock(place_id, access_control_id, entrance_id)

    async def get_balances_info(self) -> list[dict[str, Any]]:
        """Fetch balances for user places."""
        LOGGER.info("Getting balances info")

        balances: list[dict[str, Any]] = []

        for subscriber_place in self._subscriber_places:
            place = subscriber_place.get("place") or {}
            place_id = place.get("id")
            if not place_id:
                continue

            self._api.http.user_agent.place_id = place_id
            finance_data = await self._api.query_balance(place_id)
            if not finance_data:
                continue

            balances.append({
                "place_id": place_id,
                "balance": finance_data.get("balance"),
                "block_type": finance_data.get("blockType"),
                "blocked": finance_data.get("blocked"),
                "payment_date": finance_data.get("targetDate"),
                "payment_sum": finance_data.get("amountSum"),
                "payment_link": finance_data.get("paymentLink"),
            })

        return balances

    async def update_balance_state(self, place_id: str) -> dict[str, Any]:
        """Refresh and return a single balance state."""
        LOGGER.info("Updating balance %s state", place_id)

        self._api.http.user_agent.place_id = place_id
        finance_data = await self._api.query_balance(place_id)
        if not finance_data:
            raise UpdateFailed(f"Finance data not found for place {place_id}")

        return {
            "place_id": place_id,
            "balance": finance_data.get("balance"),
            "block_type": finance_data.get("blockType"),
            "blocked": finance_data.get("blocked"),
            "payment_date": finance_data.get("targetDate"),
            "payment_sum": finance_data.get("amountSum"),
            "payment_link": finance_data.get("paymentLink"),
        }
