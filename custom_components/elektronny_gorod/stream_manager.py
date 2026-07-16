"""Per-entry ownership of operator camera streams published through go2rtc."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    DEFAULT_GO2RTC_KEEP_WARM,
    DEFAULT_GO2RTC_KEEP_WARM_HIDDEN,
    DOMAIN,
)
from .go2rtc import Go2RtcClient, Go2RtcRequestError


BACKGROUND_REFRESH_INTERVAL = timedelta(minutes=28, seconds=30)
RECONCILE_INTERVAL = timedelta(minutes=1)
STARTUP_JITTER_MAX_SECONDS = 60.0
RETRY_INITIAL_SECONDS = 15.0
RETRY_MAX_SECONDS = 300.0


def _monotonic() -> float:
    """Patchable monotonic clock boundary for deterministic scheduler tests."""
    return time.monotonic()


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
        self.keep_warm = bool(
            self._entry_value(
                CONF_GO2RTC_KEEP_WARM,
                DEFAULT_GO2RTC_KEEP_WARM,
            )
        )
        self.keep_warm_hidden = bool(
            self._entry_value(
                CONF_GO2RTC_KEEP_WARM_HIDDEN,
                DEFAULT_GO2RTC_KEEP_WARM_HIDDEN,
            )
        )
        self._states: dict[str, ManagedCameraState] = {}
        self._inflight: dict[
            str, asyncio.Task[StreamRefreshResult]
        ] = {}
        self._due_unsubs: dict[str, CALLBACK_TYPE] = {}
        self._reconcile_unsub: CALLBACK_TYPE | None = None
        self._registry_unsub: CALLBACK_TYPE | None = None
        self._prompt_reconcile_unsub: CALLBACK_TYPE | None = None
        self._reconcile_lock = asyncio.Lock()
        self._started = False

    async def async_start(self) -> None:
        """Start opt-in reconcile/listener/timers after entity setup."""
        if self._started:
            return
        self._started = True
        if not self.keep_warm:
            return

        self._registry_unsub = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_registry_update,
        )
        self._reconcile_unsub = async_track_time_interval(
            self.hass,
            self._async_reconcile_interval,
            RECONCILE_INTERVAL,
            name=f"{DOMAIN}_stream_manager_reconcile",
        )

        # Observe existing go2rtc state and clean ineligible streams without
        # bypassing the bounded per-camera startup jitter for missing streams.
        await self.async_reconcile(refresh_missing=False)
        for camera_id in self._camera_ids():
            state = self._state_for(camera_id)
            state.eligible = self.is_camera_eligible(camera_id)
            if state.eligible:
                self._schedule_due(
                    camera_id,
                    self._startup_offset(camera_id),
                )

    async def async_stop(self) -> None:
        """Idempotently cancel every listener, timer, and refresh owner."""
        self._started = False
        for attr in (
            "_registry_unsub",
            "_reconcile_unsub",
            "_prompt_reconcile_unsub",
        ):
            unsub = getattr(self, attr)
            if unsub is not None:
                unsub()
                setattr(self, attr, None)

        for unsub in self._due_unsubs.values():
            unsub()
        self._due_unsubs.clear()
        for state in self._states.values():
            state.next_due_monotonic = None

        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._inflight.clear()

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

    def is_camera_eligible(self, camera_id: str) -> bool:
        """Return registry-derived opt-in policy for one camera."""
        if not self.keep_warm:
            return False
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "camera",
            DOMAIN,
            f"{DOMAIN}_camera_{camera_id}",
        )
        if entity_id is None:
            return False
        registry_entry = registry.async_get(entity_id)
        if (
            registry_entry is None
            or registry_entry.config_entry_id != self.entry.entry_id
            or registry_entry.disabled_by is not None
        ):
            return False
        return (
            registry_entry.hidden_by is None
            or self.keep_warm_hidden
        )

    async def async_reconcile(self, *, refresh_missing: bool = True) -> None:
        """Compare one complete go2rtc snapshot with registry desired state."""
        if not self.keep_warm:
            return
        async with self._reconcile_lock:
            try:
                streams = await self.client.async_list_streams()
            except asyncio.CancelledError:
                raise
            except Go2RtcRequestError:
                return
            except Exception:  # noqa: BLE001 - keep scheduler alive, details private
                return

            refreshes: list[asyncio.Future[StreamRefreshResult] | Any] = []
            cleanups: list[Any] = []
            for camera_id in self._camera_ids():
                state = self._state_for(camera_id)
                state.eligible = self.is_camera_eligible(camera_id)
                info = streams.get(state.stream_name)
                state.present = info is not None
                state.consumer_count = info.consumer_count if info is not None else 0

                if state.eligible:
                    state.cleanup_pending = False
                    if info is None and refresh_missing:
                        refreshes.append(
                            self.async_refresh(camera_id, "missing")
                        )
                    elif info is not None and state.status == "idle":
                        state.status = "present"
                    continue

                self._cancel_due(camera_id)
                if info is None:
                    state.cleanup_pending = False
                    continue
                if info.consumer_count > 0:
                    state.cleanup_pending = True
                    state.status = "cleanup_pending"
                    continue
                cleanups.append(self._async_delete_stream(state))

            if cleanups:
                await asyncio.gather(*cleanups)
            if refreshes:
                await asyncio.gather(*refreshes)

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
            completed = _monotonic()
            state.last_success_monotonic = completed
            state.failure_count = 0
            state.status = "ready"
            if (
                self._started
                and self.keep_warm
                and self.is_camera_eligible(camera_id)
            ):
                self._schedule_due(
                    camera_id,
                    BACKGROUND_REFRESH_INTERVAL.total_seconds(),
                    base_monotonic=completed,
                )
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

    def _record_failure(self, state: ManagedCameraState, status: str) -> None:
        state.failure_count += 1
        state.status = status
        if (
            self._started
            and self.keep_warm
            and self.is_camera_eligible(state.camera_id)
        ):
            retry_delay = min(
                RETRY_INITIAL_SECONDS * (2 ** (state.failure_count - 1)),
                RETRY_MAX_SECONDS,
            )
            self._schedule_due(state.camera_id, retry_delay)

    async def _async_delete_stream(self, state: ManagedCameraState) -> None:
        try:
            await self.client.async_delete_stream(state.stream_name)
        except Go2RtcRequestError as err:
            state.status = f"delete_{err.category}"
            state.cleanup_pending = True
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize unexpected transport detail
            state.status = "delete_unexpected"
            state.cleanup_pending = True
            return
        state.present = False
        state.consumer_count = 0
        state.cleanup_pending = False
        state.status = "excluded"

    def _entry_value(self, key: str, default: Any) -> Any:
        options = getattr(self.entry, "options", {})
        data = getattr(self.entry, "data", {})
        return options.get(key, data.get(key, default))

    def _camera_ids(self) -> list[str]:
        result: list[str] = []
        for camera in (self.coordinator.data or {}).get("cameras") or []:
            camera_id = str(camera.get("id") or "")
            if camera_id:
                result.append(camera_id)
        return result

    def _startup_offset(self, camera_id: str) -> float:
        seed = f"{self.entry.entry_id}:{camera_id}".encode()
        bucket = int.from_bytes(hashlib.sha256(seed).digest()[:8], "big")
        return (bucket % int(STARTUP_JITTER_MAX_SECONDS * 1000)) / 1000

    def _schedule_due(
        self,
        camera_id: str,
        delay: float,
        *,
        base_monotonic: float | None = None,
    ) -> None:
        if not self._started or not self.keep_warm:
            return
        self._cancel_due(camera_id)
        state = self._state_for(camera_id)
        base = _monotonic() if base_monotonic is None else base_monotonic
        state.next_due_monotonic = base + delay

        async def _due(_now: datetime) -> None:
            self._due_unsubs.pop(camera_id, None)
            state.next_due_monotonic = None
            if self._started and self.is_camera_eligible(camera_id):
                await self.async_refresh(camera_id, "background_due")

        self._due_unsubs[camera_id] = async_call_later(
            self.hass,
            delay,
            _due,
        )

    def _cancel_due(self, camera_id: str) -> None:
        unsub = self._due_unsubs.pop(camera_id, None)
        if unsub is not None:
            unsub()
        state = self._states.get(camera_id)
        if state is not None:
            state.next_due_monotonic = None

    async def _async_reconcile_interval(self, _now: datetime) -> None:
        await self.async_reconcile()

    def _handle_registry_update(self, event: Event) -> None:
        entity_id = str((event.data or {}).get("entity_id") or "")
        if not entity_id.startswith("camera."):
            return
        if self._prompt_reconcile_unsub is not None or not self._started:
            return

        async def _prompt(_now: datetime) -> None:
            self._prompt_reconcile_unsub = None
            await self.async_reconcile()

        self._prompt_reconcile_unsub = async_call_later(
            self.hass,
            0,
            _prompt,
        )
