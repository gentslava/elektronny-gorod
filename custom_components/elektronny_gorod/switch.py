"""Do Not Disturb switches.

Master + 2 dependent (см. api-reference §settings/do_not_disturb):
- `DO_NOT_DISTURB_ROOT`         — master (всегда available).
- `INTERCOM_CALLS`              — dependent (available только если root=ON).
- `MANAGEMENT_COMPANY_CALLS`    — dependent.

Mirror semantics приложения: при выключении master зависимые скрываются
из UI приложения. В HA — отражаем через `_attr_available = root_state`.
HA нативно красит unavailable серым, но registry entry сохраняется.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import ElektronnyGorodUpdateCoordinator

DND_ROOT = "DO_NOT_DISTURB_ROOT"
DND_INTERCOM = "INTERCOM_CALLS"
DND_MGMT = "MANAGEMENT_COMPANY_CALLS"

# Translation keys в strings.json → entity.switch.{key}.name
_TRANSLATION_KEYS: dict[str, str] = {
    DND_ROOT: "dnd_root",
    DND_INTERCOM: "dnd_intercom_calls",
    DND_MGMT: "dnd_management_company_calls",
}

_ICONS: dict[str, str] = {
    DND_ROOT: "mdi:bell-off",
    DND_INTERCOM: "mdi:phone-off",
    DND_MGMT: "mdi:office-building-remove",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DND switches based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    dnd_per_place: dict[str, list[dict[str, Any]]] = (
        (coordinator.data or {}).get("dnd") or {}
    )

    entities: list[ElektronnyGorodDNDSwitch] = []
    for place_id, items in dnd_per_place.items():
        present_types = {item.get("type") for item in items}
        for dnd_type in (DND_ROOT, DND_INTERCOM, DND_MGMT):
            if dnd_type in present_types:
                entities.append(
                    ElektronnyGorodDNDSwitch(coordinator, place_id, dnd_type)
                )

    async_add_entities(entities)


class ElektronnyGorodDNDSwitch(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], SwitchEntity
):
    """Do Not Disturb switch (один из 3-х per place).

    State source — `coordinator.data["dnd"][place_id]` (list of items).
    Toggle — POST `/settings/do_not_disturb` через api с обновлённым status,
    затем refresh coordinator.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        place_id: str,
        dnd_type: str,
    ) -> None:
        """Initialize DND switch."""
        super().__init__(coordinator)
        self._place_id = str(place_id)
        self._dnd_type = dnd_type
        self._attr_translation_key = _TRANSLATION_KEYS[dnd_type]
        self._attr_icon = _ICONS[dnd_type]
        self._attr_unique_id = (
            f"{DOMAIN}_dnd_{self._place_id}_{_TRANSLATION_KEYS[dnd_type]}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"place_{self._place_id}")},
        )

    # ------------------------------------------------------------------ #
    # State helpers                                                      #
    # ------------------------------------------------------------------ #

    @property
    def _dnd_items(self) -> list[dict[str, Any]] | None:
        """Все DND items для нашего place из coordinator.data."""
        dnd = (self.coordinator.data or {}).get("dnd") or {}
        return dnd.get(self._place_id)

    def _item(self, dnd_type: str) -> dict[str, Any] | None:
        items = self._dnd_items
        if not items:
            return None
        for item in items:
            if item.get("type") == dnd_type:
                return item
        return None

    @property
    def _own_item(self) -> dict[str, Any] | None:
        return self._item(self._dnd_type)

    @property
    def _root_status(self) -> bool:
        """True если DO_NOT_DISTURB_ROOT включён (для available у dependent)."""
        root = self._item(DND_ROOT)
        return bool(root and root.get("status"))

    # ------------------------------------------------------------------ #
    # HA properties                                                      #
    # ------------------------------------------------------------------ #

    @property
    def available(self) -> bool:
        """Master всегда available; dependent — только при root=ON."""
        if not super().available:
            return False
        if self._own_item is None:
            return False
        if self._dnd_type == DND_ROOT:
            return True
        return self._root_status

    @property
    def is_on(self) -> bool | None:
        """Current status."""
        item = self._own_item
        if item is None:
            return None
        return bool(item.get("status"))

    # ------------------------------------------------------------------ #
    # Service calls                                                      #
    # ------------------------------------------------------------------ #

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Включить DND."""
        await self._set_status(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Выключить DND."""
        await self._set_status(False)

    async def _set_status(self, status: bool) -> None:
        """Send POST с обновлённым нашим item.status, refresh coordinator."""
        items = self._dnd_items
        if not items:
            LOGGER.warning(
                "DND %s for place=%s: no items in coordinator, skipping toggle",
                self._dnd_type, self._place_id,
            )
            return

        payload: list[dict[str, Any]] = []
        for item in items:
            new_item = dict(item)
            if new_item.get("type") == self._dnd_type:
                new_item["status"] = status
            payload.append(new_item)

        ok = await self.coordinator.async_set_dnd(self._place_id, payload)
        if not ok:
            LOGGER.warning(
                "DND POST failed for place=%s type=%s status=%s",
                self._place_id, self._dnd_type, status,
            )
            return

        # Refresh coordinator чтобы entity увидела новый state.
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator обновился — read state из coordinator.data в properties."""
        self.async_write_ha_state()
