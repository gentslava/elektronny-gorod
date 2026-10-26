"""Native Media Source: forpost camera motion-event clips.

Browse: account entry → place → camera → day → events.
Resolve: one signed mp4 per event, fetched on demand and discarded;
an event still being recorded plays from its start as the operator archive
stream through HA Stream (HLS), falling back to the camera live view (A-124).
Opaque IDs only — signed URLs are never logged or persisted
(spec: docs/specs/2026-08-29-media-source-design.md).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components import media_source as ha_media_source
from homeassistant.components.camera import DynamicStreamSettings
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
from homeassistant.components.stream import HLS_PROVIDER, Stream, create_stream
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import translation
from homeassistant.util import dt as dt_util

from ._logging import UrlPathRedactFilter
from .clip_proxy import async_register_clip_view, clip_proxy_url
from .coordinator import async_get_coordinator
from .const import DOMAIN, LOGGER
from .history import place_display_name

_SOURCE_TITLE = "Электронный город"

_MIME_MP4 = "video/mp4"
_MIME_HLS_CAMERA = "application/vnd.apple.mpegurl"
# Единственный HLS-тип, который играет плеер медиабраузера HA (см.
# `_live_play_media`): им отдаются и эфир, и поток архива.
_MIME_HLS_FRONTEND = "application/x-mpegURL"

_CAMERA_SOURCES = ("intercom", "public")

_INTERCOM_RETENTION_DAYS = 14
_OTHER_RETENTION_DAYS = 7

_MOTION_EVENT_SUBJECT_ID = 126

# Событие считается идущим, пока его окончание `timestamp + duration` не
# ушло в прошлое дальше этого окна: оператор держит окончание идущей записи
# на несколько секунд впереди «сейчас» и сдвигает его, пока длится движение
# (A-124, прод 2026-10-26). Завершённые события не меняются.
_LIVE_GRACE_SEC = 15

# Потоки архива идущих событий: (entry_id, camera_id, event_id) → Stream.
# Живой поток переиспользуется повторным resolve; остановленный (idle HLS,
# отказ worker-а, выгрузка записи) выбрасывается — ссылка оператора выдаётся
# заново на каждый запрос, поэтому новый resolve берёт свежую.
_ARCHIVE_STREAMS_KEY = f"{DOMAIN}_archive_streams"
_ARCHIVE_LOCK_KEY = f"{DOMAIN}_archive_streams_lock"
# Логгер, в который HA Stream пишет источник потока с меткой `stream_label`
# (`homeassistant/components/stream/__init__.py`, `Stream.__init__`).
_STREAM_LOGGER_PREFIX = "homeassistant.components.stream.stream"

# EN-fallback для подписей событий (длительность, «идёт запись»);
# переопределяются категорией `common` translations (hass.config.language).
_DEFAULT_DURATION_LABELS = {
    "duration_min_sec": "{minutes} min {seconds} sec",
    "duration_min": "{minutes} min",
    "duration_sec": "{seconds} sec",
    "recording_in_progress": "Recording",
}


def _event_in_progress(event: Any, now_ts: float) -> bool:
    """Запись события ещё идёт: окончание позже, чем `now - grace`."""
    return event.timestamp + event.duration > now_ts - _LIVE_GRACE_SEC


def _tz_offset(timestamp: int) -> int:
    """Смещение часового пояса HA в момент `timestamp`, в секундах.

    Приложение шлёт в `TZ` смещение устройства (25200 для UTC+7); у нас
    устройство — это HA, и смещение берётся на время события (переход на
    летнее время меняет его).
    """
    offset = dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).utcoffset()
    return int(offset.total_seconds()) if offset is not None else 0


def _archive_streams(hass: HomeAssistant) -> dict[tuple[str, str, str], Stream]:
    return hass.data.setdefault(_ARCHIVE_STREAMS_KEY, {})


def _stream_alive(stream: Stream) -> bool:
    """Провайдер HLS снимается при остановке потока (`Stream.stop`)."""
    return HLS_PROVIDER in stream.outputs()


def _archive_stream_label(camera_id: str) -> str:
    """Метка потока для логгера HA Stream; фильтр ставится один раз.

    Метка на камеру, а не на событие: логгеры модуля `logging` живут до
    конца процесса, и метка на событие копила бы их без предела.
    """
    label = f"{DOMAIN}_archive_{camera_id}"
    stream_logger = logging.getLogger(f"{_STREAM_LOGGER_PREFIX}.{label}")
    if not any(
        isinstance(existing, UrlPathRedactFilter)
        for existing in stream_logger.filters
    ):
        stream_logger.addFilter(UrlPathRedactFilter())
    return label


async def async_stop_archive_streams(hass: HomeAssistant, entry_id: str) -> None:
    """Остановить потоки архива записи (выгрузка config entry)."""
    streams: dict[tuple[str, str, str], Stream] = (
        hass.data.get(_ARCHIVE_STREAMS_KEY) or {}
    )
    for key in [key for key in streams if key[0] == entry_id]:
        await streams.pop(key).stop()


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
    async_register_clip_view(hass)
    return ElektronnyGorodMediaSource(hass)


class ElektronnyGorodMediaSource(MediaSource):
    """Forpost camera archive: motion-event clips per day."""

    name = _SOURCE_TITLE

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self._hass = hass

    def _coordinator(self, entry_id: str) -> Any | None:
        return async_get_coordinator(self._hass, entry_id)

    # Возвращаем `BrowseMedia`, тогда как база объявляет `BrowseMediaSource`.
    # Ядро читает только поля `BrowseMedia`, поэтому рантайм корректен, но
    # контракт шире базового — сужение это отдельный рефакторинг (A-101).
    async def async_browse_media(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, item: MediaSourceItem
    ) -> BrowseMedia:
        identifier = item.identifier or ""
        if not identifier:
            return self._browse_root()
        parts = identifier.split("/")
        if len(parts) == 1:
            return self._browse_entry(parts[0])
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
        # Идущее событие у оператора — недописанный mp4 (A-123/A-124). Как в
        # приложении, играем его с начала потоком архива; не вышло — эфир
        # этой же камеры, без отката на клип.
        if _event_in_progress(event, dt_util.utcnow().timestamp()):
            play = await self._archive_play_media(
                coordinator, entry_id, camera_id, event
            )
            if play is not None:
                return play
            return await self._live_play_media(item, camera_id)
        # Завершённое событие — намеренно MP4 через прокси клипа, а не поток
        # архива: в медиабраузере конечный файл с перемоткой удобнее
        # бесконечного потока, и это то же содержимое, что «Скачать» в
        # приложении (A-124).
        # Ссылку у оператора не запрашиваем: каждый минт запускает
        # подготовку mp4 заново (снимок 2026-05-25 — 4 отказа 423 и ~11 с
        # ожидания), поэтому минт должен быть ровно один и живёт в прокси.
        # Доступность события уже проверена выше по данным самого события.
        return PlayMedia(
            url=clip_proxy_url(self._hass, entry_id, event_id),
            mime_type=_MIME_MP4,
        )

    async def _archive_play_media(
        self, coordinator: Any, entry_id: str, camera_id: str, event: Any
    ) -> PlayMedia | None:
        """Идущее событие с начала: поток архива оператора → HA Stream → HLS.

        `None` — поток недоступен (ссылки нет, stream не загружен, worker не
        стартовал); вызывающий открывает эфир. Подписанная ссылка уходит
        только в HA Stream: в логах, состоянии и ответе фронтенду её нет —
        фронтенд получает HLS-endpoint HA со своим токеном.
        """
        streams = _archive_streams(self._hass)
        key = (entry_id, camera_id, event.id)
        lock: asyncio.Lock = self._hass.data.setdefault(
            _ARCHIVE_LOCK_KEY, asyncio.Lock()
        )
        async with lock:
            for stale in [k for k, found in streams.items() if not _stream_alive(found)]:
                del streams[stale]
            stream = streams.get(key)
            if stream is None:
                stream = await self._create_archive_stream(
                    coordinator, camera_id, event
                )
                if stream is None:
                    return None
            try:
                stream.add_provider(HLS_PROVIDER)
                await stream.start()
                url = stream.endpoint_url(HLS_PROVIDER)
            except (HomeAssistantError, RuntimeError, ValueError) as ex:
                LOGGER.debug(
                    "Media source archive stream failed to start for "
                    "camera_id=%s event_id=%s (%s); live view",
                    camera_id,
                    event.id,
                    type(ex).__name__,
                )
                streams.pop(key, None)
                await stream.stop()
                return None
            streams[key] = stream
        return PlayMedia(url=url, mime_type=_MIME_HLS_FRONTEND)

    async def _create_archive_stream(
        self, coordinator: Any, camera_id: str, event: Any
    ) -> Stream | None:
        """Свежая ссылка архива с начала события → новый HA Stream."""
        source = await coordinator.api.query_camera_archive_stream(
            camera_id, event.timestamp, _tz_offset(event.timestamp)
        )
        if not source:
            LOGGER.debug(
                "Media source archive stream unavailable for camera_id=%s "
                "event_id=%s; live view",
                camera_id,
                event.id,
            )
            return None
        try:
            stream = create_stream(
                self._hass,
                source,
                options={},
                dynamic_stream_settings=DynamicStreamSettings(),
                stream_label=_archive_stream_label(camera_id),
            )
        except HomeAssistantError as ex:
            # Интеграция stream не загружена или отвергла параметры.
            LOGGER.debug(
                "Media source archive stream not created for camera_id=%s "
                "event_id=%s (%s); live view",
                camera_id,
                event.id,
                type(ex).__name__,
            )
            return None
        stream.set_update_callback(self._archive_stream_watchdog(stream))
        return stream

    def _archive_stream_watchdog(self, stream: Stream) -> Callable[[], None]:
        """Отказ worker-а — остановить поток, а не повторять его вечно.

        HA Stream повторяет тот же источник, пока жив провайдер, а idle-таймер
        HLS заводится только первым сегментом: поток с истёкшей ссылкой или
        вне срока хранения иначе жил бы до перезапуска HA и писал ошибку на
        каждом круге. Повтор и не нужен: оператор выдаёт новую ссылку на
        каждый запрос, и следующий resolve возьмёт свежую.
        """

        @callback
        def _on_state_change() -> None:
            if not stream.available:
                self._hass.async_create_task(
                    stream.stop(), name=f"{DOMAIN}_archive_stream_stop"
                )

        return _on_state_change

    async def _live_play_media(
        self, item: MediaSourceItem, camera_id: str
    ) -> PlayMedia:
        """Эфир камеры через штатный camera media source HA.

        Сущность ищется в entity registry по стабильному unique_id, как и в
        `_camera_visible`; разрешение потока делегируется
        `media-source://camera/<entity_id>`.
        """
        registry = er.async_get(self._hass)
        entity_id = registry.async_get_entity_id(
            "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}"
        )
        entry = registry.async_get(entity_id) if entity_id else None
        if entry is None or entry.disabled_by is not None:
            raise Unresolvable("Live view is not available")
        try:
            play = await ha_media_source.async_resolve_media(
                self._hass,
                ha_media_source.generate_media_source_id("camera", entry.entity_id),
                item.target_media_player,
            )
        except HomeAssistantError as ex:
            LOGGER.debug(
                "Media source live view failed for camera_id=%s (%s)",
                camera_id,
                type(ex).__name__,
            )
            raise Unresolvable("Live view is not available") from None
        # Плеер медиабраузера фронтенда HA (hui-dialog-web-browser-play-media)
        # включает HLS только для sourceType === "application/x-mpegURL";
        # camera media source отдаёт "application/vnd.apple.mpegurl", и
        # браузер показывает «тип мультимедиа не поддерживается».
        if play.mime_type.lower() == _MIME_HLS_CAMERA.lower():
            return PlayMedia(url=play.url, mime_type=_MIME_HLS_FRONTEND)
        return play

    def _browse_root(self) -> BrowseMedia:
        children: list[BrowseMedia] = []
        for entry in self._hass.config_entries.async_loaded_entries(DOMAIN):
            entry_id = entry.entry_id
            coordinator = entry.runtime_data
            if not self._place_ids(coordinator):
                continue
            children.append(
                self._folder(_uri(entry_id), entry.title)
            )
        children.sort(key=lambda child: child.title)
        return self._directory(_uri(), _SOURCE_TITLE, children)

    def _camera_visible(self, camera: dict[str, Any]) -> bool:
        """Скрытые камеры не попадают ни в browse, ни в resolve.

        Скрытие у оператора проверяется первым, потому что доступно всегда.
        Полагаться на один entity registry нельзя: записи может не быть, если
        камера появилась в аккаунте уже после setup или сущность удалили, —
        и тогда скрытая камера оказалась бы видна в архиве.
        """
        if camera.get("hidden"):
            return False
        camera_id = str(camera.get("id") or "")
        if not camera_id:
            return False
        registry = er.async_get(self._hass)
        entity_id = registry.async_get_entity_id(
            "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}"
        )
        if entity_id is None:
            # Сущность ещё не создана — скрытие у оператора уже проверено выше.
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
            if not camera_id or not self._camera_visible(camera):
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

    def _browse_entry(self, entry_id: str) -> BrowseMedia:
        coordinator = self._coordinator(entry_id)
        entry = self._hass.config_entries.async_get_entry(entry_id)
        if coordinator is None or entry is None:
            raise BrowseError("Unknown media item")
        children = [
            self._folder(
                _uri(f"{entry_id}/{place_id}"),
                place_display_name(coordinator.data, place_id),
            )
            for place_id in self._place_ids(coordinator)
        ]
        if not children:
            raise BrowseError("Unknown media item")
        return self._directory(_uri(entry_id), entry.title, children)

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
            if not self._camera_visible(camera):
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
        if coordinator is None:
            raise BrowseError("Unknown media item")
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
        labels = await self._duration_labels()
        now_ts = dt_util.utcnow().timestamp()
        children = [
            BrowseMedia(
                title=self._event_title(
                    event, labels, in_progress=_event_in_progress(event, now_ts)
                ),
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

    async def _duration_labels(self) -> dict[str, str]:
        """Duration unit labels per the HA instance language.

        Media-source browse carries no user locale, so titles follow
        `hass.config.language` via the integration's `common` translation
        category; missing translations fall back to English.
        """
        labels = dict(_DEFAULT_DURATION_LABELS)
        try:
            fetched = await translation.async_get_translations(
                self._hass, self._hass.config.language, "common", {DOMAIN}
            )
        except Exception:  # noqa: BLE001 - optional feature degradation
            fetched = {}
        for key in labels:
            value = fetched.get(f"component.{DOMAIN}.common.{key}")
            if value:
                labels[key] = value
        return labels

    @staticmethod
    def _event_title(
        event: Any, labels: dict[str, str], *, in_progress: bool = False
    ) -> str:
        local = dt_util.as_local(dt_util.utc_from_timestamp(event.timestamp))
        if in_progress:
            # Длительность идущей записи ещё растёт — вместо неё метка.
            return (
                f"● {labels['recording_in_progress']} · "
                f"{local.strftime('%H:%M:%S')}"
            )
        duration = int(event.duration)
        if duration >= 60:
            minutes, seconds = divmod(duration, 60)
            duration_label = (
                labels["duration_min_sec"].format(minutes=minutes, seconds=seconds)
                if seconds
                else labels["duration_min"].format(minutes=minutes)
            )
        else:
            duration_label = labels["duration_sec"].format(seconds=duration)
        return f"{local.strftime('%H:%M:%S')} · {duration_label}"

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
