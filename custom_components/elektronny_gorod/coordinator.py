from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import CONF_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
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
            hass=self.hass,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            headers={
                "Operator": self.operatorId,
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

    async def get_cameras_info() -> list:
        LOGGER.info("Get cameras info")
        return []

    async def update_camera_state(id):
        LOGGER.info("Update camera %s state", id)
        pass