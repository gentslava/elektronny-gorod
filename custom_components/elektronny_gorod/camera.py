from __future__ import annotations

from urllib.parse import urlencode

from aiohttp import ClientSession, ClientError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    LOGGER,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    GO2RTC_RTSP_PORT,
)
from .coordinator import ElektronnyGorodUpdateCoordinator


def _build_go2rtc_src(source_url: str) -> str:
    # Video copy, audio -> AAC/OPUS (go2rtc will then output to WebRTC/HLS as needed)
    return f"ffmpeg:{source_url}#video=copy#audio=aac#audio=opus"


async def _go2rtc_upsert_stream(
    session: ClientSession,
    base_url: str,
    stream_name: str,
    src: str,
) -> None:
    qs = urlencode({"name": stream_name, "src": src})
    put_url = f"{base_url}/api/streams?{qs}"
    try:
        async with session.put(put_url) as resp:
            if resp.status in (200, 201, 204):
                return
    except ClientError:
        # PATCH
        pass

    patch_url = f"{base_url}/api/streams?{qs}"
    async with session.patch(patch_url) as resp:
        if resp.status >= 400:
            body = await resp.text()
            raise RuntimeError(f"go2rtc PATCH failed: {resp.status} {body}")


async def _go2rtc_frame_jpeg(
    session: ClientSession,
    base_url: str,
    stream_name: str,
    width: int | None,
    height: int | None,
) -> bytes | None:
    params: dict[str, str] = {"src": stream_name}
    if width:
        params["width"] = str(width)
    if height:
        params["height"] = str(height)

    url = f"{base_url}/api/frame.jpeg?{urlencode(params)}"
    async with session.get(url) as resp:
        if resp.status != 200:
            return None
        return await resp.read()


def _get_go2rtc_cfg(entry: ConfigEntry) -> tuple[bool, str | None, str | None]:
    use_go2rtc = (
        entry.options.get(CONF_USE_GO2RTC)
        if CONF_USE_GO2RTC in entry.options
        else entry.data.get(CONF_USE_GO2RTC, False)
    )
    base_url = entry.options.get(CONF_GO2RTC_BASE_URL) or entry.data.get(CONF_GO2RTC_BASE_URL)
    rtsp_host = entry.options.get(CONF_GO2RTC_RTSP_HOST) or entry.data.get(CONF_GO2RTC_RTSP_HOST)
    return bool(use_go2rtc), base_url, rtsp_host


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Camera based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    cameras_info = await coordinator.get_cameras_info()

    use_go2rtc, base_url, rtsp_host = _get_go2rtc_cfg(entry)

    async_add_entities(
        ElektronnyGorodCamera(hass, coordinator, camera_info, use_go2rtc, base_url, rtsp_host)
        for camera_info in cameras_info
    )


class ElektronnyGorodCamera(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ElektronnyGorodUpdateCoordinator,
        camera_info: dict,
        use_go2rtc: bool,
        go2rtc_base_url: str | None,
        go2rtc_rtsp_host: str | None,
    ) -> None:
        super().__init__()
        self.hass = hass

        self._coordinator: ElektronnyGorodUpdateCoordinator = coordinator
        self._camera_info: dict = camera_info

        self._id = self._camera_info["ID"]
        self._name = self._camera_info["Name"]

        self._attr_supported_features = CameraEntityFeature.STREAM
        self._last_src: str | None = None
        self._image: bytes | None = None
        self._attr_unique_id = f"{self._id}_{self._name}"

        self._go2rtc_base_url = go2rtc_base_url
        self._go2rtc_rtsp_host = go2rtc_rtsp_host
        self._use_go2rtc = use_go2rtc
        self._go2rtc_stream_name = f"eg_{self._id}"

    @property
    def name(self) -> str:
        """Return camera name."""
        return self._name

    def _rtsp_url(self) -> str:
        if not self._go2rtc_rtsp_host:
            raise RuntimeError("go2rtc rtsp host is not configured")
        return f"rtsp://{self._go2rtc_rtsp_host}:{GO2RTC_RTSP_PORT}/{self._go2rtc_stream_name}"

    async def _ensure_go2rtc_stream(self, source_url: str) -> None:
        if not self._use_go2rtc:
            return

        base_url = self._go2rtc_base_url
        if not base_url:
            LOGGER.debug("go2rtc enabled but base_url is missing; falling back to direct FLV")
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
        )
        self._last_src = src

        LOGGER.debug(
            "go2rtc stream updated: name=%s rtsp=%s",
            self._go2rtc_stream_name,
            self._rtsp_url(),
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        image = await self._coordinator.get_camera_snapshot(self._id, width, height)
        if image:
            self._image = image
        return self._image

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        stream_url = await self._coordinator.get_camera_stream(self._id)
        LOGGER.info("Stream url is %s", stream_url)
        if not stream_url:
            LOGGER.warning("Camera %s (%s): empty source stream url", self._name, self._id)
            return None

        if not self._use_go2rtc:
            return stream_url

        await self._ensure_go2rtc_stream(stream_url)
        return self._rtsp_url()

    async def async_update(self) -> None:
        """Update camera state."""
        self._camera_info = await self._coordinator.update_camera_state(self._id)
        self._is_on = self._camera_info["IsActive"] == 1
        self._is_streaming = self._camera_info["State"] == 1
        self._is_recording = self._camera_info["RecordType"] == 1
