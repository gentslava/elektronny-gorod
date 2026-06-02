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
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GO2RTC_PUBLISH_HIDDEN,
    CONF_GO2RTC_RTSP_HOST,
    CONF_USE_GO2RTC,
    DEFAULT_GO2RTC_PUBLISH_HIDDEN,
    DOMAIN,
    GO2RTC_RTSP_PORT,
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
    entities.append(ElektronnyGorodRtspUrlsSensor(coordinator, entry))
    async_add_entities(entities)


class ElektronnyGorodRtspUrlsSensor(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], SensorEntity
):
    """Diagnostic sensor with go2rtc RTSP URLs for all published cameras."""

    _attr_has_entity_name = True
    _attr_translation_key = "go2rtc_rtsp_urls"
    _attr_icon = "mdi:cctv"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_go2rtc_rtsp_urls"

    @property
    def _enabled(self) -> bool:
        if CONF_USE_GO2RTC in self._entry.options:
            return bool(self._entry.options.get(CONF_USE_GO2RTC))
        return bool(self._entry.data.get(CONF_USE_GO2RTC, False))

    @property
    def _publish_hidden(self) -> bool:
        return bool(
            self._entry.options.get(
                CONF_GO2RTC_PUBLISH_HIDDEN,
                self._entry.data.get(
                    CONF_GO2RTC_PUBLISH_HIDDEN,
                    DEFAULT_GO2RTC_PUBLISH_HIDDEN,
                ),
            )
        )

    @property
    def _rtsp_host(self) -> str | None:
        return self._entry.options.get(CONF_GO2RTC_RTSP_HOST) or self._entry.data.get(
            CONF_GO2RTC_RTSP_HOST
        )

    def _camera_urls(self) -> dict[str, str]:
        if not self._enabled or not self._rtsp_host:
            return {}

        urls: dict[str, str] = {}
        for camera in (self.coordinator.data or {}).get("cameras") or []:
            if camera.get("hidden") and not self._publish_hidden:
                continue
            camera_id = str(camera.get("id") or "")
            if not camera_id:
                continue
            name = str(camera.get("name") or camera_id)
            urls[name] = f"rtsp://{self._rtsp_host}:{GO2RTC_RTSP_PORT}/eg_{camera_id}"
        return urls

    @property
    def native_value(self) -> int:
        """Return number of published RTSP URLs."""
        return len(self._camera_urls())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return RTSP URLs in copy-friendly forms."""
        urls = self._camera_urls()
        return {
            "urls": urls,
            "url_list": list(urls.values()),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


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
