"""Timing, retry, registry-listener, and shutdown tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod import stream_manager as module
from custom_components.elektronny_gorod.const import (
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_USE_GO2RTC,
    DOMAIN,
)
from custom_components.elektronny_gorod.go2rtc import (
    Go2RtcRequestError,
    Go2RtcStreamInfo,
)
from custom_components.elektronny_gorod.stream_manager import CameraStreamManager


class _Schedules:
    def __init__(self) -> None:
        self.later: list[tuple[float, Callable, MagicMock]] = []
        self.intervals: list[tuple[object, Callable, MagicMock]] = []

    def call_later(self, hass, delay, action):
        seconds = delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay)
        cancel = MagicMock(name=f"cancel_later_{len(self.later)}")
        self.later.append((seconds, action, cancel))
        return cancel

    def track_interval(self, hass, action, interval, **kwargs):
        cancel = MagicMock(name="cancel_interval")
        self.intervals.append((interval, action, cancel))
        return cancel


def _setup(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    *,
    keep_warm: bool = True,
    stream_effect=None,
):
    schedules = _Schedules()
    monkeypatch.setattr(module, "async_call_later", schedules.call_later, raising=False)
    monkeypatch.setattr(
        module,
        "async_track_time_interval",
        schedules.track_interval,
        raising=False,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="stream-manager-entry",
        title="Test",
        data={
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://go2rtc:1984",
            CONF_GO2RTC_RTSP_HOST: "go2rtc.local",
            CONF_GO2RTC_USERNAME: None,
            CONF_GO2RTC_PASSWORD: None,
            CONF_GO2RTC_KEEP_WARM: keep_warm,
            CONF_GO2RTC_KEEP_WARM_HIDDEN: False,
        },
    )
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.data = {
        "cameras": [
            {"id": "100", "name": "Front door"},
            {"id": "200", "name": "Lift"},
        ]
    }
    if stream_effect is None:
        coordinator.get_camera_stream = AsyncMock(
            side_effect=lambda camera_id: f"https://operator/{camera_id}?token=OK"
        )
    else:
        coordinator.get_camera_stream = AsyncMock(side_effect=stream_effect)

    client = MagicMock()
    client.async_list_streams = AsyncMock(return_value={})
    client.async_list_preloads = AsyncMock(return_value=set())
    client.async_patch_stream = AsyncMock()
    client.async_enable_preload = AsyncMock()
    client.async_disable_preload = AsyncMock()
    client.async_get_stream = AsyncMock(return_value=None)
    client.async_delete_stream = AsyncMock()
    client.matches_configuration = MagicMock(return_value=True)
    client.rtsp_url = MagicMock(
        side_effect=lambda name, *, include_credentials: f"rtsp://go2rtc:8554/{name}"
    )
    manager = CameraStreamManager(
        hass=hass,
        entry=entry,
        coordinator=coordinator,
        client=client,
    )
    registry = er.async_get(hass)
    entries = []
    for camera_id in ("100", "200"):
        entries.append(
            registry.async_get_or_create(
                "camera",
                DOMAIN,
                f"{DOMAIN}_camera_{camera_id}",
                suggested_object_id=f"camera_{camera_id}",
                config_entry=entry,
            )
        )
    return manager, coordinator, client, schedules, entries


async def test_startup_offsets_are_deterministic_bounded_and_distinct(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, schedules, _ = _setup(hass, monkeypatch)

    await manager.async_start()

    offsets = [delay for delay, _, _ in schedules.later]
    assert len(offsets) == 2
    assert all(0 <= delay < 60 for delay in offsets)
    assert offsets[0] != offsets[1]
    client.async_patch_stream.assert_not_awaited()
    assert len(schedules.intervals) == 1
    assert schedules.intervals[0][0].total_seconds() == 60

    first_offsets = offsets.copy()
    await manager.async_stop()

    schedules.later.clear()
    schedules.intervals.clear()
    await manager.async_start()
    assert [delay for delay, _, _ in schedules.later] == first_offsets
    await manager.async_stop()


async def test_each_success_rebases_only_that_cameras_28m30s_due_time(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, _, schedules, _ = _setup(hass, monkeypatch)
    await manager.async_start()
    schedules.later.clear()
    completed = iter((100.0, 200.0))
    monkeypatch.setattr(module, "_monotonic", lambda: next(completed), raising=False)

    await manager.async_refresh("100", "ha_open")
    state_100 = manager.camera_state("100")
    state_200_before = manager.camera_state("200")
    await manager.async_refresh("200", "background")
    state_200 = manager.camera_state("200")

    assert [delay for delay, _, _ in schedules.later] == [1710.0, 1710.0]
    assert state_100.next_due_monotonic == 1810.0
    assert state_200_before.next_due_monotonic is not None
    assert state_200.next_due_monotonic == 1910.0
    await manager.async_stop()


async def test_slow_camera_does_not_delay_other_camera(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slow_release = asyncio.Event()

    async def stream(camera_id: str) -> str:
        if camera_id == "100":
            await slow_release.wait()
        return f"https://operator/{camera_id}?token={camera_id}"

    manager, _, client, _, _ = _setup(
        hass, monkeypatch, stream_effect=stream
    )
    await manager.async_start()
    slow = asyncio.create_task(manager.async_refresh("100", "background"))
    fast = asyncio.create_task(manager.async_refresh("200", "background"))

    fast_result = await asyncio.wait_for(fast, timeout=1)
    assert fast_result.proxied is True
    assert not slow.done()
    assert client.async_patch_stream.await_count == 1

    slow_release.set()
    await slow
    await manager.async_stop()


async def test_retry_delays_are_15_30_60_then_capped_at_300_seconds(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, schedules, _ = _setup(hass, monkeypatch)
    client.async_patch_stream.side_effect = Go2RtcRequestError(
        "patch", "http_500"
    )
    await manager.async_start()
    schedules.later.clear()

    for _ in range(7):
        result = await manager.async_refresh("100", "background")
        assert result.proxied is False

    assert [delay for delay, _, _ in schedules.later] == [
        15.0,
        30.0,
        60.0,
        120.0,
        240.0,
        300.0,
        300.0,
    ]
    await manager.async_stop()


async def test_success_resets_retry_and_returns_to_28m30s(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, schedules, _ = _setup(hass, monkeypatch)
    client.async_patch_stream.side_effect = [
        Go2RtcRequestError("patch", "http_500"),
        None,
    ]
    await manager.async_start()
    schedules.later.clear()

    await manager.async_refresh("100", "background")
    assert schedules.later[-1][0] == 15.0
    await manager.async_refresh("100", "background")

    state = manager.camera_state("100")
    assert state.failure_count == 0
    assert state.status == "ready"
    assert schedules.later[-1][0] == 1710.0
    await manager.async_stop()


async def test_registry_update_schedules_one_prompt_reconcile(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, _, schedules, entries = _setup(hass, monkeypatch)
    await manager.async_start()
    schedules.later.clear()

    for _ in range(2):
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": entries[0].entity_id},
        )
    await hass.async_block_till_done()

    assert [delay for delay, _, _ in schedules.later] == [0.0]
    await manager.async_stop()


async def test_stop_cancels_timer_listener_callbacks_and_inflight_tasks(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    never_release = asyncio.Event()

    async def stream(camera_id: str) -> str:
        started.set()
        await never_release.wait()
        return f"https://operator/{camera_id}"

    manager, _, _, schedules, _ = _setup(
        hass, monkeypatch, stream_effect=stream
    )
    await manager.async_start()
    waiter = asyncio.create_task(manager.async_refresh("100", "background"))
    await started.wait()

    await manager.async_stop()

    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert not manager._inflight
    for _, _, cancel in schedules.later:
        cancel.assert_called_once_with()
    for _, _, cancel in schedules.intervals:
        cancel.assert_called_once_with()
    assert manager._registry_unsub is None
    assert manager._prompt_reconcile_unsub is None

    # Idempotent lifecycle cleanup.
    await manager.async_stop()


async def test_start_does_not_schedule_background_work_when_keep_warm_is_off(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, coordinator, client, schedules, _ = _setup(
        hass,
        monkeypatch,
        keep_warm=False,
    )

    await manager.async_start()

    assert schedules.later == []
    assert schedules.intervals == []
    client.async_list_streams.assert_awaited_once_with()
    client.async_list_preloads.assert_awaited_once_with()
    client.async_disable_preload.assert_not_awaited()
    client.async_delete_stream.assert_not_awaited()
    coordinator.get_camera_stream.assert_not_awaited()
    await manager.async_stop()


async def test_start_with_keep_warm_off_removes_idle_stream_and_keeps_viewer(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, coordinator, client, schedules, _ = _setup(
        hass,
        monkeypatch,
        keep_warm=False,
    )
    idle = Go2RtcStreamInfo(
        producers=({},),
        consumer_count=0,
        producer_active=False,
    )
    viewed = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )
    client.async_list_streams.return_value = {
        "eg_100": idle,
        "eg_200": viewed,
    }
    client.async_list_preloads.return_value = {
        "eg_100",
        "eg_200",
        "unrelated_stream",
    }
    client.async_get_stream.side_effect = {
        "eg_100": idle,
        "eg_200": viewed,
    }.get

    await manager.async_start()

    assert {
        call.args[0]
        for call in client.async_disable_preload.await_args_list
    } == {"eg_100", "eg_200"}
    client.async_list_streams.assert_awaited_once_with()
    client.async_patch_stream.assert_not_awaited()
    client.async_delete_stream.assert_awaited_once_with("eg_100")
    coordinator.get_camera_stream.assert_not_awaited()
    assert schedules.later == []
    assert schedules.intervals == []
    await manager.async_stop()


async def test_stop_removes_adopted_preloads_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, _, _ = _setup(hass, monkeypatch)
    active = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )
    client.async_list_streams.return_value = {
        "eg_100": active,
        "eg_200": active,
    }
    client.async_list_preloads.return_value = {"eg_100", "eg_200"}
    await manager.async_start()

    await manager.async_stop()
    await manager.async_stop()

    assert client.async_disable_preload.await_count == 2
    assert {
        call.args[0]
        for call in client.async_disable_preload.await_args_list
    } == {"eg_100", "eg_200"}


async def test_stop_swallows_sanitized_preload_cleanup_failure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, _, _ = _setup(hass, monkeypatch)
    active = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )
    client.async_list_streams.return_value = {"eg_100": active}
    client.async_list_preloads.return_value = {"eg_100"}
    client.async_disable_preload.side_effect = Go2RtcRequestError(
        "preload_disable", "http_500"
    )
    await manager.async_start()

    await manager.async_stop()

    state = manager.camera_state("100")
    assert state is not None
    assert state.status == "preload_disable_http_500"
    assert state.cleanup_pending is True


async def test_policy_only_options_update_preserves_active_preloads(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, coordinator, client, schedules, _ = _setup(hass, monkeypatch)
    active = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )
    client.async_list_streams.return_value = {
        "eg_100": active,
        "eg_200": active,
    }
    client.async_list_preloads.return_value = {"eg_100", "eg_200"}
    await manager.async_start()
    client.async_disable_preload.reset_mock()
    client.async_enable_preload.reset_mock()
    client.async_patch_stream.reset_mock()
    coordinator.get_camera_stream.reset_mock()
    scheduled_before = list(manager._due_unsubs)

    hass.config_entries.async_update_entry(
        manager.entry,
        options={
            **manager.entry.options,
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://go2rtc:1984",
            CONF_GO2RTC_RTSP_HOST: "go2rtc.local",
            CONF_GO2RTC_USERNAME: "",
            CONF_GO2RTC_PASSWORD: "",
            CONF_GO2RTC_KEEP_WARM: True,
            CONF_GO2RTC_KEEP_WARM_HIDDEN: True,
        },
    )

    assert await manager.async_apply_entry_options() is True

    client.matches_configuration.assert_called_once_with(
        base_url="http://go2rtc:1984",
        rtsp_host="go2rtc.local",
        username=None,
        password=None,
    )
    client.async_disable_preload.assert_not_awaited()
    client.async_enable_preload.assert_not_awaited()
    client.async_patch_stream.assert_not_awaited()
    coordinator.get_camera_stream.assert_not_awaited()
    assert manager.keep_warm is True
    assert manager.keep_warm_hidden is True
    assert list(manager._due_unsubs) == scheduled_before
    assert len(schedules.intervals) == 1
    await manager.async_stop()


async def test_transport_change_requires_normal_config_entry_reload(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _, client, _, _ = _setup(hass, monkeypatch)
    await manager.async_start()
    client.matches_configuration.return_value = False
    hass.config_entries.async_update_entry(
        manager.entry,
        options={
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://other-go2rtc:1984",
            CONF_GO2RTC_RTSP_HOST: "other-go2rtc.local",
            CONF_GO2RTC_KEEP_WARM: True,
            CONF_GO2RTC_KEEP_WARM_HIDDEN: False,
        },
    )

    assert await manager.async_apply_entry_options() is False

    assert manager.keep_warm is True
    await manager.async_stop()


async def test_policy_update_off_cleans_preloads_without_operator_refresh(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, coordinator, client, schedules, _ = _setup(hass, monkeypatch)
    active = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )
    idle = Go2RtcStreamInfo(
        producers=({},),
        consumer_count=0,
        producer_active=False,
    )
    client.async_list_streams.return_value = {
        "eg_100": active,
        "eg_200": active,
    }
    client.async_list_preloads.return_value = {"eg_100", "eg_200"}
    client.async_get_stream.return_value = idle
    await manager.async_start()
    client.async_disable_preload.reset_mock()
    client.async_delete_stream.reset_mock()
    coordinator.get_camera_stream.reset_mock()
    client.async_patch_stream.reset_mock()

    await manager.async_update_policy(
        keep_warm=False,
        keep_warm_hidden=False,
    )

    assert manager._started is True
    assert manager.keep_warm is False
    assert manager._registry_unsub is None
    assert manager._reconcile_unsub is None
    assert manager._due_unsubs == {}
    assert client.async_disable_preload.await_count == 2
    assert client.async_delete_stream.await_count == 2
    coordinator.get_camera_stream.assert_not_awaited()
    client.async_patch_stream.assert_not_awaited()
    for _, _, cancel in schedules.intervals:
        cancel.assert_called_once_with()
    await manager.async_stop()


async def test_policy_update_on_schedules_missing_with_short_async_ramp(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, coordinator, client, schedules, _ = _setup(
        hass,
        monkeypatch,
        keep_warm=False,
    )
    await manager.async_start()
    coordinator.get_camera_stream.reset_mock()
    client.async_patch_stream.reset_mock()
    schedules.later.clear()
    schedules.intervals.clear()

    await manager.async_update_policy(
        keep_warm=True,
        keep_warm_hidden=False,
    )

    assert manager._started is True
    assert manager.keep_warm is True
    assert len(schedules.intervals) == 1
    assert len(schedules.later) == 2
    assert [delay for delay, _, _ in schedules.later] == [0.0, 0.5]
    coordinator.get_camera_stream.assert_not_awaited()
    client.async_patch_stream.assert_not_awaited()
    await manager.async_stop()


async def test_policy_off_during_background_mint_does_not_republish_stream(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mint_started = asyncio.Event()
    release_mint = asyncio.Event()

    async def slow_stream(camera_id: str) -> str:
        mint_started.set()
        await release_mint.wait()
        return f"https://operator/{camera_id}?token=late"

    manager, _, client, _, _ = _setup(
        hass,
        monkeypatch,
        stream_effect=slow_stream,
    )
    await manager.async_start()
    refresh = asyncio.create_task(
        manager.async_refresh("100", "background_due")
    )
    await mint_started.wait()

    await manager.async_update_policy(
        keep_warm=False,
        keep_warm_hidden=False,
    )
    release_mint.set()
    result = await refresh

    assert result.proxied is True
    client.async_patch_stream.assert_not_awaited()
    client.async_enable_preload.assert_not_awaited()
    await manager.async_stop()


async def test_policy_off_during_background_patch_cleans_late_stream(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_started = asyncio.Event()
    release_patch = asyncio.Event()

    async def slow_patch(name: str, source: str) -> None:
        patch_started.set()
        await release_patch.wait()

    manager, _, client, _, _ = _setup(hass, monkeypatch)
    client.async_patch_stream.side_effect = slow_patch
    client.async_get_stream.return_value = Go2RtcStreamInfo(
        producers=({},),
        consumer_count=0,
        producer_active=False,
    )
    await manager.async_start()
    refresh = asyncio.create_task(
        manager.async_refresh("100", "background_due")
    )
    await patch_started.wait()

    await manager.async_update_policy(
        keep_warm=False,
        keep_warm_hidden=False,
    )
    release_patch.set()
    await refresh

    client.async_enable_preload.assert_not_awaited()
    client.async_delete_stream.assert_awaited_once_with("eg_100")
    state = manager.camera_state("100")
    assert state is not None
    assert state.present is False
    assert state.status == "excluded"
    await manager.async_stop()
