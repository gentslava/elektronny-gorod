"""Camera entity — CoordinatorEntity-based.

См. ADR-0002. Slice 3b: camera использует coordinator.data для availability.
Stream / snapshot — on-demand actions (не кэшируются в coordinator.data).

Closes A-44: `async_update` удалён, дублирующий `get_camera_stream`-запрос
тоже. Stream URL получается лениво в `stream_source()`.
"""
from __future__ import annotations

import base64
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
        is_intercom = bool(ac_id and place_id)

        LOGGER.debug("Camera init id=%s intercom=%s", self._id, is_intercom)

        self._last_src: str | None = None
        self._image: bytes | None = None
        self._attr_unique_id = f"{DOMAIN}_camera_{self._id}"
        if is_intercom:
            device_uid = f"entrance_{place_id}_{ac_id}_{entrance_id or 'main'}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_uid)},
                name=self._name,
                manufacturer="Электронный город",
                model="Intercom",
                via_device=(DOMAIN, f"place_{place_id}"),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"camera_{self._id}")},
                name=self._name,
                manufacturer="Электронный город",
                model="IP Camera",
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
        await _go2rtc_upsert_stream(
            session=session,
            base_url=base_url,
            stream_name=self._go2rtc_stream_name,
            src=src,
            headers=headers,
        )
        self._last_src = src

        LOGGER.debug(
            "go2rtc stream updated: name=%s rtsp=%s",
            self._go2rtc_stream_name,
            self._rtsp_url(),
        )

    # ------------------------------------------------------------------ #
    # On-demand actions                                                  #
    # ------------------------------------------------------------------ #

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if not self.available:
            return None
        image = await self.coordinator.get_camera_snapshot(self._id, width, height)
        if image:
            self._image = image
        return self._image

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        stream_url = await self.coordinator.get_camera_stream(self._id)
        if not stream_url:
            LOGGER.warning("Camera %s (%s): empty source stream url", self._name, self._id)
            return None
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
