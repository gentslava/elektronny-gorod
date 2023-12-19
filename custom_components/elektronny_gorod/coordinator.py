import traceback
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
)
from .api import ElektronnyGorodAPI
from .helpers import find

class ElektronnyGorogDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Elektronny Gorod data from single endpoint."""
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global Elektronny Gorod data updater."""
        self.access_token = entry.data[CONF_ACCESS_TOKEN]
        self.refresh_token = entry.data[CONF_REFRESH_TOKEN]
        self.operatorId = entry.data[CONF_OPERATOR_ID]
        self.api = ElektronnyGorodAPI(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            headers={
                "Operator": str(self.operatorId),
                "Content-Type": "application/json"
            }
        )

        LOGGER.info("Integration loading: %s", entry.data[CONF_NAME])

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
            LOGGER.info("Integration starting...")
            pass
        except Exception as ex:
            LOGGER.error("Integration start failed: %s", traceback.format_exc())
            raise UpdateFailed(ex) from ex

    async def get_cameras_info(self) -> list:
        LOGGER.info("Get cameras info")
        return await self.api.query_cameras()

    async def get_camera_stream(self, id) -> str | None:
        LOGGER.info("Get camera stream")
        return await self.api.query_camera_stream(id)

    async def get_camera_snapshot(self, id, width, height) -> bytes:
        LOGGER.info(f"Get camera {id} snapshot with size {width}x{height}")
        return await self.api.query_camera_snapshot(id, width, height)

    async def update_camera_state(self, id) -> dict:
        LOGGER.info(f"Update camera {id} state")

        cameras = await self.api.query_cameras()
        return find(
            cameras,
            lambda camera: camera["ID"] == id
        )

    async def get_locks_info(self) -> list:
        LOGGER.info("Get locks info")

        subscriber_places = await self.api.query_places()
        locks = []
        for subscriber_place in subscriber_places:
            place = subscriber_place["place"]
            access_controls = place["accessControls"]
            for access_control in access_controls:
                entrances = access_control["entrances"]
                for entrance in entrances:
                    lock = {
                        "place_id": place["id"],
                        "access_control_id": access_control["id"],
                        "entrance_id": entrance["id"],
                        "name": entrance["name"],
                        "openable": entrance["allowOpen"]
                    }
                    locks.append(lock)
        return locks