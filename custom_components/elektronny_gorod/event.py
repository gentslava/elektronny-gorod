"""Doorbell call `event` entity — приём realtime-события вызова домофона.

Событие приходит по FCM data-push (см. fcm.py), парсится и рассылается через
dispatcher (`SIGNAL_DOORBELL`). Эта сущность ловит его и стреляет `event`:
- `ring`  — входящий вызов (`CALL_INCOMING`);
- `ended` — вызов завершён/принят на другом устройстве (`CALL_END_ANSWERED_MOBILE`).

Источник канала и payload — research/intercom-call-probe/FINDINGS.md.

Одна сущность на домофон `(place_id, access_control_id)` — дедуп по AC из
`coordinator.data["locks"]`. Device — общий с lock/intercom-camera того же
entrance (см. lock.py). Открытие двери — существующий lock; видео — go2rtc.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AREA_INTERCOM, DOMAIN, LOGGER, SIGNAL_DOORBELL
from .coordinator import ElektronnyGorodUpdateCoordinator

EVENT_RING = "ring"
EVENT_ENDED = "ended"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod doorbell call events based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    locks = (coordinator.data or {}).get("locks") or []

    # Дедуп по (place_id, access_control_id) — одна event-сущность на домофон.
    # Первый matching lock даёт entrance_id/name для общего intercom-device.
    seen: set[tuple[str, str]] = set()
    entities: list[ElektronnyGorodDoorbellEvent] = []
    for lk in locks:
        key = (lk.get("place_id"), lk.get("access_control_id"))
        if None in key or key in seen:
            continue
        seen.add(key)
        entities.append(ElektronnyGorodDoorbellEvent(coordinator, lk))

    async_add_entities(entities)


class ElektronnyGorodDoorbellEvent(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], EventEntity
):
    """`event`-сущность вызова домофона (EventDeviceClass.DOORBELL)."""

    _attr_has_entity_name = True
    _attr_translation_key = "doorbell"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = [EVENT_RING, EVENT_ENDED]

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        lock_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._place_id: str = lock_info["place_id"]
        self._access_control_id: str = lock_info["access_control_id"]
        self._entrance_id = lock_info.get("entrance_id")
        self._name: str = lock_info["name"]

        self._attr_unique_id = (
            f"{DOMAIN}_event_doorbell_{self._place_id}_{self._access_control_id}"
        )
        # Тот же device, что у lock/intercom-camera этого entrance.
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
        """Подписка на realtime-сигнал вызова."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_DOORBELL, self._handle_doorbell)
        )

    @callback
    def _handle_doorbell(self, payload: dict[str, Any]) -> None:
        """Dispatcher callback. Стреляем event, если вызов для нашего домофона.

        payload (от fcm.py): {"event_type": "ring"|"ended", "place_id",
        "access_control_id", "attributes": {...}}.
        """
        if str(payload.get("access_control_id")) != str(self._access_control_id):
            return
        event_type = payload.get("event_type")
        if event_type not in self._attr_event_types:
            LOGGER.debug("Doorbell: неизвестный event_type %s — пропуск", event_type)
            return
        self._trigger_event(event_type, payload.get("attributes") or {})
        self.async_write_ha_state()
