"""camera.intercom_call — экран вызова через HA-native (call-screen-display-design.md).

Одна сущность на entry. stream_source() при активном вызове пересобирает go2rtc-стрим
eg_intercom_call (СВЕЖИЙ video-RTSP домофона + аудио-мост) → RTSP. Рефреш-на-открытии
убирает EOF (как у камер). Вне вызова → None. HA-native отдаёт video+audio (4G, без
экспозиции go2rtc). camera.py stream-lifecycle не трогаем.
"""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, GO2RTC_RTSP_PORT, LOGGER
from .go2rtc import upsert_audio_stream
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
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_intercom_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_intercom_call")}, name="Вызов домофона"
        )

    async def stream_source(self) -> str | None:
        """Активный вызов → свежий combined-стрим eg_intercom_call → RTSP; иначе None."""
        controller = self._controller_getter()
        if controller is None:
            return None
        media = controller.active_call_media()
        if media is None:
            return None
        camera_id, bridge = media
        doorbell = self._doorbell_lookup(camera_id)
        if doorbell is None:
            return None
        # рефреш видео-источника домофона (свежий operator-URL → свежий eg_<camera> RTSP)
        video_rtsp = await doorbell.stream_source()
        if not video_rtsp:
            return None
        srcs = [f"{video_rtsp}#video=copy", bridge.go2rtc_src]
        await upsert_audio_stream(
            self._base_url, CALL_STREAM_NAME, srcs,
            async_get_clientsession(self.hass), self._headers,
        )
        LOGGER.debug("Стрим вызова собран (HA-native): %s", CALL_STREAM_NAME)
        return f"rtsp://{self._rtsp_host}:{GO2RTC_RTSP_PORT}/{CALL_STREAM_NAME}"
