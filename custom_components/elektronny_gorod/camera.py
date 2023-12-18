from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.camera import Camera, CameraEntityFeature
from .const import (
  DOMAIN,
  LOGGER,
  CONF_WIDTH,
  CONF_HEIGHT
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

    # Create camera entities
    entities = []
    for camera in cameras:
        stream_url = await coordinator.get_camera_stream(camera["ID"])
        entities.append(
            ElektronnyGorogCamera(
                coordinator,
                camera,
                stream_url
            )
        )
    async_add_entities(entities)

class ElektronnyGorogCamera(Camera):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        camera: dict,
        stream_url: str
    ) -> None:
        LOGGER.info("ElektronnyGorogCamera init %s", camera)
        super().__init__()
        self._coordinator: ElektronnyGorogDataUpdateCoordinator = coordinator
        self._camera_info: dict = camera
        self._id = self._camera_info["ID"]
        self._name = self._camera_info["Name"]
        self._is_on = self._camera_info["IsActive"] == 1
        self._is_streaming = self._camera_info["State"] == 1
        self._is_recording = self._camera_info["RecordType"] == 1
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._stream_url: str | None = stream_url
        self._image: bytes | None = None

    @property
    def unique_id(self) -> str:
        """Return camera unique_id."""
        return f"{self._id}_{self._name}"

    @property
    def name(self) -> str:
        """Return camera name."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return camera state is_on."""
        return self._is_on

    @property
    def is_streaming(self) -> bool:
        """Return camera state is_streaming."""
        return self._is_streaming

    @property
    def is_recording(self) -> bool:
        """Return camera state is_recording."""
        return self._is_recording

    async def async_camera_image(
        self,
        width: int | None = CONF_WIDTH,
        height: int | None = CONF_HEIGHT
    ) -> bytes | None:
        """Return bytes of camera image."""
        image = await self._coordinator.get_camera_snapshot(self._id, width, height)
        if image:
            self._image = image
        return self._image

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._stream_url

    async def async_update(self) -> None:
        """Update camera state."""
        self._camera_info = await self._coordinator.update_camera_state(self._id)
        self._stream_url = await self._coordinator.get_camera_stream(self._id)
