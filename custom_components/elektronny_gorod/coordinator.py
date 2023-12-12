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

    async def update_camera_state(self, id):
        LOGGER.info("Update camera %s state", id)
        pass