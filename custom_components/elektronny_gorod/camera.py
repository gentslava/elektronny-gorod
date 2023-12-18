from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HEIGHT, CONF_WIDTH, DOMAIN, LOGGER
from .coordinator import ElektronnyGorogDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorog Camera based on a config entry."""
    coordinator: ElektronnyGorogDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get cameras info
    cameras_info = await coordinator.get_cameras_info()

    # Create camera entities
    async_add_entities(
        ElektronnyGorogCamera(
            coordinator,
            camera_info
        ) for camera_info in cameras_info
    )

class ElektronnyGorogCamera(Camera):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        camera_info: dict
    ) -> None:
        LOGGER.info("ElektronnyGorogCamera init %s", camera_info)
        super().__init__()
        self._coordinator: ElektronnyGorogDataUpdateCoordinator = coordinator
        self._camera_info: dict = camera_info
        self._id = self._camera_info["ID"]
        self._name = self._camera_info["Name"]
        self._is_on = self._camera_info["IsActive"] == 1
        self._is_streaming = self._camera_info["State"] == 1
        self._is_recording = self._camera_info["RecordType"] == 1
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._stream_url: str | None = None
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
        self._stream_url = await self._coordinator.get_camera_stream(self._id)
        LOGGER.info(f"Stream url is {self._stream_url}")
        return self._stream_url

    async def async_update(self) -> None:
        """Update camera state."""
        self._camera_info = await self._coordinator.update_camera_state(self._id)
        self._is_on = self._camera_info["IsActive"] == 1
        self._is_streaming = self._camera_info["State"] == 1
        self._is_recording = self._camera_info["RecordType"] == 1
