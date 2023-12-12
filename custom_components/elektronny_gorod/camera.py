from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

class ElektronnyGorogCamera(Entity):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        camera_info: dict
    ) -> None:
        self.coordinator = coordinator
        self.camera_info = camera_info

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

    async def async_update(self) -> None:
        # Обновляем состояние камеры, если необходимо
        await self.coordinator.update_camera_state(self.camera_info["id"])