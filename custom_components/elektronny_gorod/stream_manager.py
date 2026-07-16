"""Per-entry ownership of operator camera streams published through go2rtc."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_USE_GO2RTC,
    DEFAULT_GO2RTC_KEEP_WARM,
    DEFAULT_GO2RTC_KEEP_WARM_HIDDEN,
    DOMAIN,
    LOGGER,
)
from .go2rtc import Go2RtcClient, Go2RtcRequestError, Go2RtcStreamInfo


BACKGROUND_REFRESH_INTERVAL = timedelta(minutes=28, seconds=30)
RECONCILE_INTERVAL = timedelta(minutes=1)
STARTUP_JITTER_MAX_SECONDS = 60.0
POLICY_ENABLE_STAGGER_SECONDS = 0.5
RETRY_INITIAL_SECONDS = 15.0
RETRY_MAX_SECONDS = 300.0
BACKGROUND_REFRESH_REASONS = frozenset({"background_due", "reconcile"})
ON_DEMAND_REFRESH_REASONS = frozenset({
    "ha_open",
    "recovery",
    "active_consumer",
})


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
    preloaded: bool = False
    producer_active: bool = False
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
        self._listeners: set[Callable[[], None]] = set()
        self._owned_preloads: set[str] = set()
        self._started = False
        self._stopping = False

    async def async_start(self) -> None:
        """Start opt-in reconcile/listener/timers after entity setup."""
        if self._started:
            return
        self._stopping = False
        self._started = True
        if not self.keep_warm:
            # Preserve the publication contract on setup/transport reload:
            # remove every idle integration-owned stream when publishing is
            # disabled, while deferring streams that still have a viewer.
            await self.async_reconcile()
            return

        self._ensure_background_tracking()

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
        self._stopping = True
        self._stop_background_tracking()

        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # A reconcile callback already inside its network snapshot is not in
        # `_inflight`. Waiting for its lock prevents a late preload from
        # surviving the cleanup below.
        async with self._reconcile_lock:
            pass
        self._inflight.clear()
        await self._async_remove_owned_preloads()
        self._listeners.clear()

    async def async_apply_entry_options(self) -> bool:
        """Apply publication-only options without reloading the config entry."""
        if not self._started:
            return False
        use_go2rtc = bool(self._entry_value(CONF_USE_GO2RTC, False))
        base_url = str(self._entry_value(CONF_GO2RTC_BASE_URL, "") or "")
        rtsp_host = str(self._entry_value(CONF_GO2RTC_RTSP_HOST, "") or "")
        username = self._entry_value(CONF_GO2RTC_USERNAME, None) or None
        password = self._entry_value(CONF_GO2RTC_PASSWORD, None) or None
        if (
            not use_go2rtc
            or not base_url
            or not rtsp_host
            or not self.client.matches_configuration(
                base_url=base_url,
                rtsp_host=rtsp_host,
                username=username,
                password=password,
            )
        ):
            return False

        keep_warm = bool(
            self._entry_value(
                CONF_GO2RTC_KEEP_WARM,
                DEFAULT_GO2RTC_KEEP_WARM,
            )
        )
        keep_warm_hidden = bool(
            self._entry_value(
                CONF_GO2RTC_KEEP_WARM_HIDDEN,
                DEFAULT_GO2RTC_KEEP_WARM_HIDDEN,
            )
        )
        await self.async_update_policy(
            keep_warm=keep_warm,
            keep_warm_hidden=keep_warm_hidden,
        )
        return True

    async def async_update_policy(
        self,
        *,
        keep_warm: bool,
        keep_warm_hidden: bool,
    ) -> None:
        """Atomically update publication policy without producer churn."""
        if (
            self.keep_warm == keep_warm
            and self.keep_warm_hidden == keep_warm_hidden
        ):
            return

        async with self._reconcile_lock:
            self.keep_warm = keep_warm
            self.keep_warm_hidden = keep_warm_hidden

        if not keep_warm:
            self._stop_background_tracking()
            await self.async_reconcile()
            return

        self._ensure_background_tracking()
        await self.async_reconcile(refresh_missing=False)
        activation_index = 0
        for camera_id in self._camera_ids():
            state = self._state_for(camera_id)
            state.eligible = self.is_camera_eligible(camera_id)
            if state.eligible and camera_id not in self._due_unsubs:
                self._schedule_due(
                    camera_id,
                    activation_index * POLICY_ENABLE_STAGGER_SECONDS,
                )
                activation_index += 1

    def _ensure_background_tracking(self) -> None:
        """Install policy listeners and reconcile interval once."""
        if self._registry_unsub is None:
            self._registry_unsub = self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._handle_registry_update,
            )
        if self._reconcile_unsub is None:
            self._reconcile_unsub = async_track_time_interval(
                self.hass,
                self._async_reconcile_interval,
                RECONCILE_INTERVAL,
                name=f"{DOMAIN}_stream_manager_reconcile",
            )

    def _stop_background_tracking(self) -> None:
        """Cancel policy listeners and timers without removing preloads."""
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

    async def async_refresh(
        self,
        camera_id: str,
        reason: str,
    ) -> StreamRefreshResult:
        """Join or start one complete operator-mint and go2rtc-PATCH chain."""
        camera_id = str(camera_id)
        task = self._inflight.get(camera_id)
        if task is None:
            task = self.hass.async_create_task(
                self._async_refresh_owner(camera_id, reason),
                name=f"elektronny_gorod_stream_refresh_{camera_id}",
                eager_start=False,
            )
            self._inflight[camera_id] = task
        return await asyncio.shield(task)

    def camera_state(self, camera_id: str) -> ManagedCameraState | None:
        """Return a detached, credential-free snapshot for diagnostics."""
        state = self._states.get(str(camera_id))
        return replace(state) if state is not None else None

    def camera_states(self) -> tuple[ManagedCameraState, ...]:
        """Return sorted detached snapshots without source URLs or secrets."""
        return tuple(
            replace(self._states[camera_id])
            for camera_id in sorted(self._states)
        )

    def async_subscribe(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Subscribe to sanitized manager-state changes."""
        self._listeners.add(listener)

        def _unsubscribe() -> None:
            self._listeners.discard(listener)

        return _unsubscribe

    async def async_get_stream_info(
        self,
        camera_id: str,
    ) -> Go2RtcStreamInfo | None:
        """Read one sanitized go2rtc stream snapshot for A-71 triggers."""
        try:
            return await self.client.async_get_stream(f"eg_{camera_id}")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - transport boundary is sanitized
            return None

    def is_camera_eligible(self, camera_id: str) -> bool:
        """Return whether one camera should own a background preload."""
        return self.keep_warm and self.is_camera_publishable(camera_id)

    def is_camera_publishable(self, camera_id: str) -> bool:
        """Return whether background policy may publish one camera stream."""
        registry_entry = self._enabled_registry_entry(camera_id)
        if registry_entry is None:
            return False
        hidden = registry_entry.hidden_by is not None
        if (
            not hidden
            and not self._started
            and self._camera_is_api_hidden(camera_id)
        ):
            options = dict(registry_entry.options.get(DOMAIN) or {})
            user_shown = bool(options.get("user_shown")) or bool(
                options.get("we_set_integration")
            )
            hidden = not user_shown
        return not hidden or (self.keep_warm and self.keep_warm_hidden)

    def _is_refresh_allowed(self, camera_id: str, reason: str) -> bool:
        """Allow hidden on-demand viewing without background publication."""
        if self._stopping:
            return False
        if self.is_camera_publishable(camera_id):
            return True
        return (
            reason in ON_DEMAND_REFRESH_REASONS
            and self._enabled_registry_entry(camera_id) is not None
        )

    def _enabled_registry_entry(self, camera_id: str) -> Any | None:
        """Return this entry's enabled camera registry row, if present."""
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "camera",
            DOMAIN,
            f"{DOMAIN}_camera_{camera_id}",
        )
        if entity_id is None:
            return None
        registry_entry = registry.async_get(entity_id)
        if (
            registry_entry is None
            or registry_entry.config_entry_id != self.entry.entry_id
            or registry_entry.disabled_by is not None
        ):
            return None
        return registry_entry

    async def async_reconcile(self, *, refresh_missing: bool = True) -> None:
        """Compare one complete go2rtc snapshot with registry desired state."""
        async with self._reconcile_lock:
            try:
                streams = await self.client.async_list_streams()
                preloads = await self.client.async_list_preloads()
            except asyncio.CancelledError:
                raise
            except Go2RtcRequestError:
                return
            except Exception:  # noqa: BLE001 - keep scheduler alive, details private
                return

            refreshes: list[asyncio.Future[StreamRefreshResult] | Any] = []
            cleanups: list[Any] = []
            managed_names = {
                f"eg_{camera_id}" for camera_id in self._camera_ids()
            }
            self._owned_preloads.update(preloads & managed_names)
            for camera_id in self._camera_ids():
                state = self._state_for(camera_id)
                state.eligible = self.is_camera_eligible(camera_id)
                info = streams.get(state.stream_name)
                state.present = info is not None
                state.consumer_count = info.consumer_count if info is not None else 0
                state.preloaded = state.stream_name in preloads
                state.producer_active = (
                    info.producer_active if info is not None else False
                )

                if state.eligible:
                    state.cleanup_pending = False
                    needs_recovery = (
                        info is None
                        or not state.preloaded
                        or not state.producer_active
                    )
                    if needs_recovery and refresh_missing:
                        if state.preloaded and not state.producer_active:
                            # Re-arm the existing preload after a fresh PATCH.
                            state.preloaded = False
                        refreshes.append(
                            self.async_refresh(camera_id, "reconcile")
                        )
                    elif info is None:
                        state.status = "missing"
                    elif not state.preloaded:
                        state.status = "preload_missing"
                    elif not state.producer_active:
                        state.status = "producer_inactive"
                    elif state.status == "idle":
                        state.status = "present"
                    continue

                self._cancel_due(camera_id)
                if info is None and not state.preloaded:
                    state.cleanup_pending = False
                    continue
                cleanups.append(self._async_cleanup_stream(state))

            if cleanups:
                await asyncio.gather(*cleanups)
            if refreshes:
                await asyncio.gather(*refreshes)
            self._notify_listeners()

    async def _async_refresh_owner(
        self,
        camera_id: str,
        reason: str,
    ) -> StreamRefreshResult:
        """Own one refresh; source URLs exist only in this coroutine/result."""
        state = self._state_for(camera_id)
        publishable = self._is_refresh_allowed(camera_id, reason)
        state.eligible = self.is_camera_eligible(camera_id)
        try:
            if not publishable:
                state.status = "excluded"
                self._notify_listeners()
                return self._proxied_result(state)
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

            publishable = self._is_refresh_allowed(camera_id, reason)
            state.eligible = self.is_camera_eligible(camera_id)
            if (
                not publishable
                or (
                    reason in BACKGROUND_REFRESH_REASONS
                    and not state.eligible
                )
            ):
                state.status = "excluded"
                self._notify_listeners()
                return self._proxied_result(state)

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
            state.eligible = self.is_camera_eligible(camera_id)
            if (
                reason in BACKGROUND_REFRESH_REASONS
                and not state.eligible
            ):
                await self._async_cleanup_stream(state)
                self._notify_listeners()
                return self._proxied_result(state)

            needs_preload = state.eligible and not (
                state.preloaded and state.producer_active
            )
            if needs_preload:
                # Claim the stable name before network I/O so unload can issue
                # an idempotent DELETE even if cancellation races a completed
                # server-side preload PUT whose response never reaches us.
                self._owned_preloads.add(state.stream_name)
                try:
                    await self.client.async_enable_preload(state.stream_name)
                except Go2RtcRequestError as err:
                    self._owned_preloads.discard(state.stream_name)
                    state.preloaded = False
                    state.producer_active = False
                    self._record_failure(state, f"preload_{err.category}")
                    return StreamRefreshResult(
                        url=source_url,
                        proxied=False,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - sanitize transport detail
                    self._owned_preloads.discard(state.stream_name)
                    state.preloaded = False
                    state.producer_active = False
                    self._record_failure(state, "preload_unexpected")
                    return StreamRefreshResult(
                        url=source_url,
                        proxied=False,
                    )
                state.preloaded = True
                state.producer_active = True

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
            self._notify_listeners()
            return self._proxied_result(state)
        finally:
            current = asyncio.current_task()
            if self._inflight.get(camera_id) is current:
                self._inflight.pop(camera_id, None)

    def _proxied_result(self, state: ManagedCameraState) -> StreamRefreshResult:
        """Return the stable credential-aware URL without persisting it."""
        return StreamRefreshResult(
            url=self.client.rtsp_url(
                state.stream_name,
                include_credentials=True,
            ),
            proxied=True,
        )

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
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        """Notify diagnostic consumers without letting them break refresh."""
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception as err:  # noqa: BLE001 - HA callback boundary
                LOGGER.error(
                    "go2rtc stream manager listener failed (%s)",
                    type(err).__name__,
                )

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
        state.preloaded = False
        state.producer_active = False
        state.cleanup_pending = False
        state.status = "excluded"

    async def _async_cleanup_stream(self, state: ManagedCameraState) -> None:
        """Remove manager preload, then preserve any external consumers."""
        if state.preloaded:
            try:
                await self.client.async_disable_preload(state.stream_name)
            except Go2RtcRequestError as err:
                state.status = f"preload_disable_{err.category}"
                state.cleanup_pending = True
                return
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - sanitize transport detail
                state.status = "preload_disable_unexpected"
                state.cleanup_pending = True
                return
            state.preloaded = False
            self._owned_preloads.discard(state.stream_name)

        if not state.present:
            state.consumer_count = 0
            state.producer_active = False
            state.cleanup_pending = False
            state.status = "excluded"
            return

        try:
            info = await self.client.async_get_stream(state.stream_name)
        except Go2RtcRequestError as err:
            state.status = f"cleanup_get_{err.category}"
            state.cleanup_pending = True
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize transport detail
            state.status = "cleanup_get_unexpected"
            state.cleanup_pending = True
            return

        if info is None:
            state.present = False
            state.consumer_count = 0
            state.producer_active = False
            state.cleanup_pending = False
            state.status = "excluded"
            return

        state.consumer_count = info.consumer_count
        state.producer_active = info.producer_active
        if info.consumer_count > 0:
            state.cleanup_pending = True
            state.status = "cleanup_pending"
            return
        await self._async_delete_stream(state)

    async def _async_remove_owned_preloads(self) -> None:
        """Best-effort idempotent unload of stable manager preload names."""
        names = sorted(self._owned_preloads)
        self._owned_preloads.clear()
        await asyncio.gather(
            *(self._async_remove_owned_preload(name) for name in names)
        )

    async def _async_remove_owned_preload(self, stream_name: str) -> None:
        """Remove one preload without exposing transport error details."""
        state = next(
            (
                candidate
                for candidate in self._states.values()
                if candidate.stream_name == stream_name
            ),
            None,
        )
        try:
            await self.client.async_disable_preload(stream_name)
        except Go2RtcRequestError as err:
            if state is not None:
                state.status = f"preload_disable_{err.category}"
                state.cleanup_pending = True
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize transport detail
            if state is not None:
                state.status = "preload_disable_unexpected"
                state.cleanup_pending = True
            return
        if state is not None:
            state.preloaded = False
            state.producer_active = False

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

    def _camera_is_api_hidden(self, camera_id: str) -> bool:
        """Read the pre-visibility-sync API hint for startup race prevention."""
        for camera in (self.coordinator.data or {}).get("cameras") or []:
            if str(camera.get("id") or "") == camera_id:
                return bool(camera.get("hidden"))
        return False

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
        if not self._stopping:
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
