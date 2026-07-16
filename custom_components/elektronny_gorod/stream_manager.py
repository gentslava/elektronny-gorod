"""Per-entry ownership of operator camera streams published through go2rtc."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .go2rtc import Go2RtcClient, Go2RtcRequestError


@dataclass(frozen=True)
class StreamRefreshResult:
    """Transient refresh result returned to an HA or background caller."""

    url: str | None
    proxied: bool


@dataclass
class ManagedCameraState:
    """Credential-free mutable state owned by CameraStreamManager."""

    camera_id: str
    stream_name: str
    display_name: str
    eligible: bool = False
    present: bool = False
    consumer_count: int = 0
    last_success: datetime | None = None
    last_success_monotonic: float | None = None
    next_due_monotonic: float | None = None
    failure_count: int = 0
    status: str = "idle"
    cleanup_pending: bool = False


class CameraStreamManager:
    """Single writer for integration-owned `eg_<camera_id>` streams."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: Any,
        client: Go2RtcClient,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.client = client
        self._states: dict[str, ManagedCameraState] = {}
        self._inflight: dict[
            str, asyncio.Task[StreamRefreshResult]
        ] = {}

    async def async_refresh(
        self,
        camera_id: str,
        reason: str,
    ) -> StreamRefreshResult:
        """Join or start one complete operator-mint and go2rtc-PATCH chain."""
        camera_id = str(camera_id)
        task = self._inflight.get(camera_id)
        if task is None:
            task = asyncio.create_task(
                self._async_refresh_owner(camera_id, reason),
                name=f"elektronny_gorod_stream_refresh_{camera_id}",
            )
            self._inflight[camera_id] = task
        return await asyncio.shield(task)

    def camera_state(self, camera_id: str) -> ManagedCameraState | None:
        """Return a detached, credential-free snapshot for diagnostics."""
        state = self._states.get(str(camera_id))
        return replace(state) if state is not None else None

    async def _async_refresh_owner(
        self,
        camera_id: str,
        reason: str,
    ) -> StreamRefreshResult:
        """Own one refresh; source URLs exist only in this coroutine/result."""
        state = self._state_for(camera_id)
        try:
            try:
                source_url = await self.coordinator.get_camera_stream(camera_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - sanitize operator boundary
                self._record_failure(state, "operator_error")
                return StreamRefreshResult(url=None, proxied=False)

            if not source_url:
                self._record_failure(state, "empty_source")
                return StreamRefreshResult(url=None, proxied=False)

            stream_source = (
                f"ffmpeg:{source_url}"
                "#video=copy#audio=aac#audio=opus"
            )
            try:
                await self.client.async_patch_stream(
                    state.stream_name,
                    stream_source,
                )
            except Go2RtcRequestError as err:
                self._record_failure(state, f"patch_{err.category}")
                return StreamRefreshResult(url=source_url, proxied=False)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep unexpected details private
                self._record_failure(state, "patch_unexpected")
                return StreamRefreshResult(url=source_url, proxied=False)

            state.present = True
            state.last_success = datetime.now(timezone.utc)
            state.last_success_monotonic = time.monotonic()
            state.failure_count = 0
            state.status = "ready"
            return StreamRefreshResult(
                url=self.client.rtsp_url(
                    state.stream_name,
                    include_credentials=True,
                ),
                proxied=True,
            )
        finally:
            current = asyncio.current_task()
            if self._inflight.get(camera_id) is current:
                self._inflight.pop(camera_id, None)

    def _state_for(self, camera_id: str) -> ManagedCameraState:
        state = self._states.get(camera_id)
        if state is not None:
            return state
        display_name = camera_id
        for camera in (self.coordinator.data or {}).get("cameras") or []:
            if str(camera.get("id") or "") == camera_id:
                display_name = str(camera.get("name") or camera_id)
                break
        state = ManagedCameraState(
            camera_id=camera_id,
            stream_name=f"eg_{camera_id}",
            display_name=display_name,
        )
        self._states[camera_id] = state
        return state

    @staticmethod
    def _record_failure(state: ManagedCameraState, status: str) -> None:
        state.failure_count += 1
        state.status = status
