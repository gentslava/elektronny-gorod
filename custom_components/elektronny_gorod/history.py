"""Durable, privacy-safe event-history polling primitives."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LOGGER


_GENERAL_EVENT_TYPES = {
    "accessControlCallAccepted": "call_accepted",
    "accessControlCallMissed": "call_missed",
}
_CAMERA_MOTION_EVENT_SUBJECT_ID = 126
_CAMERA_LOOKBACK = timedelta(days=1)
_STORAGE_VERSION = 1
_MAX_STORED_IDS = 200

HISTORY_POLL_INTERVAL = timedelta(minutes=5)
SIGNAL_HISTORY_EVENT = f"{DOMAIN}_history_event"


def history_signal(entry_id: str) -> str:
    """Return the durable-history dispatcher signal for one config entry."""
    return f"{SIGNAL_HISTORY_EVENT}_{entry_id}"


def camera_history_unique_id(camera_id: str) -> str:
    """Return the stable registry ID for one camera-history stream."""
    return f"{DOMAIN}_event_history_camera_{camera_id}"


def _general_stream_key(event: Any) -> str:
    """Return the watermark stream for one general-history source."""
    return (
        f"general:{event.place_id}:"
        f"{event.source_type}:{event.source_id}"
    )


def map_general_event_type(event_type: str) -> str | None:
    """Map one runtime-verified backend call type to its HA event type."""
    return _GENERAL_EVENT_TYPES.get(event_type)


def place_display_name(
    data: Mapping[str, Any] | None,
    place_id: str,
) -> str:
    """Return the same stable place label used by HA place devices."""
    for subscriber_place in (data or {}).get("places") or []:
        place = subscriber_place.get("place") or {}
        if str(place.get("id") or "") != place_id:
            continue
        address = place.get("address")
        if isinstance(address, dict):
            visible = address.get("visibleAddress")
            if isinstance(visible, str) and visible:
                return visible
        if isinstance(address, str) and address:
            return address
        name = place.get("name")
        if isinstance(name, str) and name:
            return name
        break
    return f"Place {place_id}"


class HistoryWatermark:
    """Bounded per-stream event-ID watermark with a silent first baseline."""

    def __init__(
        self,
        seen: Mapping[str, Iterable[str]] | None = None,
        *,
        max_ids: int = 200,
    ) -> None:
        self._max_ids = max_ids
        self._seen: dict[str, list[str]] = {
            stream: list(dict.fromkeys(str(event_id) for event_id in event_ids))[
                :max_ids
            ]
            for stream, event_ids in (seen or {}).items()
        }

    def ingest(self, stream: str, event_ids: Iterable[str]) -> tuple[str, ...]:
        """Record newest-first IDs and return unseen IDs after baseline."""
        incoming = list(dict.fromkeys(str(event_id) for event_id in event_ids))
        previous = self._seen.get(stream)
        if previous is None:
            self._seen[stream] = incoming[: self._max_ids]
            return ()

        previous_ids = set(previous)
        new_ids = tuple(
            event_id for event_id in incoming if event_id not in previous_ids
        )
        incoming_ids = set(incoming)
        self._seen[stream] = (
            incoming
            + [event_id for event_id in previous if event_id not in incoming_ids]
        )[: self._max_ids]
        return new_ids

    def as_dict(self) -> dict[str, list[str]]:
        """Return the versionable, JSON-serializable storage payload."""
        return {stream: list(event_ids) for stream, event_ids in self._seen.items()}


class HistoryPoller:
    """Fetch sanitized history and emit only new, verified event types."""

    def __init__(
        self,
        coordinator: Any,
        watermark: HistoryWatermark,
        emit: Callable[[dict[str, Any]], None],
        *,
        camera_enabled: Callable[[str], bool] | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._watermark = watermark
        self._emit = emit
        self._camera_enabled = camera_enabled or (lambda _camera_id: False)

    async def async_poll(self) -> bool:
        """Poll page zero and emit unseen whitelisted events chronologically."""
        any_success = False
        place_ids: list[int] = []
        for subscriber_place in (self._coordinator.data or {}).get("places") or []:
            place_id = (subscriber_place.get("place") or {}).get("id")
            try:
                place_ids.append(int(place_id))
            except (TypeError, ValueError):
                continue
        if place_ids:
            try:
                page = await self._coordinator.api.query_events(place_ids, page=0)
            except Exception as ex:  # noqa: BLE001
                LOGGER.debug(
                    "General history fetch failed (%s)",
                    type(ex).__name__,
                )
            else:
                any_success = True
                by_source: dict[str, list[str]] = {}
                for event in page.events:
                    stream = _general_stream_key(event)
                    by_source.setdefault(stream, []).append(event.id)
                new_events = {
                    (stream, event_id)
                    for stream, event_ids in by_source.items()
                    for event_id in self._watermark.ingest(stream, event_ids)
                }
                for event in reversed(page.events):
                    mapped_type = map_general_event_type(event.event_type)
                    if (
                        (_general_stream_key(event), event.id) not in new_events
                        or mapped_type is None
                    ):
                        continue
                    self._emit(
                        {
                            "event_type": mapped_type,
                            "event_id": event.id,
                            "occurred_at": event.timestamp,
                            "place_id": event.place_id,
                            "source_type": event.source_type,
                            "source_id": event.source_id,
                        }
                    )

        upper = datetime.now(UTC).replace(microsecond=0)
        lower = upper - _CAMERA_LOOKBACK
        lower_date = lower.isoformat().replace("+00:00", "Z")
        upper_date = upper.isoformat().replace("+00:00", "Z")
        for camera in (self._coordinator.data or {}).get("cameras") or []:
            camera_id = camera.get("id")
            if not camera_id or camera.get("source") not in ("intercom", "public"):
                continue
            camera_id = str(camera_id)
            if not self._camera_enabled(camera_id):
                continue
            try:
                camera_events = await self._coordinator.api.query_camera_events(
                    camera_id,
                    lower_date=lower_date,
                    upper_date=upper_date,
                )
            except Exception as ex:  # noqa: BLE001
                LOGGER.debug(
                    "Camera history fetch failed for camera_id=%s (%s)",
                    camera_id,
                    type(ex).__name__,
                )
                continue
            any_success = True
            new_camera_ids = set(
                self._watermark.ingest(
                    f"camera:{camera_id}",
                    (event.id for event in camera_events),
                )
            )
            for event in reversed(camera_events):
                if (
                    event.id not in new_camera_ids
                    or event.event_subject_id != _CAMERA_MOTION_EVENT_SUBJECT_ID
                ):
                    continue
                self._emit(
                    {
                        "event_type": "motion",
                        "event_id": event.id,
                        "occurred_at": event.timestamp,
                        "camera_id": event.camera_id,
                        "duration": event.duration,
                        "recording_available": (
                            event.available and event.goto_enabled
                        ),
                    }
                )
        return any_success


class HistoryManager:
    """Own storage and timer lifecycle for one config entry's history poller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        coordinator: Any,
    ) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._store: Store[dict[str, Any]] = Store(
            hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.history.{entry_id}",
        )
        self._coordinator = coordinator
        self._watermark = HistoryWatermark(max_ids=_MAX_STORED_IDS)
        self._poller: HistoryPoller | None = None
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._poll_lock = asyncio.Lock()

    async def async_start(self) -> None:
        """Restore opaque IDs, establish a baseline, then schedule polling."""
        stored = await self._store.async_load()
        streams = (stored or {}).get("streams") or {}
        if not isinstance(streams, Mapping):
            streams = {}
        self._watermark = HistoryWatermark(
            streams,
            max_ids=_MAX_STORED_IDS,
        )
        self._poller = HistoryPoller(
            self._coordinator,
            self._watermark,
            lambda payload: async_dispatcher_send(
                self._hass,
                history_signal(self._entry_id),
                payload,
            ),
            camera_enabled=self._camera_enabled,
        )
        await self.async_poll()
        self._unsub_interval = async_track_time_interval(
            self._hass,
            self._async_interval,
            HISTORY_POLL_INTERVAL,
        )

    @callback
    def _camera_enabled(self, camera_id: str) -> bool:
        """Return whether this entry's motion-history entity is enabled."""
        registry = er.async_get(self._hass)
        entity_id = registry.async_get_entity_id(
            "event",
            DOMAIN,
            camera_history_unique_id(camera_id),
        )
        if entity_id is None:
            return False
        entry = registry.async_get(entity_id)
        return (
            entry is not None
            and entry.config_entry_id == self._entry_id
            and entry.disabled_by is None
        )

    async def async_poll(self) -> bool:
        """Run at most one poll and persist only bounded opaque event IDs."""
        if self._poller is None:
            return False
        if self._poll_lock.locked():
            LOGGER.debug("History poll skipped: previous poll still running")
            return False
        async with self._poll_lock:
            success = await self._poller.async_poll()
            if success:
                await self._store.async_save(
                    {"streams": self._watermark.as_dict()}
                )
            return success

    async def _async_interval(self, _now: datetime) -> None:
        """Handle one HA interval callback."""
        await self.async_poll()

    @callback
    def async_stop(self) -> None:
        """Cancel future polls on config-entry unload."""
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
