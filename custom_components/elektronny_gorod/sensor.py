"""Balance sensor — CoordinatorEntity-based.

См. ADR-0002. Slice 3b: entity использует coordinator.data напрямую через
CoordinatorEntity._handle_coordinator_update. Старый async_update удалён.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import ElektronnyGorodUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Balance Sensor based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    balances = (coordinator.data or {}).get("balances") or []
    async_add_entities(
        ElektronnyGorodBalanceSensor(coordinator, balance_info["place_id"])
        for balance_info in balances
    )


class ElektronnyGorodBalanceSensor(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], SensorEntity
):
    """Balance sensor (CoordinatorEntity)."""

    _attr_icon = "mdi:cash-multiple"
    _attr_name = "Баланс аккаунта"

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        place_id: str,
    ) -> None:
        """Initialize the balance sensor."""
        super().__init__(coordinator)
        LOGGER.debug("BalanceSensor init for place_id=%s", place_id)
        self._place_id = place_id
        self._attr_unique_id = f"{DOMAIN}_{place_id}_balance"

    @property
    def _balance_info(self) -> dict[str, Any] | None:
        """Найти balance для нашего place_id в текущем coordinator.data."""
        balances = (self.coordinator.data or {}).get("balances") or []
        for entry in balances:
            if entry.get("place_id") == self._place_id:
                return entry
        return None

    @property
    def available(self) -> bool:
        """Доступен, если coordinator.data содержит balance для нашего place."""
        return super().available and self._balance_info is not None

    @property
    def native_value(self) -> float | None:
        """Return state of the sensor."""
        info = self._balance_info
        if info is None:
            return None
        balance = info.get("balance")
        if balance is None:
            return None
        return round(balance, 2)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        # TODO(slice-3c): заменить на CURRENCY_RUBLE (A-14).
        if self.native_value is None:
            return None
        return "₽"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Дополнительные атрибуты (payment info)."""
        info = self._balance_info
        if info is None:
            return None

        payment_sum = info.get("payment_sum")
        amount_sum = round(payment_sum, 2) if payment_sum is not None else None

        payment_date = info.get("payment_date")
        target_date = None
        if payment_date is not None:
            try:
                target_date = datetime.fromisoformat(payment_date).strftime(
                    "%d.%m.%Y, %H:%M:%S"
                )
            except (TypeError, ValueError):
                target_date = payment_date

        # TODO(slice-3c): keys → snake_case (A-30).
        return {
            "Amount sum": amount_sum,
            "Target date": target_date,
            "Payment link": info.get("payment_link"),
            "Blocked": info.get("blocked"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator обновился — нашу state читаем из coordinator.data в propertых."""
        self.async_write_ha_state()
