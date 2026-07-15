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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    AREA_INTERCOM,
    AREA_INDOOR_CAM,
    AREA_PUBLIC_CAM,
    DOMAIN,
    DOORBELL_CALL_WINDOW_FALLBACK_SEC,
    LOGGER,
    SIGNAL_DOORBELL,
)
from .coordinator import ElektronnyGorodUpdateCoordinator
from .history import SIGNAL_HISTORY_EVENT

EVENT_RING = "ring"
EVENT_ENDED = "ended"
EVENT_CALL_ACCEPTED = "call_accepted"
EVENT_CALL_MISSED = "call_missed"
EVENT_MOTION = "motion"

# Авто-`ended`: оператор присылает `ended` только при «принят на другом
# устройстве». На сброс у домофона / истечение времени ответа end-пуша нет —
# иначе статус навсегда завис бы на `ring`. Закрываем вызов сами ровно в момент
# `call_invalidated` (операторское окно из payload, не угаданная константа).
# Без margin: по прод-данным реальный `ended` прилетает за ~20с ДО call_invalidated
# (и снимает таймер через _cancel_auto_end), так что буфер ничего не ловил.
# Fallback-окно (нет/невалиден call_invalidated) — shared с sip/call_controller.py.
_AUTO_END_FALLBACK_SEC = DOORBELL_CALL_WINDOW_FALLBACK_SEC


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod doorbell call events based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    locks = (coordinator.data or {}).get("locks") or []

    # Дедуп по (place_id, access_control_id) — одна event-сущность на домофон
    # (FCM-payload несёт AccessControlId, не entrance). При multi-entrance AC
    # берём lock с min entrance_id → стабильный intercom-device между рестартами.
    by_ac: dict[tuple[str, str], dict] = {}
    for lk in locks:
        key = (lk.get("place_id"), lk.get("access_control_id"))
        if None in key:
            continue
        cur = by_ac.get(key)
        if cur is None or str(lk.get("entrance_id") or "") < str(cur.get("entrance_id") or ""):
            by_ac[key] = lk

    entities: list[EventEntity] = []
    entities.extend(
        ElektronnyGorodDoorbellEvent(coordinator, lock_info)
        for lock_info in by_ac.values()
    )
    entities.extend(
        ElektronnyGorodAccessHistoryEvent(coordinator, lock_info)
        for lock_info in by_ac.values()
    )
    entities.extend(
        ElektronnyGorodCameraHistoryEvent(coordinator, camera_info)
        for camera_info in (coordinator.data or {}).get("cameras") or []
        if camera_info.get("source") in ("intercom", "public")
    )
    async_add_entities(entities)


class ElektronnyGorodAccessHistoryEvent(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], EventEntity
):
    """Durable accepted/missed-call history for one access control."""

    _attr_has_entity_name = True
    _attr_translation_key = "access_history"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = [EVENT_CALL_ACCEPTED, EVENT_CALL_MISSED]

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        lock_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        place_id = str(lock_info["place_id"])
        access_control_id = str(lock_info["access_control_id"])
        self._place_id = place_id
        self._access_control_id = access_control_id
        entrance_id = lock_info.get("entrance_id")
        self._attr_unique_id = (
            f"{DOMAIN}_event_history_access_{place_id}_{access_control_id}"
        )
        device_uid = (
            f"entrance_{place_id}_{access_control_id}_{entrance_id or 'main'}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
            name=lock_info["name"],
            manufacturer="Электронный город",
            model="Intercom",
            suggested_area=AREA_INTERCOM,
            via_device=(DOMAIN, f"place_{place_id}"),
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to sanitized durable-history events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_HISTORY_EVENT,
                self._handle_history,
            )
        )

    @callback
    def _handle_history(self, payload: dict[str, Any]) -> None:
        """Route one verified access-control event to this entity."""
        event_type = payload.get("event_type")
        if (
            event_type not in self._attr_event_types
            or payload.get("source_type") != "accessControl"
            or str(payload.get("place_id")) != self._place_id
            or str(payload.get("source_id")) != self._access_control_id
        ):
            return
        attributes = {
            key: payload[key]
            for key in ("event_id", "occurred_at")
            if key in payload
        }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()


class ElektronnyGorodCameraHistoryEvent(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], EventEntity
):
    """Durable verified motion history for one forpost camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "camera_history"
    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = [EVENT_MOTION]

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        camera_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        camera_id = str(camera_info["id"])
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_event_history_camera_{camera_id}"

        source = camera_info.get("source") or "public"
        place_id = camera_info.get("place_id")
        access_control_id = camera_info.get("access_control_id")
        entrance_id = camera_info.get("entrance_id")
        if source == "intercom" and place_id and access_control_id:
            device_uid = (
                f"entrance_{place_id}_{access_control_id}_{entrance_id or 'main'}"
            )
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_uid)},
                name=camera_info.get("name") or camera_id,
                manufacturer="Электронный город",
                model="Intercom",
                suggested_area=AREA_INTERCOM,
                via_device=(DOMAIN, f"place_{place_id}"),
            )
        else:
            model = "Indoor Camera" if source == "place" else "Public Camera"
            area = AREA_INDOOR_CAM if source == "place" else AREA_PUBLIC_CAM
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"camera_{camera_id}")},
                name=camera_info.get("name") or camera_id,
                manufacturer="Электронный город",
                model=model,
                suggested_area=area,
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to sanitized durable-history events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_HISTORY_EVENT,
                self._handle_history,
            )
        )

    @callback
    def _handle_history(self, payload: dict[str, Any]) -> None:
        """Route one verified motion event to this camera entity."""
        event_type = payload.get("event_type")
        if (
            event_type != EVENT_MOTION
            or str(payload.get("camera_id")) != self._camera_id
        ):
            return
        attributes = {
            key: payload[key]
            for key in (
                "event_id",
                "occurred_at",
                "duration",
                "recording_available",
            )
            if key in payload
        }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()


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
        self._auto_end_cancel: CALLBACK_TYPE | None = None
        self._ring_attributes: dict[str, Any] = {}

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
        """Подписка на realtime-сигнал вызова + baseline «нет вызова»."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_DOORBELL, self._handle_doorbell)
        )
        self.async_on_remove(self._cancel_auto_end)
        # EventEntity(RestoreEntity) сам восстанавливает последнее событие после
        # рестарта HA / reload. Если восстанавливать нечего (самый первый запуск) —
        # state=None («Неизвестно»). Ставим условный baseline `ended` = нет
        # активного вызова, чтобы сущность не висела в Unknown. В момент первой
        # установки реальный вызов крайне маловероятен, а настоящий `ring` его
        # сразу перепишет. На рестартах baseline не трогаем (state уже восстановлен)
        # — синтетическое событие стреляет максимум один раз, до появления автоматизаций.
        if self.state is None:
            self._trigger_event(EVENT_ENDED)
            self.async_write_ha_state()

    @callback
    def _handle_doorbell(self, payload: dict[str, Any]) -> None:
        """Dispatcher callback. Стреляем event, если вызов для нашего домофона.

        payload (от fcm.py): {"event_type": "ring"|"ended", "place_id",
        "access_control_id", "attributes": {...}}.
        """
        if (
            str(payload.get("place_id")) != str(self._place_id)
            or str(payload.get("access_control_id")) != str(self._access_control_id)
        ):
            return
        event_type = payload.get("event_type")
        if event_type not in self._attr_event_types:
            LOGGER.debug("Doorbell: неизвестный event_type %s — пропуск", event_type)
            return
        attributes = dict(payload.get("attributes") or {})
        # Apartment/Sender в пуше у калиток gate-кодированы префиксом корпуса/секции;
        # канонический номер квартиры жильца — в place.address оператора
        # (coordinator.data["places"]). Подъезд шлёт уже чистый номер.
        canonical_apartment = self._resident_apartment()
        if canonical_apartment:
            attributes["apartment"] = canonical_apartment
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
        if event_type == EVENT_RING:
            self._schedule_auto_end(attributes)
        else:  # реальный `ended` — снять авто-таймер, чтобы не было дубля
            self._cancel_auto_end()

    def _resident_apartment(self) -> str | None:
        """Канонический номер квартиры жильца из place.address оператора.

        Место истины — `apartment` в subscriber-places (coordinator.data["places"]),
        а не gate-кодированный `Apartment`/`Sender` из FCM-пуша.
        """
        for sp in (self.coordinator.data or {}).get("places") or []:
            place = sp.get("place") or {}
            if str(place.get("id")) == str(self._place_id):
                address = place.get("address")
                if isinstance(address, dict):
                    return address.get("apartment")
        return None

    @callback
    def _schedule_auto_end(self, ring_attributes: dict[str, Any]) -> None:
        """Взвести авто-`ended` к моменту `call_invalidated` из push.

        Оператор шлёт `ended` только при «принят на другом устройстве». На сброс
        у домофона / истечение времени ответа end-пуша нет — без этого статус
        завис бы на `ring`. Берём операторское окно (`call_invalidated`), не
        угадываем константу; при отсутствии/невалидности — fallback.
        """
        self._cancel_auto_end()
        self._ring_attributes = ring_attributes
        delay = _AUTO_END_FALLBACK_SEC
        invalidated = ring_attributes.get("call_invalidated")
        if invalidated:
            parsed = dt_util.parse_datetime(invalidated)
            if parsed is not None:
                remaining = (parsed - dt_util.utcnow()).total_seconds()
                delay = max(remaining, 1.0)
        self._auto_end_cancel = async_call_later(self.hass, delay, self._auto_end_fire)

    @callback
    def _auto_end_fire(self, _now: Any) -> None:
        """Сработал таймер: реального `ended` не пришло → закрываем вызов сами."""
        self._auto_end_cancel = None
        self._trigger_event(
            EVENT_ENDED,
            {
                "reason": "timeout",
                "call_id": self._ring_attributes.get("call_id"),
                "gate_name": self._ring_attributes.get("gate_name"),
            },
        )
        self.async_write_ha_state()

    @callback
    def _cancel_auto_end(self) -> None:
        """Снять отложенный авто-`ended` (реальный конец / новый вызов / удаление)."""
        if self._auto_end_cancel is not None:
            self._auto_end_cancel()
            self._auto_end_cancel = None
