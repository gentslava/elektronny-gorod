"""Background publisher for Elektronny Gorod camera streams in go2rtc."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    DEFAULT_GO2RTC_PUBLISH_HIDDEN,
    DEFAULT_GO2RTC_REFRESH_INTERVAL,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_PUBLISH_HIDDEN,
    CONF_GO2RTC_REFRESH_INTERVAL,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_USE_GO2RTC,
    DOMAIN,
    GO2RTC_RTSP_PORT,
    LOGGER,
)
from .coordinator import ElektronnyGorodUpdateCoordinator
from .go2rtc import (
    build_basic_auth_headers,
    build_go2rtc_src,
    normalize_base_url,
    upsert_go2rtc_stream,
)

RETRY_INTERVAL = timedelta(seconds=60)


class Go2RtcStreamPublisher:
    """Keep operator cameras published as stable RTSP streams in go2rtc."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: ElektronnyGorodUpdateCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._last_src: dict[str, str] = {}
        self._task: asyncio.Task | None = None
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._unsub_retry: CALLBACK_TYPE | None = None

    @property
    def enabled(self) -> bool:
        """Return True if go2rtc publishing is enabled for the entry."""
        if CONF_USE_GO2RTC in self.entry.options:
            return bool(self.entry.options.get(CONF_USE_GO2RTC))
        return bool(self.entry.data.get(CONF_USE_GO2RTC, False))

    @property
    def base_url(self) -> str:
        """Return normalized go2rtc HTTP API base URL."""
        value = self.entry.options.get(CONF_GO2RTC_BASE_URL) or self.entry.data.get(
            CONF_GO2RTC_BASE_URL
        )
        return normalize_base_url(value)

    @property
    def rtsp_host(self) -> str | None:
        """Return the host external clients should use for go2rtc RTSP."""
        return self.entry.options.get(CONF_GO2RTC_RTSP_HOST) or self.entry.data.get(
            CONF_GO2RTC_RTSP_HOST
        )

    @property
    def refresh_interval(self) -> timedelta:
        """Return configured stream refresh interval."""
        value = self.entry.options.get(
            CONF_GO2RTC_REFRESH_INTERVAL,
            self.entry.data.get(
                CONF_GO2RTC_REFRESH_INTERVAL,
                DEFAULT_GO2RTC_REFRESH_INTERVAL,
            ),
        )
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            minutes = DEFAULT_GO2RTC_REFRESH_INTERVAL
        return timedelta(minutes=max(1, minutes))

    @property
    def publish_hidden(self) -> bool:
        """Return True if hidden cameras should also be published to go2rtc."""
        return bool(
            self.entry.options.get(
                CONF_GO2RTC_PUBLISH_HIDDEN,
                self.entry.data.get(
                    CONF_GO2RTC_PUBLISH_HIDDEN,
                    DEFAULT_GO2RTC_PUBLISH_HIDDEN,
                ),
            )
        )

    def rtsp_url_for(self, camera_id: str) -> str | None:
        """Return stable RTSP URL for a camera id, if RTSP host is configured."""
        if not self.rtsp_host:
            return None
        return f"rtsp://{self.rtsp_host}:{GO2RTC_RTSP_PORT}/eg_{camera_id}"

    async def async_start(self) -> None:
        """Start initial and periodic go2rtc publishing."""
        if not self.enabled:
            return

        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._schedule_sync,
            self.refresh_interval,
        )
        self._schedule_sync(None)

    async def async_stop(self) -> None:
        """Stop periodic publishing."""
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        if self._unsub_retry is not None:
            self._unsub_retry()
            self._unsub_retry = None
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    @callback
    def _schedule_sync(self, _now: Any) -> None:
        """Schedule one sync run, skipping overlap."""
        if self._task is not None and not self._task.done():
            LOGGER.debug("go2rtc stream publisher sync already running; skip tick")
            return
        self._task = self.hass.async_create_task(
            self.async_sync_once(),
            name=f"{DOMAIN}_go2rtc_stream_sync_{self.entry.entry_id}",
        )

    def _schedule_retry(self) -> None:
        """Schedule a quick retry after a failed sync."""
        if self._unsub_retry is not None:
            return

        @callback
        def _retry(_now: Any) -> None:
            self._unsub_retry = None
            self._schedule_sync(_now)

        self._unsub_retry = async_call_later(
            self.hass,
            RETRY_INTERVAL.total_seconds(),
            _retry,
        )

    async def async_sync_once(self) -> None:
        """Publish current coordinator cameras to go2rtc once."""
        if not self.enabled:
            return

        base_url = self.base_url
        if not base_url:
            LOGGER.debug("go2rtc publisher enabled but base_url is missing")
            return

        cameras = (self.coordinator.data or {}).get("cameras") or []
        if not cameras:
            LOGGER.debug("go2rtc publisher: no cameras in coordinator data")
            return

        session: ClientSession = async_get_clientsession(self.hass)
        headers = build_basic_auth_headers(
            self.entry.options.get(CONF_GO2RTC_USERNAME)
            or self.entry.data.get(CONF_GO2RTC_USERNAME),
            self.entry.options.get(CONF_GO2RTC_PASSWORD)
            or self.entry.data.get(CONF_GO2RTC_PASSWORD),
        )

        published = 0
        failed = 0
        for camera in cameras:
            camera_id = str(camera.get("id") or "")
            if not camera_id:
                continue
            if camera.get("hidden") and not self.publish_hidden:
                continue
            try:
                stream_url = await self.coordinator.get_camera_stream(camera_id)
                if not stream_url:
                    LOGGER.warning(
                        "go2rtc publisher: empty stream URL for camera %s",
                        camera_id,
                    )
                    failed += 1
                    continue

                src = build_go2rtc_src(stream_url)
                stream_name = f"eg_{camera_id}"
                if self._last_src.get(stream_name) == src:
                    continue

                await upsert_go2rtc_stream(
                    session=session,
                    base_url=base_url,
                    stream_name=stream_name,
                    src=src,
                    headers=headers,
                )
                self._last_src[stream_name] = src
                camera["go2rtc_rtsp_url"] = self.rtsp_url_for(camera_id)
                published += 1
            except Exception as err:  # noqa: BLE001 - keep other cameras publishing
                failed += 1
                LOGGER.warning(
                    "go2rtc publisher: failed to publish camera %s: %s",
                    camera_id,
                    err,
                )

        if published:
            LOGGER.info("go2rtc publisher updated %d camera stream(s)", published)
        if failed:
            self._schedule_retry()
