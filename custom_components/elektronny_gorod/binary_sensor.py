"""Binary sensors — `blocked` индикатор для каждого place.

Источник — `/finance` response (см. api-reference §finance). Поле
`blocked: bool` отражает блокировку аккаунта оператором (например при
просрочке оплаты). Удобно для automation: «если blocked → уведомить +
trigger button.pay».
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import ElektronnyGorodUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Binary Sensors."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    balances = (coordinator.data or {}).get("balances") or []
    async_add_entities(
        ElektronnyGorodBlockedBinarySensor(coordinator, balance_info["place_id"])
        for balance_info in balances
    )


class ElektronnyGorodBlockedBinarySensor(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], BinarySensorEntity
):
    """`blocked: bool` из /finance response. True = аккаунт заблокирован."""

    _attr_has_entity_name = True
    _attr_translation_key = "blocked"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:cash-lock"

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        place_id: str,
    ) -> None:
        super().__init__(coordinator)
        LOGGER.debug("BlockedBinarySensor init for place_id=%s", place_id)
        self._place_id = place_id
        self._attr_unique_id = f"{DOMAIN}_{place_id}_blocked"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"place_{place_id}")},
        )

    @property
    def _balance_info(self) -> dict[str, Any] | None:
        balances = (self.coordinator.data or {}).get("balances") or []
        for entry in balances:
            if entry.get("place_id") == self._place_id:
                return entry
        return None

    @property
    def available(self) -> bool:
        info = self._balance_info
        return (
            super().available
            and info is not None
            and info.get("blocked") is not None
        )

    @property
    def is_on(self) -> bool | None:
        info = self._balance_info
        if info is None:
            return None
        val = info.get("blocked")
        if val is None:
            return None
        return bool(val)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
