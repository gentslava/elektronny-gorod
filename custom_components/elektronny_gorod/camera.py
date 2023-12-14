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
    cameras = []
    cameras_info = await coordinator.get_cameras_info()
    for camera_info in cameras_info:
        stream_url = await coordinator.get_camera_stream()
        camera = {
            camera_info,
            stream_url
        }
        cameras.append(camera)

    LOGGER.info("Setting up camera entries %s", cameras)
    # Create camera entities
    async_add_entities(
        ElektronnyGorogCamera(
            coordinator,
            camera
        )
        for camera in cameras
    )

class ElektronnyGorogCamera(Camera):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        camera: dict
    ) -> None:
        LOGGER.info("ElektronnyGorogCamera init %s", camera)
        self._coordinator: ElektronnyGorogDataUpdateCoordinator = coordinator
        self._camera_info: dict = camera.camera_info
        self._stream_url: str | None = camera.stream_url
        self._image: bytes | None = None
        self.content_type = "image/jpg"

    @property
    def unique_id(self) -> str:
        """Return camera unique_id."""
        return f"{self._camera_info['ID']}_{self._camera_info['Name']}"

    @property
    def name(self) -> str:
        """Return camera name."""
        return self._camera_info["Name"]

    @property
    def is_on(self) -> bool:
        """Return camera state is_on."""
        return self._camera_info["IsActive"] == 1

    @property
    def is_recording(self) -> bool:
        """Return camera state is_recording."""
        return self._camera_info["RecordType"] == 1

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        image = await self._coordinator.get_camera_snapshot(self._camera_info["ID"])
        if image:
            self._image = image
        return self._image

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._stream_url

    async def async_update(self) -> None:
        """Update camera state."""
        self._camera_info = await self._coordinator.update_camera_state(self._camera_info["ID"])
