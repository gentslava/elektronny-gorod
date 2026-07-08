"""Balance sensor — CoordinatorEntity-based.

Slice 3c (Bronze polish):
- `_attr_has_entity_name = True` + `_attr_translation_key = "balance"` — имя
  entity берётся из translations (см. `strings.json`).
- `device_class = MONETARY`, `state_class = TOTAL`, unit = `CURRENCY_RUBLE` —
  даёт корректные long-term statistics в HA.
- `device_info` группирует sensor с place (один device = один адрес).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AREA_INTERCOM,
    CALL_STATE_ACTIVE,
    CALL_STATE_CONNECTING,
    CALL_STATE_ENDED,
    CALL_STATE_ERROR,
    CALL_STATE_IDLE,
    CALL_STATE_RINGING,
    DOMAIN,
    EVENT_CALL_STATE,
    LOGGER,
)
from .coordinator import ElektronnyGorodUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Sensors (balance + days_to_block per place)."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    balances = (coordinator.data or {}).get("balances") or []
    entities: list[SensorEntity] = []
    for balance_info in balances:
        place_id = balance_info["place_id"]
        entities.append(ElektronnyGorodBalanceSensor(coordinator, place_id))
        entities.append(ElektronnyGorodDaysToBlockSensor(coordinator, place_id))

    # call_state — одна сущность на домофон (дедуп по (place_id, access_control_id),
    # как event.py: FCM-payload несёт AccessControlId, не entrance). Push-driven
    # через EVENT_CALL_STATE (sip/call_controller.py) — единый источник фазы вызова.
    locks = (coordinator.data or {}).get("locks") or []
    by_ac: dict[tuple, dict] = {}
    for lk in locks:
        key = (lk.get("place_id"), lk.get("access_control_id"))
        if None in key:
            continue
        cur = by_ac.get(key)
        if cur is None or str(lk.get("entrance_id") or "") < str(cur.get("entrance_id") or ""):
            by_ac[key] = lk
    entities.extend(ElektronnyGorodCallStateSensor(lk) for lk in by_ac.values())

    async_add_entities(entities)


class ElektronnyGorodBalanceSensor(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], SensorEntity
):
    """Balance sensor (CoordinatorEntity)."""

    _attr_has_entity_name = True
    _attr_translation_key = "balance"
    _attr_icon = "mdi:cash-multiple"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    # SensorDeviceClass.MONETARY требует ISO 4217 currency code; константа
    # `CURRENCY_RUBLE` (= "₽") удалена из homeassistant.const в новых релизах.
    _attr_native_unit_of_measurement = "RUB"

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"place_{place_id}")},
            name=self._place_display_name(),
            manufacturer="Электронный город",
            model="Place",
        )

    def _place_display_name(self) -> str:
        """Достать читаемое имя места из coordinator.data.places.

        `place.address` от API оператора — это **dict** (regional structure),
        не строка. DeviceInfo.name требует str; иначе HA молча отбрасывает
        entity при регистрации в state machine. Поэтому достаём
        `visibleAddress` (готовая строка) или собираем fallback.
        """
        places = (self.coordinator.data or {}).get("places") or []
        for subscriber_place in places:
            place = subscriber_place.get("place") or {}
            if place.get("id") != self._place_id:
                continue
            addr = place.get("address")
            if isinstance(addr, dict):
                visible = addr.get("visibleAddress")
                if isinstance(visible, str) and visible:
                    return visible
            if isinstance(addr, str) and addr:
                return addr
            name = place.get("name")
            if isinstance(name, str) and name:
                return name
            break
        return f"Place {self._place_id}"

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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Дополнительные атрибуты (payment info).

        Ключи — Title Case для обратной совместимости с пользовательскими
        автоматизациями. Перевод на snake_case — отдельный slice (A-30,
        Итерация 3 / Silver), требует release notes как breaking change.
        """
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

        return {
            "Amount sum": amount_sum,
            "Target date": target_date,
            "Payment link": info.get("payment_link"),
            "Blocked": info.get("blocked"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator обновился — нашу state читаем из coordinator.data в propertах."""
        self.async_write_ha_state()


class ElektronnyGorodDaysToBlockSensor(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], SensorEntity
):
    """Days-to-block из /finance response (A-57).

    Backend возвращает `daysToBlock` int — дней до автоматической блокировки
    аккаунта оператором при отсутствии оплаты. Полезно для automation:
    «if days_to_block <= 3 → уведомить + (опц.) кликнуть button.pay».
    """

    _attr_has_entity_name = True
    _attr_translation_key = "days_to_block"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        place_id: str,
    ) -> None:
        super().__init__(coordinator)
        LOGGER.debug("DaysToBlockSensor init for place_id=%s", place_id)
        self._place_id = place_id
        self._attr_unique_id = f"{DOMAIN}_{place_id}_days_to_block"
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
            and info.get("days_to_block") is not None
        )

    @property
    def native_value(self) -> int | None:
        info = self._balance_info
        if info is None:
            return None
        return info.get("days_to_block")

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class ElektronnyGorodCallStateSensor(SensorEntity):
    """Фаза вызова домофона (idle/ringing/connecting/active/ended/error).

    Единый источник истины для карточки вызова и автоматизаций. Push-driven:
    слушает bus-событие `EVENT_CALL_STATE` (его шлёт DoorbellCallController на
    каждом переходе). НЕ CoordinatorEntity — состояние не из coordinator.data,
    а из realtime-сигнала; coordinator используется лишь при setup (lock_info).
    Device — общий с lock/event/intercom-camera того же домофона.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "call_state"
    _attr_icon = "mdi:phone-ring-outline"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        CALL_STATE_IDLE,
        CALL_STATE_RINGING,
        CALL_STATE_CONNECTING,
        CALL_STATE_ACTIVE,
        CALL_STATE_ENDED,
        CALL_STATE_ERROR,
    ]

    def __init__(self, lock_info: dict[str, Any]) -> None:
        self._place_id: str = lock_info["place_id"]
        self._access_control_id: str = lock_info["access_control_id"]
        self._entrance_id = lock_info.get("entrance_id")
        self._name: str = lock_info["name"]
        self._attr_native_value = CALL_STATE_IDLE
        self._extra: dict[str, Any] = {}
        self._attr_unique_id = (
            f"{DOMAIN}_call_state_{self._place_id}_{self._access_control_id}"
        )
        # Тот же device, что у lock/event/intercom-camera этого домофона (см. event.py).
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

    async def async_added_to_hass(self) -> None:
        """Подписка на realtime-фазу вызова (EVENT_CALL_STATE)."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CALL_STATE, self._handle_call_state)
        )

    @callback
    def _handle_call_state(self, event: Event) -> None:
        """Bus-callback: обновить state, если фаза относится к нашему домофону."""
        data = event.data
        if (
            str(data.get("access_control_id")) != str(self._access_control_id)
            or str(data.get("place_id")) != str(self._place_id)
        ):
            return
        self._attr_native_value = data.get("state", CALL_STATE_IDLE)
        self._extra = {
            "call_id": data.get("call_id"),
            "intercom_name": self._name,
            "started_at": data.get("started_at"),
            "access_control_id": self._access_control_id,
            "place_id": self._place_id,
        }
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra
