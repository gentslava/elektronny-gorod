"""camera.intercom_call — экран вызова через HA-native (call-screen-display-design.md).

Одна сущность на entry. stream_source() при активном вызове пересобирает go2rtc-стрим
eg_intercom_call (СВЕЖИЙ video-RTSP домофона + аудио-мост) → RTSP. Рефреш-на-открытии
убирает EOF (как у камер). Вне вызова → None. HA-native отдаёт video+audio (4G, без
экспозиции go2rtc). camera.py stream-lifecycle не трогаем.
"""
from __future__ import annotations

from collections.abc import Callable

from aiohttp import ClientTimeout

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import Event, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CALL_STATE_ACTIVE,
    CALL_STATE_ENDED,
    CALL_STATE_ERROR,
    DOMAIN,
    EVENT_CALL_STATE,
    GO2RTC_RTSP_PORT,
    LOGGER,
)
from .go2rtc import remove_audio_stream, upsert_audio_stream
from .sip.call_controller import CALL_STREAM_NAME, DoorbellCallController


class ElektronnyGorodCallCamera(Camera):
    """Camera-сущность активного вызова (video домофона + downlink-аудио)."""

    _attr_has_entity_name = True
    _attr_name = None  # имя берётся из DeviceInfo(name="Вызов домофона")
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        controller_getter: Callable[[], "DoorbellCallController | None"],
        go2rtc_base_url: str,
        go2rtc_headers: dict,
        rtsp_host: str,
        doorbell_lookup: Callable[[str], Camera | None],
        entry_id: str,
    ) -> None:
        super().__init__()
        self._controller_getter = controller_getter
        self._base_url = go2rtc_base_url
        self._headers = go2rtc_headers
        self._rtsp_host = rtsp_host
        # camera_id → entity домофона (для рефреша её source); из camera-платформы.
        self._doorbell_lookup = doorbell_lookup
        self._last_available: bool | None = None  # DIAG: лог смены available
        # A-88 anti-churn: (id(bridge), rtsp_url) собранного стрима текущего звонка.
        # Сбор — один раз на звонок; последующие открытия отдают этот URL.
        self._call_stream_cache: tuple[int, str] | None = None
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_intercom_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_intercom_call")}, name="Вызов домофона"
        )

    async def async_added_to_hass(self) -> None:
        """Слушать смену фазы вызова, чтобы обновлять `available`/снапшот в UI.

        `available` этой сущности зависит от активного вызова, но HA не узнает об
        изменении без записи состояния. Контроллер шлёт `EVENT_CALL_STATE` на
        каждой смене фазы (ringing/active/ended/…) — по нему пишем state, тогда
        фронтенд видит камеру доступной во время разговора и запрашивает стрим
        (иначе весь звонок висит «Видео недоступно» и видео не запрашивается)."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CALL_STATE, self._on_call_state)
        )

    @callback
    def _on_call_state(self, event: Event) -> None:
        """Фаза вызова изменилась → обновить state; на `active` — прогреть стрим."""
        state = (getattr(event, "data", None) or {}).get("state")
        self.async_write_ha_state()
        if state == CALL_STATE_ACTIVE:
            self.hass.async_create_task(self._warm_up())
        elif state in (CALL_STATE_ENDED, CALL_STATE_ERROR):
            # A-88: снять go2rtc-стрим вызова — иначе HA Stream worker ретраит
            # мёртвый `eg_intercom_call` (404 каждые ~60–90 с после звонка).
            self.hass.async_create_task(self._teardown_call_stream())

    async def _teardown_call_stream(self) -> None:
        """Best-effort снятие `eg_intercom_call` из go2rtc + сброс anti-churn кэша."""
        self._call_stream_cache = None
        if not self._base_url:
            return
        try:
            session = async_get_clientsession(self.hass)
            await remove_audio_stream(
                self._base_url, CALL_STREAM_NAME, session, self._headers
            )
            LOGGER.debug("call-camera teardown: стрим %s снят из go2rtc", CALL_STREAM_NAME)
        except Exception:  # noqa: BLE001 — teardown best-effort
            LOGGER.debug("call-camera teardown не удался", exc_info=True)

    async def _warm_up(self) -> None:
        """Anti-delay: на answer заранее собрать `eg_intercom_call` и поднять
        producer (первый keyframe) ДО открытия карточки — иначе видео вызова
        поднимается с ~3с задержкой (сборка стрима + первый keyframe в момент
        открытия). Идемпотентно с последующим `stream_source()` от фронтенда."""
        try:
            url = await self.stream_source()  # строит eg_intercom_call в go2rtc
            if not url:
                return
            # Нудж go2rtc поднять producer (и первый keyframe) — GET frame.jpeg.
            session = async_get_clientsession(self.hass)
            probe = f"{self._base_url}/api/frame.jpeg?src={CALL_STREAM_NAME}"
            async with session.get(
                probe, headers=self._headers, timeout=ClientTimeout(total=8)
            ) as resp:
                await resp.read()
            LOGGER.debug("call-camera warm-up: producer прогрет (keyframe запрошен)")
        except Exception:  # noqa: BLE001 — прогрев best-effort, не влияет на вызов
            LOGGER.debug("call-camera warm-up не удался", exc_info=True)

    @property
    def available(self) -> bool:
        """Доступна ТОЛЬКО во время активного вызова.

        Вне вызова HA не должен пытаться стримить/снимать эту сущность: иначе
        HA Stream worker бесконечно ретраит мёртвый `rtsp://…/eg_intercom_call`
        (404, спам в логе), а снапшот-запросы валятся. Пока `active_call_media`
        None — entity `unavailable`, карточка показывает чистый плейсхолдер."""
        controller = self._controller_getter()
        v = controller is not None and controller.active_call_media() is not None
        if v != self._last_available:
            LOGGER.debug("call-camera available: %s -> %s", self._last_available, v)
            self._last_available = v
        return v

    def _active_doorbell(self) -> Camera | None:
        """Камера домофона активного вызова (для снапшота), либо None."""
        controller = self._controller_getter()
        if controller is None:
            return None
        media = controller.active_call_media()
        if media is None:
            return None
        camera_id, _bridge = media
        return self._doorbell_lookup(camera_id)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Снимок/постер экрана вызова = снапшот камеры домофона.

        Базовый `Camera.camera_image()` кидает `NotImplementedError` — раньше это
        валило постер `ha-camera-stream` и любой снапшот (серый прямоугольник +
        спам ошибок в логе). Делегируем на камеру домофона активного вызова; вне
        вызова — None (нет кадра, без ошибки)."""
        doorbell = self._active_doorbell()
        if doorbell is None:
            return None
        return await doorbell.async_camera_image(width, height)

    async def stream_source(self) -> str | None:
        """Активный вызов → свежий combined-стрим eg_intercom_call → RTSP; иначе None."""
        controller = self._controller_getter()
        if controller is None:
            return None
        media = controller.active_call_media()
        if media is None:
            self._call_stream_cache = None  # звонок кончился → сброс кэша
            return None
        camera_id, bridge = media
        # A-88 anti-churn: собрать стрим ОДИН раз на звонок. Последующие открытия
        # (второй клиент, WebRTC re-offer, повторный stream_source) отдают уже
        # собранный URL и подключаются к тому же go2rtc-продюсеру — БЕЗ пересборки.
        # Иначе пере-фетч одноразового operator-URL пере-собирал общий forpost-
        # продюсер → у второго клиента видео пустое / рвётся.
        if self._call_stream_cache is not None and self._call_stream_cache[0] == id(bridge):
            return self._call_stream_cache[1]
        doorbell = self._doorbell_lookup(camera_id)
        if doorbell is None:
            return None
        # рефреш видео-источника домофона (свежий operator-URL → свежий eg_<camera> RTSP)
        video_rtsp = await doorbell.stream_source()
        if not video_rtsp:
            return None
        srcs = [f"{video_rtsp}#video=copy", bridge.go2rtc_src]
        try:
            await upsert_audio_stream(
                self._base_url, CALL_STREAM_NAME, srcs,
                async_get_clientsession(self.hass), self._headers,
            )
        except Exception as exc:  # noqa: BLE001
            # Стрим не создан в go2rtc (напр. раздутый конфиг, A-84) — НЕ отдаём
            # мёртвый RTSP-URL, иначе HA Stream worker ловит 404 и спамит. Лучше
            # None → сущность без видео (карточка покажет плейсхолдер).
            LOGGER.warning(
                "Стрим вызова не создан в go2rtc (%s) — видео вызова недоступно",
                type(exc).__name__,
            )
            return None
        url = f"rtsp://{self._rtsp_host}:{GO2RTC_RTSP_PORT}/{CALL_STREAM_NAME}"
        self._call_stream_cache = (id(bridge), url)  # anti-churn: собрано на звонок
        LOGGER.debug("Стрим вызова собран (HA-native): %s", CALL_STREAM_NAME)
        return url
