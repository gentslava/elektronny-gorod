"""Camera entity — CoordinatorEntity-based.

См. ADR-0002. Slice 3b: camera использует coordinator.data для availability.
Stream / snapshot — on-demand actions (не кэшируются в coordinator.data).

Closes A-44: `async_update` удалён, дублирующий `get_camera_stream`-запрос
тоже. Stream URL получается лениво в `stream_source()`.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AREA_INTERCOM,
    AREA_INDOOR_CAM,
    AREA_PUBLIC_CAM,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_USE_GO2RTC,
    DOMAIN,
    GO2RTC_RTSP_PORT,
    LOGGER,
)
from .coordinator import ElektronnyGorodUpdateCoordinator

# A-69: TTL для cached stream URL в `Camera._fetch_stream_source_impl`.
# Sequential calls в пределах TTL hit cache → 0 HTTP к operator + 0 PUT в
# go2rtc + 0 `Stream.update_source()` restart (т.к. src == _last_src).
# TTL подобран короче operator session token TTL (~минуты) — URL всегда живой.
# Покрывает sequential batches (HA Stream retry, Frigate prefetch с
# интервалом 0.5-30 сек), которые A-68 future-pattern не ловит (overlap
# окно слишком короткое).
_STREAM_URL_TTL_SECONDS = 30


def _build_go2rtc_src(source_url: str) -> str:
    # Video copy, audio -> AAC/OPUS (go2rtc will then output to WebRTC/HLS as needed)
    return f"ffmpeg:{source_url}#video=copy#audio=aac#audio=opus"


async def _go2rtc_upsert_stream(
    session: ClientSession,
    base_url: str,
    stream_name: str,
    src: str,
    headers: dict | None = None,
) -> None:
    qs = urlencode({"name": stream_name, "src": src})
    put_url = f"{base_url}/api/streams?{qs}"
    try:
        async with session.put(put_url, headers=headers or {}) as resp:
            if resp.status in (200, 201, 204):
                return
    except ClientError:
        # PATCH
        pass

    patch_url = f"{base_url}/api/streams?{qs}"
    async with session.patch(patch_url, headers=headers or {}) as resp:
        if resp.status >= 400:
            body = await resp.text()
            raise RuntimeError(f"go2rtc PATCH failed: {resp.status} {body}")


def _get_go2rtc_cfg(
    entry: ConfigEntry,
) -> tuple[bool, str | None, str | None, str | None, str | None]:
    use_go2rtc = (
        entry.options.get(CONF_USE_GO2RTC)
        if CONF_USE_GO2RTC in entry.options
        else entry.data.get(CONF_USE_GO2RTC, False)
    )
    base_url = entry.options.get(CONF_GO2RTC_BASE_URL) or entry.data.get(CONF_GO2RTC_BASE_URL)
    rtsp_host = entry.options.get(CONF_GO2RTC_RTSP_HOST) or entry.data.get(CONF_GO2RTC_RTSP_HOST)
    go2rtc_username = entry.options.get(CONF_GO2RTC_USERNAME) or entry.data.get(CONF_GO2RTC_USERNAME)
    go2rtc_password = entry.options.get(CONF_GO2RTC_PASSWORD) or entry.data.get(CONF_GO2RTC_PASSWORD)
    return bool(use_go2rtc), base_url, rtsp_host, go2rtc_username, go2rtc_password


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Camera based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    cameras = (coordinator.data or {}).get("cameras") or []

    use_go2rtc, base_url, rtsp_host, go2rtc_username, go2rtc_password = _get_go2rtc_cfg(entry)

    async_add_entities(
        ElektronnyGorodCamera(
            coordinator,
            camera_info,
            use_go2rtc=use_go2rtc,
            go2rtc_base_url=base_url,
            go2rtc_rtsp_host=rtsp_host,
            go2rtc_username=go2rtc_username,
            go2rtc_password=go2rtc_password,
        )
        for camera_info in cameras
    )


class ElektronnyGorodCamera(
    CoordinatorEntity[ElektronnyGorodUpdateCoordinator], Camera
):
    """Camera entity (CoordinatorEntity).

    Slice 3c (Bronze polish):
    - Стабильный `unique_id = f"{DOMAIN}_camera_{camera_id}"` (без `name`,
      см. ADR-0002, A-12). Миграция старого формата `{id}_{name}` — в
      `async_setup_entry` через `er.async_migrate_entries`.
    - `_attr_has_entity_name = True` + `_attr_name = None`: camera как
      самостоятельный device, имя берётся из `device_info.name`.
    """

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ElektronnyGorodUpdateCoordinator,
        camera_info: dict[str, Any],
        *,
        use_go2rtc: bool,
        go2rtc_base_url: str | None,
        go2rtc_rtsp_host: str | None,
        go2rtc_username: str | None = None,
        go2rtc_password: str | None = None,
    ) -> None:
        # Camera.__init__ инициализирует Entity-state; затем регистрируемся в coordinator.
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

        self._id: str = camera_info.get("id") or ""
        self._name: str = camera_info.get("name") or self._id

        # Intercom-камеры (от entrances в access_controls) имеют place_id +
        # access_control_id + entrance_id и разделяют device с lock того же
        # entrance. Public/place-cameras без этих полей → standalone devices.
        ac_id = camera_info.get("access_control_id")
        place_id = camera_info.get("place_id")
        entrance_id = camera_info.get("entrance_id")
        source = camera_info.get("source") or "public"  # fallback
        is_intercom = source == "intercom" and bool(ac_id and place_id)

        # Visibility управляется на DEVICE-уровне в __init__.py:_sync_visibility:
        # если все entities device hidden в API → device.disabled_by=INTEGRATION,
        # HA автоматически set entity.disabled_by=DEVICE (cascade).
        LOGGER.debug("Camera init id=%s source=%s hidden=%s",
                     self._id, source, camera_info.get("hidden"))

        self._last_src: str | None = None
        # A-65: counter consecutive empty stream URL responses для лог-throttling.
        # 1й fail → WARNING, 2й+ подряд → DEBUG, reset на первый success.
        self._consecutive_empty_count: int = 0
        # A-68: in-flight future для dedup concurrent stream_source() calls.
        # HA Stream worker + Frigate + Lovelace могут одновременно дёргать
        # stream_source — без dedup это создаёт N HTTP к operator + N PUT в
        # go2rtc + N `Stream.update_source()` restart → «мигание видео».
        self._inflight_stream_future: asyncio.Future[str | None] | None = None
        # A-69: TTL cache stream URL для sequential batches (HA Stream retry,
        # Frigate prefetch с интервалом 0.5-30 сек). См. `_STREAM_URL_TTL_SECONDS`.
        self._cached_stream_url: str | None = None
        self._cached_stream_ts: float = 0.0
        self._image: bytes | None = None
        self._attr_unique_id = f"{DOMAIN}_camera_{self._id}"
        if is_intercom:
            device_uid = f"entrance_{place_id}_{ac_id}_{entrance_id or 'main'}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_uid)},
                name=self._name,
                manufacturer="Электронный город",
                model="Intercom",
                suggested_area=AREA_INTERCOM,
                via_device=(DOMAIN, f"place_{place_id}"),
            )
        else:
            # source="place" — личные подписочные камеры из /rest/v1/.../cameras
            # (юзер их купил отдельно). source="public" — всё из
            # /rest/v2/.../public/cameras (общедомовые + городские, API не
            # разделяет; юзер может скрыть конкретные через app — см. `hidden`).
            if source == "place":
                model = "Indoor Camera"
                area = AREA_INDOOR_CAM
            else:
                model = "Public Camera"
                area = AREA_PUBLIC_CAM
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"camera_{self._id}")},
                name=self._name,
                manufacturer="Электронный город",
                model=model,
                suggested_area=area,
            )

        self._go2rtc_base_url = go2rtc_base_url
        self._go2rtc_rtsp_host = go2rtc_rtsp_host
        self._use_go2rtc = use_go2rtc
        self._go2rtc_stream_name = f"eg_{self._id}"
        self._go2rtc_username = go2rtc_username
        self._go2rtc_password = go2rtc_password

    @property
    def _coordinator_camera_info(self) -> dict[str, Any] | None:
        """Найти текущую запись camera в coordinator.data."""
        cameras = (self.coordinator.data or {}).get("cameras") or []
        for cam in cameras:
            if cam.get("id") == self._id:
                return cam
        return None

    @property
    def available(self) -> bool:
        """Доступна, если camera найдена в последнем refresh coordinator."""
        return super().available and self._coordinator_camera_info is not None

    # ------------------------------------------------------------------ #
    # go2rtc                                                             #
    # ------------------------------------------------------------------ #

    def _rtsp_url(self) -> str:
        if not self._go2rtc_rtsp_host:
            raise RuntimeError("go2rtc rtsp host is not configured")
        return (
            f"rtsp://{self._go2rtc_rtsp_host}:{GO2RTC_RTSP_PORT}/"
            f"{self._go2rtc_stream_name}"
        )

    async def _ensure_go2rtc_stream(self, source_url: str) -> None:
        if not self._use_go2rtc:
            return

        base_url = self._go2rtc_base_url
        if not base_url:
            LOGGER.debug("go2rtc enabled but base_url missing; falling back to direct FLV")
            self._use_go2rtc = False
            return

        src = _build_go2rtc_src(source_url)
        if src == self._last_src:
            return

        session: ClientSession = async_get_clientsession(self.hass)
        headers: dict[str, str] = {}
        if self._go2rtc_username and self._go2rtc_password:
            userpass = f"{self._go2rtc_username}:{self._go2rtc_password}"
            b64 = base64.b64encode(userpass.encode()).decode()
            headers["Authorization"] = f"Basic {b64}"
        try:
            await _go2rtc_upsert_stream(
                session=session,
                base_url=base_url,
                stream_name=self._go2rtc_stream_name,
                src=src,
                headers=headers,
            )
        except Exception:  # noqa: BLE001 — defensive: go2rtc PUT может fail
            # A-70: PUT failure → invalidate cache чтобы next call сделал
            # fresh fetch + fresh PUT (faster recovery, не ждём TTL expire).
            self._cached_stream_url = None
            LOGGER.exception(
                "go2rtc PUT failed for %s (%s) — cache invalidated",
                self._name, self._id,
            )
            raise
        self._last_src = src

        LOGGER.debug(
            "go2rtc stream updated: name=%s rtsp=%s",
            self._go2rtc_stream_name,
            self._rtsp_url(),
        )
        # A-66 partial revert: `stream.update_source()` forced restart УБРАН.
        # Каждый PUT приводил к interruption видео ~1-2 сек. Operator выдаёт
        # unique token на каждый запрос → cache miss = inevitable PUT, что
        # значило restart каждые 30-60s (A-69 cache TTL) = постоянное «мигание»
        # (production-лог 2026-05-27). HA Stream lifecycle сам обрабатывает
        # producer failure: при stale token go2rtc producer fail → HA Stream
        # worker `Invalid data` → backoff retry → fresh stream_source →
        # fresh PUT → reconnect. Lag 10-30s после рare token expire vs
        # continuous «мигание» — приемлемый trade-off.

    # ------------------------------------------------------------------ #
    # On-demand actions                                                  #
    # ------------------------------------------------------------------ #

    def _is_hidden(self) -> bool:
        """A-63 (PARTIAL): skip только для snapshot, НЕ для stream_source.

        Используется ТОЛЬКО в `async_camera_image` — snapshot on-demand,
        lifecycle проблем нет, skip безопасен.

        Для `stream_source` skip убран (см. A-66v3): HA Stream worker pin-ится
        к RTSP URL который мы вернули один раз; `stream_source` повторно не
        вызывается. Если мы возвращаем None после того как stream была
        активна, worker зависает в retry-loop на устаревшем RTSP/producer.
        Лучше всегда возвращать живой URL + полагаться на HA prefetch для
        обновления go2rtc producer + Stream.update_source() для force restart
        при изменении src в go2rtc.
        """
        reg = self.registry_entry
        return reg is not None and reg.hidden_by is not None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if self._is_hidden() or not self.available:
            return None
        image = await self.coordinator.get_camera_snapshot(self._id, width, height)
        if image:
            self._image = image
        return self._image

    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        НЕ skip-аем для hidden (см. A-66v3). HA Stream lifecycle несовместим
        с возвратом None после того как stream была активна — worker зависает.

        A-68: dedup concurrent calls через future-pattern. HA Stream worker +
        Frigate + Lovelace могут одновременно дёргать stream_source — без
        dedup создаётся N HTTP к operator + N PUT в go2rtc + N
        `Stream.update_source()` restart, что приводит к «миганию видео».
        Concurrent callers wait first in-flight future → получают одинаковый
        результат → 1 HTTP + 1 PUT + 1 restart.
        """
        if self._inflight_stream_future is not None:
            return await self._inflight_stream_future
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str | None] = loop.create_future()
        self._inflight_stream_future = fut
        try:
            result = await self._fetch_stream_source_impl()
            if not fut.done():
                fut.set_result(result)
            return result
        except BaseException as exc:
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            # Safety net: если future остался unresolved (например, exception
            # пробросился до set_result/set_exception, или task cancelled
            # между присваиванием _inflight_stream_future и try) — cancel-нём
            # его, чтобы waiters не зависли навсегда.
            if not fut.done():
                fut.cancel()
            self._inflight_stream_future = None

    async def _fetch_stream_source_impl(self) -> str | None:
        """Реальная логика fetch — operator stream URL + go2rtc PUT.

        Вызывается из `stream_source` под защитой in-flight future (A-68).
        """
        # A-69: TTL cache — sequential calls в пределах TTL возвращают
        # cached URL без HTTP. Дополняет A-68 (future dedup для overlap)
        # для случая sequential batch через 0.5-30 сек (HA Stream retry,
        # Frigate prefetch). Failure НЕ кэшируется (cache update только
        # после `if not stream_url: return None`).
        now = time.monotonic()
        if (
            self._cached_stream_url is not None
            and now - self._cached_stream_ts < _STREAM_URL_TTL_SECONDS
        ):
            stream_url: str | None = self._cached_stream_url
        else:
            stream_url = await self.coordinator.get_camera_stream(self._id)
            if not stream_url:
                # A-65: log throttling — 1й fail в серии WARNING, 2й+ DEBUG.
                # Counter сбрасывается при первом успешном response.
                self._consecutive_empty_count += 1
                level = (
                    logging.WARNING if self._consecutive_empty_count == 1
                    else logging.DEBUG
                )
                LOGGER.log(
                    level,
                    "Camera %s (%s): empty source stream url",
                    self._name, self._id,
                )
                return None
            self._cached_stream_url = stream_url
            self._cached_stream_ts = now
        self._consecutive_empty_count = 0
        if not self._use_go2rtc:
            return stream_url
        await self._ensure_go2rtc_stream(stream_url)
        return self._rtsp_url()

    # ------------------------------------------------------------------ #
    # Coordinator hook                                                   #
    # ------------------------------------------------------------------ #

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coordinator refresh — actuality берётся из property `available`."""
        self.async_write_ha_state()
