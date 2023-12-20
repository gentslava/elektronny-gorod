import asyncio
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)

from .const import DOMAIN, LOGGER
from .coordinator import ElektronnyGorogDataUpdateCoordinator

LOCK_UNLOCK_DELAY = 5  # Used to give a realistic lock/unlock experience in frontend

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorog Camera based on a config entry."""
    coordinator: ElektronnyGorogDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get cameras info
    locks_info = await coordinator.get_locks_info()

    # Create camera entities
    async_add_entities(
        ElektronnyGorogLock(
            coordinator,
            lock_info
        ) for lock_info in locks_info
    )

class ElektronnyGorogLock(LockEntity):
    def __init__(
        self,
        coordinator: ElektronnyGorogDataUpdateCoordinator,
        lock_info: dict
    ) -> None:
        LOGGER.info("ElektronnyGorogLock init %s", lock_info)
        super().__init__()
        self._coordinator: ElektronnyGorogDataUpdateCoordinator = coordinator
        self._lock_info: dict = lock_info
        self._place_id = self._lock_info["place_id"]
        self._access_control_id = self._lock_info["access_control_id"]
        self._entrance_id = self._lock_info["entrance_id"]
        self._name = self._lock_info["name"]
        self._openable = self._lock_info["openable"]
        self._state = STATE_LOCKED

    @property
    def unique_id(self) -> str:
        """Return lock unique_id."""
        return f"{self._place_id}_{self._access_control_id}_{self._entrance_id}_{self._name}"

    @property
    def name(self) -> str:
        """Return lock name."""
        return self._name

    @property
    def available(self) -> bool:
        """Return lock is available."""
        return self._openable

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._state == STATE_LOCKING

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        LOGGER.info("Not supported")
        self._state = STATE_LOCKED

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock all or specified locks."""
        LOGGER.info(f"Unlock {self.unique_id}")
        self._state = STATE_UNLOCKING
        self.async_write_ha_state()
        await self._coordinator.open_lock(self._place_id, self._access_control_id, self._entrance_id)
        self._state = STATE_UNLOCKED
        self.async_write_ha_state()

    async def fake_timer_lock(self) -> None:
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        self._state = STATE_LOCKED
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update lock state."""
        if self._state == STATE_UNLOCKED:
            await self.fake_timer_lock()
        # self._lock_info = await self._coordinator.update_lock_state(self._place_id, self._access_control_id, self._entrance_id)
        # self._openable = self._lock_info["openable"]
