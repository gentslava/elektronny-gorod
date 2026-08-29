"""Native Media Source: forpost camera motion-event clips.

Browse: account entry → place → camera → day → events.
Resolve: one signed mp4 per event, fetched on demand and discarded.
Opaque IDs only — signed URLs are never logged or persisted
(spec: docs/specs/2026-08-29-media-source-design.md).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .api import ForpostDownloadError
from .const import DOMAIN, LOGGER
from .history import place_display_name

_SOURCE_TITLE = "Электронный город"

_MIME_MP4 = "video/mp4"

_CAMERA_SOURCES = ("intercom", "public")

_INTERCOM_RETENTION_DAYS = 14
_OTHER_RETENTION_DAYS = 7

_MOTION_EVENT_SUBJECT_ID = 126


def _recent_days(count: int) -> list[date]:
    today = dt_util.now().date()
    return [today - timedelta(days=offset) for offset in range(count)]


def _day_bounds(day: date) -> tuple[str, str]:
    """Local-midnight ISO-Z bounds of a day (lower inclusive, upper not)."""
    day_start = dt_util.start_of_local_day(day)
    lower = dt_util.as_utc(day_start).isoformat().replace("+00:00", "Z")
    upper = (
        dt_util.as_utc(day_start + timedelta(days=1))
        .isoformat()
        .replace("+00:00", "Z")
    )
    return lower, upper


def _uri(identifier: str = "") -> str:
    """Build the media-source URI for one opaque identifier path."""
    if not identifier:
        return f"media-source://{DOMAIN}"
    return f"media-source://{DOMAIN}/{identifier}"


async def async_get_media_source(hass: HomeAssistant) -> ElektronnyGorodMediaSource:
    """Register the Elektronny Gorod archive as a HA media source."""
    return ElektronnyGorodMediaSource(hass)


class ElektronnyGorodMediaSource(MediaSource):
    """Forpost camera archive: motion-event clips per day."""

    name = _SOURCE_TITLE

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self._hass = hass

    def _coordinator(self, entry_id: str) -> Any | None:
        return (self._hass.data.get(DOMAIN) or {}).get(entry_id)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMedia:
        identifier = item.identifier or ""
        if not identifier:
            return self._browse_root()
        parts = identifier.split("/")
        if len(parts) == 2:
            return self._browse_place(*parts)
        if len(parts) == 3:
            return self._browse_camera(*parts)
        if len(parts) == 4:
            return await self._browse_day(*parts)
        raise BrowseError("Unknown media item")

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        parts = (item.identifier or "").split("/")
        if len(parts) != 5:
            raise Unresolvable("Unknown media item")
        entry_id, place_id, camera_id, day_str, event_id = parts
        # event_id входит в URL запроса к оператору, day_str — в окно поиска:
        # принимаем только цифры/валидную дату (закрывает path/query-инъекции).
        if not event_id.isdigit():
            raise Unresolvable("Unknown media item")
        if len(day_str) != 8 or not day_str.isdigit():
            raise Unresolvable("Unknown media item")
        try:
            day = datetime.strptime(day_str, "%Y%m%d").date()
        except ValueError as err:
            raise Unresolvable("Unknown media item") from err
        coordinator = self._coordinator(entry_id)
        if coordinator is None or self._camera(
            entry_id, place_id, camera_id
        ) is None:
            raise Unresolvable("Unknown media item")
        # Привязка события к гейтируемой камере: client-supplied event_id сам
        # по себе не авторизует доступ — событие должно найтись среди событий
        # этой камеры за этот день и быть играемым (spec: "in browse and in
        # resolve"). Каждый play ре-резолвит события, как и ссылку.
        lower, upper = _day_bounds(day)
        try:
            events = await coordinator.api.query_camera_events(
                camera_id, lower_date=lower, upper_date=upper
            )
        except Exception as ex:  # noqa: BLE001 - operator boundary
            LOGGER.debug(
                "Media source resolve failed for camera_id=%s event_id=%s (%s)",
                camera_id,
                event_id,
                type(ex).__name__,
            )
            raise Unresolvable("Archive is temporarily unavailable") from None
        event = next(
            (found for found in events if found.id == event_id), None
        )
        if (
            event is None
            or event.event_subject_id != _MOTION_EVENT_SUBJECT_ID
            or not (event.available and event.goto_enabled)
        ):
            raise Unresolvable("Recording is not available")
        try:
            url = await coordinator.api.query_event_download(event_id)
        except ForpostDownloadError as err:
            if err.error_code == "11005":
                raise Unresolvable(
                    "Archive is outside the retention window"
                ) from err
            raise Unresolvable("Recording is not available") from err
        except Exception as ex:  # noqa: BLE001 - operator boundary
            LOGGER.debug(
                "Media source resolve failed for camera_id=%s event_id=%s (%s)",
                camera_id,
                event_id,
                type(ex).__name__,
            )
            raise Unresolvable("Archive is temporarily unavailable") from None
        return PlayMedia(url=url, mime_type=_MIME_MP4)

    def _browse_root(self) -> BrowseMedia:
        children: list[BrowseMedia] = []
        for entry_id, coordinator in (self._hass.data.get(DOMAIN) or {}).items():
            entry = self._hass.config_entries.async_get_entry(entry_id)
            if entry is None or not self._place_ids(coordinator):
                continue
            children.append(
                self._folder(_uri(entry_id), entry.title)
            )
        children.sort(key=lambda child: child.title)
        return self._directory(_uri(), _SOURCE_TITLE, children)

    def _camera_visible(self, camera_id: str) -> bool:
        registry = er.async_get(self._hass)
        entity_id = registry.async_get_entity_id(
            "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}"
        )
        if entity_id is None:
            return True
        entry = registry.async_get(entity_id)
        return entry is None or entry.hidden_by is None

    def _place_cameras(self, coordinator: Any, place_id: str) -> list[dict]:
        cameras: list[dict] = []
        for camera in (coordinator.data or {}).get("cameras") or []:
            if camera.get("source") not in _CAMERA_SOURCES:
                continue
            if str(camera.get("place_id") or "") != place_id:
                continue
            camera_id = str(camera.get("id") or "")
            if not camera_id or not self._camera_visible(camera_id):
                continue
            cameras.append(camera)
        return cameras

    def _place_ids(self, coordinator: Any) -> list[str]:
        place_ids: list[str] = []
        for subscriber_place in (coordinator.data or {}).get("places") or []:
            place_id = str((subscriber_place.get("place") or {}).get("id") or "")
            if place_id and self._place_cameras(coordinator, place_id):
                place_ids.append(place_id)
        return place_ids

    def _browse_place(self, entry_id: str, place_id: str) -> BrowseMedia:
        coordinator = self._coordinator(entry_id)
        if coordinator is None:
            raise BrowseError("Unknown media item")
        cameras = self._place_cameras(coordinator, place_id)
        if not cameras:
            raise BrowseError("Unknown media item")
        children = [
            self._folder(
                _uri(f"{entry_id}/{place_id}/{camera_id}"),
                str(camera.get("name") or camera_id),
            )
            for camera in cameras
            if (camera_id := str(camera.get("id") or ""))
        ]
        return self._directory(
            _uri(f"{entry_id}/{place_id}"),
            place_display_name(coordinator.data, place_id),
            children,
        )

    def _camera(
        self, entry_id: str, place_id: str, camera_id: str
    ) -> dict[str, Any] | None:
        coordinator = self._coordinator(entry_id)
        if coordinator is None:
            return None
        for camera in (coordinator.data or {}).get("cameras") or []:
            if camera.get("source") not in _CAMERA_SOURCES:
                continue
            if str(camera.get("id") or "") != camera_id:
                continue
            if str(camera.get("place_id") or "") != place_id:
                continue
            if not self._camera_visible(camera_id):
                return None
            return camera
        return None

    def _browse_camera(
        self, entry_id: str, place_id: str, camera_id: str
    ) -> BrowseMedia:
        camera = self._camera(entry_id, place_id, camera_id)
        if camera is None:
            raise BrowseError("Unknown media item")
        retention = (
            _INTERCOM_RETENTION_DAYS
            if camera.get("source") == "intercom"
            else _OTHER_RETENTION_DAYS
        )
        base = f"{entry_id}/{place_id}/{camera_id}"
        children = [
            self._folder(
                _uri(f"{base}/{day.strftime('%Y%m%d')}"),
                day.isoformat(),
                children_media_class=MediaClass.VIDEO,
            )
            for day in _recent_days(retention)
        ]
        return self._directory(
            _uri(base), str(camera.get("name") or camera_id), children
        )

    async def _browse_day(
        self, entry_id: str, place_id: str, camera_id: str, day_str: str
    ) -> BrowseMedia:
        camera = self._camera(entry_id, place_id, camera_id)
        if camera is None or len(day_str) != 8 or not day_str.isdigit():
            raise BrowseError("Unknown media item")
        try:
            day = datetime.strptime(day_str, "%Y%m%d").date()
        except ValueError as err:
            raise BrowseError("Unknown media item") from err
        coordinator = self._coordinator(entry_id)
        lower, upper = _day_bounds(day)
        try:
            events = await coordinator.api.query_camera_events(
                camera_id, lower_date=lower, upper_date=upper
            )
        except Exception as ex:  # noqa: BLE001 - operator boundary
            LOGGER.debug(
                "Media source day browse failed for camera_id=%s (%s)",
                camera_id,
                type(ex).__name__,
            )
            raise BrowseError("Archive is temporarily unavailable") from None
        base = f"{entry_id}/{place_id}/{camera_id}/{day_str}"
        children = [
            BrowseMedia(
                title=self._event_title(event),
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                media_content_id=_uri(f"{base}/{event.id}"),
                can_play=bool(event.available and event.goto_enabled),
                can_expand=False,
            )
            for event in events
            if event.event_subject_id == _MOTION_EVENT_SUBJECT_ID
        ]
        return self._directory(_uri(base), day.isoformat(), children)

    @staticmethod
    def _event_title(event: Any) -> str:
        local = dt_util.as_local(dt_util.utc_from_timestamp(event.timestamp))
        return f"{local.strftime('%H:%M:%S')} · {event.duration}s"

    @staticmethod
    def _folder(
        identifier: str,
        title: str,
        *,
        children_media_class: MediaClass = MediaClass.DIRECTORY,
    ) -> BrowseMedia:
        return BrowseMedia(
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            media_content_id=identifier,
            can_play=False,
            can_expand=True,
            children_media_class=children_media_class,
        )

    @staticmethod
    def _directory(
        identifier: str,
        title: str,
        children: list[BrowseMedia],
    ) -> BrowseMedia:
        return BrowseMedia(
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            media_content_id=identifier,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=(
                children[0].media_class if children else MediaClass.DIRECTORY
            ),
        )
