"""Button entities — `pay` action для каждого place.

Press → persistent_notification с `payment_link` из /finance response.

HA не имеет нативного browser-launch (server-side, без mobile companion).
Persistent notification — стандартный pattern для «открыть URL через
service call»: пользователь видит уведомление в колокольчике HA с
кликабельной ссылкой на платежную страницу оператора.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
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
    """Set up Elektronny Gorod Buttons (pay per place)."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    balances = (coordinator.data or {}).get("balances") or []
    async_add_entities(
        ElektronnyGorodPayButton(coordinator, balance_info["place_id"])
        for balance_info in balances
    )


class ElektronnyGorodPayButton(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], ButtonEntity
):
    """Press → persistent_notification с текущим payment_link."""

    _attr_has_entity_name = True
    _attr_translation_key = "pay"
    _attr_icon = "mdi:credit-card-outline"

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        place_id: str,
    ) -> None:
        super().__init__(coordinator)
        LOGGER.debug("PayButton init for place_id=%s", place_id)
        self._place_id = place_id
        self._attr_unique_id = f"{DOMAIN}_{place_id}_pay"
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
    def _payment_link(self) -> str | None:
        info = self._balance_info
        if info is None:
            return None
        link = info.get("payment_link")
        return link if isinstance(link, str) and link else None

    @property
    def available(self) -> bool:
        return super().available and self._payment_link is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        link = self._payment_link
        return {"payment_link": link} if link else None

    async def async_press(self) -> None:
        link = self._payment_link
        if not link:
            LOGGER.warning(
                "Pay button pressed для place_id=%s, но payment_link отсутствует",
                self._place_id,
            )
            return
        async_create_notification(
            self.hass,
            f"Платёжная ссылка: [{link}]({link})",
            title="Электронный город — оплата",
            notification_id=f"{DOMAIN}_pay_{self._place_id}",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
