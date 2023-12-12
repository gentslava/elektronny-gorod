from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.camera import Camera

from .const import (
  DOMAIN,
  LOGGER
)

from .coordinator import ElektronnyGorogDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorog Camera based on a config entry."""
    coordinator: ElektronnyGorogDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get cameras info
    cameras = await coordinator.get_cameras_info()

    LOGGER.info("Setting up camera entries %s", cameras)
    # Create camera entities
    async_add_entities(
        ElektronnyGorogCamera(
            coordinator,
            camera_info
        )
        for camera_info in cameras
    )

class ElektronnyGorogCamera(Camera):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        camera_info: dict
    ) -> None:
        self.coordinator = coordinator
        self.camera_info = camera_info
        self._image: bytes | None = None
        self.content_type = "image/jpg"
        LOGGER.info("ElektronnyGorogCamera init %s", camera_info)

    @property
    def unique_id(self) -> str:
        return f"{self.camera_info['ID']}_{self.camera_info['Name']}"

    @property
    def name(self) -> str:
        return self.camera_info["Name"]

    @property
    def is_on(self) -> bool:
        return self.camera_info["IsActive"] == 1

    @property
    def is_recording(self) -> bool:
        return self.camera_info["RecordType"] == 1

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        image = await self.coordinator.get_camera_snapshot(self.camera_info["ID"])
        if image:
            self._image = image
        return self._image

    async def async_update(self) -> None:
        """Update camera state."""
        self.camera_info = await self.coordinator.update_camera_state(self.camera_info["ID"])
