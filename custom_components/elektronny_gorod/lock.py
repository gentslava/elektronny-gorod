"""Lock entity — CoordinatorEntity-based.

См. ADR-0002. Slice 3b: lock использует coordinator.data для availability.
Synthetic state-cycle (UNLOCKED → 5s → LOCKED) сохраняется как cosmetic UX,
но реализован через `async_call_later` (вместо `asyncio.sleep` в `async_update`),
что совместимо с `CoordinatorEntity` (у которой `should_poll=False`).

Полное решение `lock → button` отложено в ADR-0005 (отдельный PR).
"""
from __future__ import annotations

from typing import Any

from aiohttp import ClientError

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AREA_INTERCOM, DOMAIN, LOGGER
from .coordinator import ElektronnyGorodUpdateCoordinator
from .entity_migration import lock_unique_id

LOCK_UNLOCK_DELAY = 5  # секунды cosmetic-UX «открыто»
LOCK_JAMMED_DELAY = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Lock based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    locks = (coordinator.data or {}).get("locks") or []
    async_add_entities(ElektronnyGorodLock(coordinator, lock_info) for lock_info in locks)


class ElektronnyGorodLock(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], LockEntity
):
    """Lock entity (CoordinatorEntity).

    Slice 3c (Bronze polish):
    - Stable `unique_id` без `name` (см. `entity_migration.lock_unique_id`, A-12).
    - `_attr_has_entity_name = True` + `_attr_translation_key = "lock"`:
      entity-имя из translations («Замок» / «Lock»). Device.name = entrance.name
      (например «Калитка 1»). В UI получается «Калитка 1 Замок».
    - `device_info.identifiers = (DOMAIN, f"entrance_{place}_{ac}_{eid|main}")` —
      общий с intercom-camera того же entrance (см. api-reference §Access
      controls — каждая entrance имеет свою `externalCameraId`).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "lock"

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        lock_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._place_id = lock_info["place_id"]
        self._access_control_id = lock_info["access_control_id"]
        self._entrance_id = lock_info["entrance_id"]
        self._name: str = lock_info["name"]
        # Visibility управляется на DEVICE-уровне в __init__.py:_sync_visibility
        # (cascade через HA core: device disabled → entity disabled_by=DEVICE).
        # Synthetic state — управляется async_unlock + async_call_later.
        self._state: LockState = LockState.LOCKED
        # Cancel-handle для запланированного reset (если есть).
        self._cancel_reset = None
        self._attr_unique_id = lock_unique_id(
            self._place_id, self._access_control_id, self._entrance_id
        )
        # Device per entrance: общий с intercom-camera того же entrance.
        # entrance.externalCameraId — первичный источник связи camera↔lock
        # (см. api-reference §Access controls). На уровне access_control в API
        # бывают рассогласования; entrance — точнее.
        device_uid = (
            f"entrance_{self._place_id}_{self._access_control_id}_"
            f"{self._entrance_id or 'main'}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
            name=self._name,
            manufacturer="Электронный город",
            model="Intercom",
            suggested_area=AREA_INTERCOM,
            via_device=(DOMAIN, f"place_{self._place_id}"),
        )

        LOGGER.debug("Lock init for entrance_id=%s", self._entrance_id)

    @property
    def _coordinator_lock_info(self) -> dict[str, Any] | None:
        """Найти текущий lock в coordinator.data."""
        locks = (self.coordinator.data or {}).get("locks") or []
        for lk in locks:
            if (
                lk.get("place_id") == self._place_id
                and lk.get("access_control_id") == self._access_control_id
                and lk.get("entrance_id") == self._entrance_id
            ):
                return lk
        return None

    @property
    def available(self) -> bool:
        """Доступен, если coordinator успешно обновился и lock с
        openable=True есть в coordinator.data.

        Прежняя реализация возвращала `self._openable` напрямую, что могло
        дать `None` (не bool). Здесь нормализуем через `bool(...)`.
        """
        if not super().available:
            return False
        info = self._coordinator_lock_info
        return info is not None and bool(info.get("openable"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the lock.

        Ключи — Title Case для обратной совместимости с пользовательскими
        автоматизациями (A-30 → snake_case отложен в Итерацию 3).
        """
        info = self._coordinator_lock_info
        if info is None:
            return None
        return {
            "Place ID": str(info.get("place_id")),
            "Access control ID": str(info.get("access_control_id")),
            "Entrance ID": str(info.get("entrance_id")),
            "Name": info.get("name"),
            "Openable": str(info.get("openable")),
        }

    @property
    def is_locking(self) -> bool:
        return self._state == LockState.LOCKING

    @property
    def is_unlocking(self) -> bool:
        return self._state == LockState.UNLOCKING

    @property
    def is_jammed(self) -> bool:
        return self._state == LockState.JAMMED

    @property
    def is_locked(self) -> bool:
        return self._state == LockState.LOCKED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock не поддерживается API оператора — это домофон. См. ADR-0005."""
        LOGGER.info("async_lock is not supported (intercom)")
        self._state = LockState.LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Trigger door-open. Synthetic state-cycle через async_call_later."""
        LOGGER.info("Unlock %s", self.unique_id)
        self._state = LockState.UNLOCKING
        self.async_write_ha_state()
        try:
            await self.coordinator.open_lock(
                self._place_id, self._access_control_id, self._entrance_id
            )
        except ClientError:
            self._state = LockState.JAMMED
            self._schedule_reset(LOCK_JAMMED_DELAY)
        else:
            self._state = LockState.UNLOCKED
            self._schedule_reset(LOCK_UNLOCK_DELAY)
        self.async_write_ha_state()

    def _schedule_reset(self, delay: int) -> None:
        """Запланировать возврат state → LOCKED через `delay` секунд.

        Если уже есть pending reset — отменяем (защита от наложения вызовов).
        """
        if self._cancel_reset is not None:
            self._cancel_reset()
            self._cancel_reset = None

        @callback
        def _restore_locked(_now) -> None:
            self._cancel_reset = None
            # Idempotent: восстанавливаем LOCKED только если state ещё в
            # «временной» зоне. Если за время задержки пользователь снова
            # нажал unlock и state теперь UNLOCKING — не перетираем.
            if self._state in (LockState.UNLOCKED, LockState.JAMMED):
                self._state = LockState.LOCKED
                self.async_write_ha_state()

        self._cancel_reset = async_call_later(self.hass, delay, _restore_locked)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup pending reset при удалении entity."""
        if self._cancel_reset is not None:
            self._cancel_reset()
            self._cancel_reset = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator обновился — properties (available/extra_state_attributes)
        читают из coordinator.data в propertах; пишем state."""
        self.async_write_ha_state()
