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
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientError, ClientTimeout

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
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

if TYPE_CHECKING:
    from homeassistant.components.stream import Stream

# A-71 / ADR-0009: минимальный интервал между авто-recovery попытками.
# HA Stream worker сигналит unavailable на каждый retry-tick (10/20/30с);
# без cooldown re-fetch забивал бы operator API. См. ADR-0009.
STREAM_RECOVERY_COOLDOWN = 30.0

# A-71 v2 / ADR-0009: интервал poll'а go2rtc producer-health для
# go2rtc/WebRTC-only пути (камеры без legacy HA Stream worker — напр. лифты).
# Живой forpost-поток шлёт ~150 КБ/с; `bytes_recv`, замороженный за интервал
# при наличии consumers → producer мёртв (operator session EOF) → recovery.
GO2RTC_HEALTH_POLL_INTERVAL = timedelta(seconds=30)


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
        # A-71: monotonic-метка последней авто-recovery (throttle, см. ADR-0009).
        self._last_recovery_monotonic: float = 0.0
        # A-71 v2: go2rtc producer-health poll (go2rtc/WebRTC-only путь, лифты).
        # baseline `bytes_recv` с прошлого опроса + unsub таймера.
        self._go2rtc_last_bytes_recv: int | None = None
        self._unsub_health_poll: CALLBACK_TYPE | None = None
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

    def _go2rtc_auth_headers(self) -> dict[str, str]:
        """Basic-auth заголовок для go2rtc API (если заданы creds)."""
        headers: dict[str, str] = {}
        if self._go2rtc_username and self._go2rtc_password:
            userpass = f"{self._go2rtc_username}:{self._go2rtc_password}"
            b64 = base64.b64encode(userpass.encode()).decode()
            headers["Authorization"] = f"Basic {b64}"
        return headers

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
        await _go2rtc_upsert_stream(
            session=session,
            base_url=base_url,
            stream_name=self._go2rtc_stream_name,
            src=src,
            headers=self._go2rtc_auth_headers(),
        )
        self._last_src = src

        LOGGER.debug(
            "go2rtc stream updated: name=%s rtsp=%s",
            self._go2rtc_stream_name,
            self._rtsp_url(),
        )

        # A-66v3: если HA Stream worker уже running — force restart, чтобы
        # новый ffmpeg producer (с свежим operator src) активировался немедленно.
        # Без этого worker продолжает старое подключение, при истечении operator
        # токена впадает в retry-with-backoff (10-60 сек).
        # `update_source()` устанавливает `_fast_restart_once=True` +
        # `_thread_quit.set()` (см. homeassistant.components.stream).
        stream = self.stream
        if stream is not None:
            try:
                stream.update_source(self._rtsp_url())
                LOGGER.debug(
                    "Camera %s (%s): forced HA Stream restart after go2rtc PUT",
                    self._name, self._id,
                )
            except Exception:  # noqa: BLE001 — defensive: HA Stream API edge cases
                LOGGER.exception(
                    "Failed to update HA Stream source for camera %s (%s)",
                    self._name, self._id,
                )

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

    # ------------------------------------------------------------------ #
    # Stream auto-recovery (A-71 / ADR-0009)                             #
    # ------------------------------------------------------------------ #

    async def async_create_stream(self) -> "Stream | None":
        """Создать HA Stream и обернуть update-callback для auto-recovery.

        Базовый `Camera` вешает `stream.set_update_callback(async_write_ha_state)`.
        Мы оборачиваем callback своим `_on_stream_state_change`: сохраняем
        `async_write_ha_state` + детектим переход stream в unavailable (operator
        session истекла, ~30 мин — A-71) → throttled re-fetch свежего URL.
        """
        stream = await super().async_create_stream()
        if stream is not None:
            stream.set_update_callback(self._on_stream_state_change)
        return stream

    @callback
    def _on_stream_state_change(self) -> None:
        """Wrapped HA Stream update-callback (A-71).

        HA Stream worker зовёт это при смене availability (`_set_state`).
        Сохраняем штатный `async_write_ha_state`; при отказе worker'а
        (`available == False`) планируем throttled recovery.
        """
        self.async_write_ha_state()
        stream = self.stream
        if stream is not None and not stream.available:
            self._maybe_schedule_stream_recovery()

    @callback
    def _maybe_schedule_stream_recovery(self) -> None:
        """Запланировать recovery, если прошёл cooldown (защита от шторма)."""
        now = time.monotonic()
        if now - self._last_recovery_monotonic < STREAM_RECOVERY_COOLDOWN:
            return
        self._last_recovery_monotonic = now
        # Background task — авто-отмена при HA shutdown; не держит unload.
        self.hass.async_create_background_task(
            self._async_recover_stream(),
            name=f"{DOMAIN}_stream_recovery_{self._id}",
        )

    async def _async_recover_stream(self) -> None:
        """Re-fetch свежий operator URL + перенаправить источник (A-71).

        Вызывается когда HA Stream worker сигналит unavailable (operator
        forpost session истекла, ~30 мин — см. ADR-0009). Делает те же вызовы,
        что HA на WebRTC re-offer / пользователь при reopen карточки:
        fresh `stream_source` → `_ensure_go2rtc_stream` (PATCH go2rtc +
        `Stream.update_source()`, A-66) либо прямой `update_source` без go2rtc.
        """
        # `available` здесь = ElektronnyGorodCamera.available, т.е.
        # `CoordinatorEntity.available` (coordinator.last_update_success) И
        # наличие камеры в coordinator.data. Это guard «не восстанавливать,
        # если координатор down или камера выпала из снапшота» — НЕ проверка
        # stream-availability (она перекрыта CoordinatorEntity.available).
        if not self.available:
            return
        try:
            stream_url = await self.coordinator.get_camera_stream(self._id)
        except Exception:  # noqa: BLE001 — defensive: не валим callback-цепочку
            LOGGER.exception(
                "Camera %s (%s): stream recovery fetch failed",
                self._name, self._id,
            )
            return
        if not stream_url:
            LOGGER.debug(
                "Camera %s (%s): stream recovery got empty url — skip",
                self._name, self._id,
            )
            return
        LOGGER.debug(
            "Camera %s (%s): auto-recovery — refreshing stalled stream",
            self._name, self._id,
        )
        if self._use_go2rtc:
            await self._ensure_go2rtc_stream(stream_url)
        elif self.stream is not None:
            self.stream.update_source(stream_url)

    # ------------------------------------------------------------------ #
    # go2rtc producer-health poll (A-71 v2 / ADR-0009)                   #
    # ------------------------------------------------------------------ #

    async def async_added_to_hass(self) -> None:
        """Подписка на coordinator + (для go2rtc) запуск producer-health poll.

        Event-driven recovery (`_on_stream_state_change`) ловит только camera с
        активным legacy HA Stream worker (домофоны). go2rtc/WebRTC-only camera
        (напр. лифты) такого сигнала не дают — для них poll'им go2rtc producer.
        """
        await super().async_added_to_hass()
        if (
            self._use_go2rtc
            and self._go2rtc_base_url
            and self._unsub_health_poll is None  # idempotent: не плодим таймеры
        ):
            self._unsub_health_poll = async_track_time_interval(
                self.hass,
                self._async_poll_go2rtc_health,
                GO2RTC_HEALTH_POLL_INTERVAL,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Снять health-poll таймер при удалении entity."""
        if self._unsub_health_poll is not None:
            self._unsub_health_poll()
            self._unsub_health_poll = None
        await super().async_will_remove_from_hass()

    async def _fetch_go2rtc_stream_info(
        self,
    ) -> tuple[list[dict[str, Any]], Any] | None:
        """GET go2rtc `/api/streams?src=<name>` → `(producers, consumers)`.

        Возвращает None при сетевой ошибке / не-200 / не-JSON (graceful).
        """
        base_url = self._go2rtc_base_url
        if not base_url:
            return None
        session = async_get_clientsession(self.hass)
        url = f"{base_url}/api/streams?{urlencode({'src': self._go2rtc_stream_name})}"
        try:
            async with session.get(
                url,
                headers=self._go2rtc_auth_headers(),
                timeout=ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except (ClientError, asyncio.TimeoutError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return data.get("producers") or [], data.get("consumers")

    async def _async_poll_go2rtc_health(self, now: datetime | None = None) -> None:
        """Детект stall по go2rtc producer `bytes_recv` (A-71 v2).

        Живой forpost-producer непрерывно принимает байты. Если `bytes_recv` не
        изменился с прошлого опроса **при наличии consumers** — producer мёртв
        (operator session EOF), но go2rtc держит stale-producer → запускаем тот
        же throttled recovery, что и event-driven путь. Покрывает камеры без
        legacy HA Stream worker (go2rtc/WebRTC-only, напр. лифты).
        """
        # `available` тут = координатор жив И камера в coordinator.data
        # (CoordinatorEntity.available перекрывает Camera stream-check) —
        # guard «координатор down → не дёргаем», НЕ проверка живости потока.
        if not self.available:
            return
        info = await self._fetch_go2rtc_stream_info()
        if info is None:
            return
        producers, consumers = info
        n_consumers = len(consumers) if isinstance(consumers, list) else 0
        if n_consumers == 0 or not producers:
            # Никто не смотрит — producer может быть idle легитимно; baseline сброс.
            self._go2rtc_last_bytes_recv = None
            return
        cur = producers[0].get("bytes_recv")
        if not isinstance(cur, int):
            return
        prev = self._go2rtc_last_bytes_recv
        self._go2rtc_last_bytes_recv = cur
        if prev is not None and cur == prev:
            LOGGER.debug(
                "Camera %s (%s): go2rtc producer frozen "
                "(bytes_recv=%d, %d consumer(s)) — triggering recovery",
                self._name, self._id, cur, n_consumers,
            )
            self._maybe_schedule_stream_recovery()
            # Ре-baseline: после re-mint producer стартует заново.
            self._go2rtc_last_bytes_recv = None
