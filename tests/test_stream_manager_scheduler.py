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
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    DOMAIN,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcRequestError
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
    client.async_patch_stream = AsyncMock()
    client.async_delete_stream = AsyncMock()
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


async def test_start_is_inert_when_keep_warm_is_off(
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
    client.async_list_streams.assert_not_awaited()
    coordinator.get_camera_stream.assert_not_awaited()
    await manager.async_stop()
