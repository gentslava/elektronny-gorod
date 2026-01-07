import traceback
import json
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import CONF_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN,
    LOGGER,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_OPERATOR_ID,
    CONF_USER_AGENT,
    CONF_WIDTH,
)
from .user_agent import UserAgent
from .api import ElektronnyGorodAPI
from .helpers import find


class ElektronnyGorodUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Elektronny Gorod data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global Elektronny Gorod data updater."""
        user_agent = UserAgent()
        user_agent.from_json(json.loads(entry.data[CONF_USER_AGENT]))
        self._api = ElektronnyGorodAPI(
            user_agent,
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            operator=str(entry.data[CONF_OPERATOR_ID]),
        )
        self._subscriber_places = []

        LOGGER.info(f"Integration loading: {entry.data[CONF_NAME]}")

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
        )

        async_dispatcher_connect(
            hass,
            persistent_notification.SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
            self._notification_dismiss_listener,
        )

    def _notification_dismiss_listener(self, type, data) -> None:
        pass

    async def _async_update_data(self) -> None:
        """Handle device update. This function is only called once when the integration is added to Home Assistant."""
        try:
            LOGGER.info("Integration starting")
            self._subscriber_places = await self._api.query_places()
        except Exception as ex:
            LOGGER.error(f"Integration start failed: {traceback.format_exc()}")
            raise UpdateFailed(ex) from ex

    async def get_cameras_info(self) -> list:
        LOGGER.info("Get cameras info")
        return await self._api.query_cameras()

    async def get_camera_stream(self, camera_id) -> str | None:
        LOGGER.info("Get camera stream")
        return await self._api.query_camera_stream(camera_id)

    async def get_camera_snapshot(self, camera_id, width, height) -> bytes:
        if not width:
            width = CONF_WIDTH
        if not height:
            height = round(width / 16 * 9)
        LOGGER.info(f"Get camera {camera_id} snapshot with size {width}x{height}")
        return await self._api.query_camera_snapshot(camera_id, width, height)

    async def update_camera_state(self, camera_id) -> dict:
        LOGGER.info(f"Update camera {camera_id} state")

        cameras = await self._api.query_cameras()
        return find(cameras, lambda camera: camera["ID"] == camera_id)

    async def get_locks_info(self) -> list:
        LOGGER.info("Get locks info")

        locks = []
        for subscriber_place in self._subscriber_places:
            place_id = subscriber_place["place"]["id"]
            self._api.http.user_agent.place_id = place_id
            access_controls = await self._api.query_access_controls(place_id)
            for access_control in access_controls:
                entrances = access_control["entrances"]
                for entrance in entrances:
                    lock = {
                        "place_id": place_id,
                        "access_control_id": access_control["id"],
                        "entrance_id": entrance["id"],
                        "name": entrance["name"],
                        "openable": entrance["allowOpen"],
                    }
                    locks.append(lock)
                    
                if not entrances:
                    lock = {
                        "place_id": place_id,
                        "access_control_id": access_control["id"],
                        "entrance_id": None,
                        "name": access_control["name"],
                        "openable": access_control["allowOpen"],
                    }
                    locks.append(lock)
        return locks

    async def update_lock_state(self, place_id, access_control_id, entrance_id) -> dict:
        LOGGER.info(f"Update lock {place_id}_{access_control_id}_{entrance_id} state")

        subscriber_place = await self._api.query_places(place_id)
        place = subscriber_place["place"]

        access_control = find(
            place["accessControls"],
            lambda access_control: access_control["id"] == access_control_id,
        )

        if not access_control["entrances"]:
            return {
                "place_id": place["id"],
                "access_control_id": access_control["id"],
                "entrance_id": None,
                "name": access_control["name"],
                "openable": access_control["allowOpen"],
            }

        entrance = find(
            access_control["entrances"], lambda entrance: entrance["id"] == entrance_id
        )

        return {
            "place_id": place["id"],
            "access_control_id": access_control["id"],
            "entrance_id": entrance["id"],
            "name": entrance["name"],
            "openable": entrance["allowOpen"],
        }

    async def open_lock(self, place_id, access_control_id, entrance_id) -> None:
        LOGGER.info(f"Open lock place_id={place_id}, access_control_id={access_control_id}, entrance_id={entrance_id}")
        await self._api.open_lock(place_id, access_control_id, entrance_id)

    async def get_balances_info(self) -> list:
        """Fetch the balances for user places."""
        LOGGER.info(f"Get balances info")

        balances = []
        for subscriber_place in self._subscriber_places:
            place_id = subscriber_place["place"]["id"]
            self._api.http.user_agent.place_id = place_id
            finance_data = await self._api.query_balance(place_id)
            balance = {
                "place_id": place_id,
                "balance": finance_data["balance"],
                "block_type": finance_data["blockType"],
                "payment_date": finance_data["targetDate"],
                "payment_sum": finance_data["amountSum"],
            }
            balances.append(balance)
        return balances

    async def update_balance_state(self, place_id) -> dict:
        LOGGER.info(f"Update balance {place_id} state")

        self._api.http.user_agent.place_id = place_id
        finance_data = await self._api.query_balance(place_id)
        return {
            "place_id": place_id,
            "balance": finance_data["balance"],
            "block_type": finance_data["blockType"],
            "payment_date": finance_data["targetDate"],
            "payment_sum": finance_data["amountSum"],
        }
