"""Core refresh and concurrency contract for CameraStreamManager."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.go2rtc import Go2RtcRequestError
from custom_components.elektronny_gorod.stream_manager import CameraStreamManager


def _manager(
    *,
    stream_side_effect=None,
    client: MagicMock | None = None,
):
    coordinator = MagicMock()
    coordinator.data = {
        "cameras": [
            {"id": "100", "name": "Front door"},
            {"id": "200", "name": "Lift"},
        ]
    }
    if stream_side_effect is None:
        coordinator.get_camera_stream = AsyncMock(
            return_value="https://operator/100?token=TOKEN_1"
        )
    elif isinstance(stream_side_effect, BaseException):
        coordinator.get_camera_stream = AsyncMock(side_effect=stream_side_effect)
    else:
        coordinator.get_camera_stream = AsyncMock(side_effect=stream_side_effect)

    if client is None:
        client = MagicMock()
        client.async_patch_stream = AsyncMock()
        client.async_enable_preload = AsyncMock()
        client.rtsp_url = MagicMock(
            side_effect=lambda name, *, include_credentials: (
                f"rtsp://user:pass@go2rtc:8554/{name}"
                if include_credentials
                else f"rtsp://go2rtc:8554/{name}"
            )
        )

    entry = SimpleNamespace(
        entry_id="entry-1",
        data={},
        options={},
    )
    hass = MagicMock()
    hass.async_create_task.side_effect = (
        lambda coro, **kwargs: asyncio.create_task(
            coro,
            name=kwargs.get("name"),
        )
    )
    manager = CameraStreamManager(
        hass=hass,
        entry=entry,
        coordinator=coordinator,
        client=client,
    )
    manager.is_camera_publishable = MagicMock(return_value=True)
    return manager, coordinator, client


async def test_refresh_mints_and_patches_complete_source() -> None:
    manager, coordinator, client = _manager()

    result = await manager.async_refresh("100", "ha_open")

    coordinator.get_camera_stream.assert_awaited_once_with("100")
    client.async_patch_stream.assert_awaited_once_with(
        "eg_100",
        "ffmpeg:https://operator/100?token=TOKEN_1"
        "#video=copy#audio=aac#audio=opus",
    )
    client.rtsp_url.assert_called_once_with(
        "eg_100", include_credentials=True
    )
    assert result.url == "rtsp://user:pass@go2rtc:8554/eg_100"
    assert result.proxied is True

    state = manager.camera_state("100")
    assert state is not None
    assert state.camera_id == "100"
    assert state.stream_name == "eg_100"
    assert state.display_name == "Front door"
    assert state.present is True
    assert state.status == "ready"
    assert state.last_success is not None
    assert state.last_success_monotonic is not None
    assert state.preloaded is False
    assert state.producer_active is False
    assert "TOKEN_1" not in repr(state)


async def test_eligible_refresh_patches_then_enables_preload() -> None:
    manager, coordinator, client = _manager()
    events: list[str] = []
    manager.keep_warm = True
    manager.is_camera_eligible = MagicMock(return_value=True)
    coordinator.get_camera_stream.side_effect = lambda camera_id: (
        events.append("mint")
        or f"https://operator/{camera_id}?token=FRESH"
    )
    client.async_patch_stream.side_effect = (
        lambda *_args: events.append("patch")
    )
    client.async_enable_preload.side_effect = (
        lambda *_args: events.append("preload")
    )

    result = await manager.async_refresh("100", "background")

    assert events == ["mint", "patch", "preload"]
    assert result.proxied is True
    client.async_enable_preload.assert_awaited_once_with("eg_100")
    state = manager.camera_state("100")
    assert state is not None
    assert state.eligible is True
    assert state.present is True
    assert state.preloaded is True
    assert state.producer_active is True
    assert state.status == "ready"


async def test_active_preload_refreshes_source_without_rearming() -> None:
    manager, coordinator, client = _manager()
    manager.keep_warm = True
    manager.is_camera_eligible = MagicMock(return_value=True)
    state = manager._state_for("100")
    state.preloaded = True
    state.producer_active = True

    result = await manager.async_refresh("100", "background_due")

    assert result.proxied is True
    coordinator.get_camera_stream.assert_awaited_once_with("100")
    client.async_patch_stream.assert_awaited_once()
    client.async_enable_preload.assert_not_awaited()
    assert manager.camera_state("100").preloaded is True
    assert manager.camera_state("100").producer_active is True


async def test_preload_failure_retries_with_a_new_operator_url() -> None:
    manager, coordinator, client = _manager(
        stream_side_effect=[
            "https://operator/100?token=FIRST",
            "https://operator/100?token=SECOND",
        ]
    )
    manager.keep_warm = True
    manager._started = True
    manager.is_camera_eligible = MagicMock(return_value=True)
    manager._schedule_due = MagicMock()
    client.async_enable_preload.side_effect = [
        Go2RtcRequestError("preload_enable", "http_500"),
        None,
    ]

    first = await manager.async_refresh("100", "background")
    second = await manager.async_refresh("100", "retry")

    assert first.url == "https://operator/100?token=FIRST"
    assert first.proxied is False
    assert second.proxied is True
    assert coordinator.get_camera_stream.await_count == 2
    assert client.async_patch_stream.await_count == 2
    assert client.async_enable_preload.await_count == 2
    assert "FIRST" in client.async_patch_stream.await_args_list[0].args[1]
    assert "SECOND" in client.async_patch_stream.await_args_list[1].args[1]
    manager._schedule_due.assert_any_call("100", 15.0)
    state = manager.camera_state("100")
    assert state is not None
    assert state.failure_count == 0
    assert state.preloaded is True
    assert state.producer_active is True


async def test_refresh_notifies_sanitized_state_subscribers() -> None:
    manager, _, _ = _manager()
    snapshots = []

    unsubscribe = manager.async_subscribe(
        lambda: snapshots.append(manager.camera_states())
    )
    await manager.async_refresh("100", "ha_open")

    assert len(snapshots) == 1
    assert snapshots[0][0].status == "ready"
    assert "TOKEN_1" not in repr(snapshots)

    unsubscribe()
    await manager.async_refresh("100", "ha_open")
    assert len(snapshots) == 1


async def test_concurrent_reasons_share_one_operator_request_and_patch() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_stream(camera_id: str) -> str:
        started.set()
        await release.wait()
        return f"https://operator/{camera_id}?token=SHARED"

    manager, coordinator, client = _manager(stream_side_effect=delayed_stream)

    calls = [
        asyncio.create_task(manager.async_refresh("100", "background")),
        asyncio.create_task(manager.async_refresh("100", "ha_open")),
        asyncio.create_task(manager.async_refresh("100", "recovery")),
    ]
    await started.wait()
    release.set()
    results = await asyncio.gather(*calls)

    assert coordinator.get_camera_stream.await_count == 1
    assert client.async_patch_stream.await_count == 1
    assert results[0] == results[1] == results[2]


async def test_concurrent_eligible_reasons_share_one_preload_activation() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_stream(camera_id: str) -> str:
        started.set()
        await release.wait()
        return f"https://operator/{camera_id}?token=SHARED"

    manager, coordinator, client = _manager(stream_side_effect=delayed_stream)
    manager.keep_warm = True
    manager.is_camera_eligible = MagicMock(return_value=True)
    calls = [
        asyncio.create_task(manager.async_refresh("100", "background")),
        asyncio.create_task(manager.async_refresh("100", "ha_open")),
        asyncio.create_task(manager.async_refresh("100", "recovery")),
    ]
    await started.wait()
    release.set()

    results = await asyncio.gather(*calls)

    assert coordinator.get_camera_stream.await_count == 1
    assert client.async_patch_stream.await_count == 1
    assert client.async_enable_preload.await_count == 1
    assert results[0] == results[1] == results[2]


async def test_sequential_refreshes_mint_separate_operator_urls() -> None:
    manager, coordinator, client = _manager(
        stream_side_effect=[
            "https://operator/100?token=FIRST",
            "https://operator/100?token=SECOND",
        ]
    )

    first = await manager.async_refresh("100", "ha_open")
    second = await manager.async_refresh("100", "ha_open")

    assert first.proxied is True
    assert second.proxied is True
    assert coordinator.get_camera_stream.await_count == 2
    assert client.async_patch_stream.await_count == 2
    patched_sources = [
        call.args[1] for call in client.async_patch_stream.await_args_list
    ]
    assert "FIRST" in patched_sources[0]
    assert "SECOND" in patched_sources[1]


async def test_empty_operator_url_records_failure_without_patch() -> None:
    manager, _, client = _manager(stream_side_effect=[None])

    result = await manager.async_refresh("100", "background")

    assert result.url is None
    assert result.proxied is False
    client.async_patch_stream.assert_not_awaited()
    state = manager.camera_state("100")
    assert state is not None
    assert state.present is False
    assert state.failure_count == 1
    assert state.status == "empty_source"


async def test_patch_failure_returns_direct_fallback_for_ha_open() -> None:
    direct_url = "https://operator/100?token=FALLBACK_SECRET"
    client = MagicMock()
    client.async_patch_stream = AsyncMock(
        side_effect=Go2RtcRequestError("patch", "http_500")
    )
    client.rtsp_url = MagicMock()
    manager, _, _ = _manager(
        stream_side_effect=[direct_url],
        client=client,
    )

    result = await manager.async_refresh("100", "ha_open")

    assert result.url == direct_url
    assert result.proxied is False
    client.rtsp_url.assert_not_called()
    state = manager.camera_state("100")
    assert state is not None
    assert state.status == "patch_http_500"
    assert state.failure_count == 1
    assert "FALLBACK_SECRET" not in repr(state)


async def test_cancelled_waiter_does_not_cancel_shared_refresh() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_stream(camera_id: str) -> str:
        started.set()
        await release.wait()
        return f"https://operator/{camera_id}?token=SURVIVES"

    manager, coordinator, client = _manager(stream_side_effect=delayed_stream)
    cancelled_waiter = asyncio.create_task(
        manager.async_refresh("100", "background")
    )
    await started.wait()
    surviving_waiter = asyncio.create_task(
        manager.async_refresh("100", "ha_open")
    )

    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter
    release.set()
    result = await asyncio.wait_for(surviving_waiter, timeout=1)

    assert result.proxied is True
    assert coordinator.get_camera_stream.await_count == 1
    assert client.async_patch_stream.await_count == 1


async def test_different_cameras_refresh_independently() -> None:
    release = {"100": asyncio.Event(), "200": asyncio.Event()}

    async def delayed_stream(camera_id: str) -> str:
        await release[camera_id].wait()
        return f"https://operator/{camera_id}?token={camera_id}"

    manager, coordinator, client = _manager(stream_side_effect=delayed_stream)
    first = asyncio.create_task(manager.async_refresh("100", "background"))
    second = asyncio.create_task(manager.async_refresh("200", "background"))
    await asyncio.sleep(0)

    release["200"].set()
    result_200 = await asyncio.wait_for(second, timeout=1)
    assert result_200.url.endswith("/eg_200")
    assert not first.done()

    release["100"].set()
    result_100 = await asyncio.wait_for(first, timeout=1)
    assert result_100.url.endswith("/eg_100")
    assert coordinator.get_camera_stream.await_count == 2
    assert client.async_patch_stream.await_count == 2


async def test_operator_error_is_recorded_without_exception_details() -> None:
    manager, _, client = _manager(
        stream_side_effect=RuntimeError(
            "https://operator/source?token=OPERATOR_SECRET"
        )
    )

    result = await manager.async_refresh("100", "background")

    assert result.url is None
    assert result.proxied is False
    client.async_patch_stream.assert_not_awaited()
    state = manager.camera_state("100")
    assert state is not None
    assert state.status == "operator_error"
    assert "OPERATOR_SECRET" not in repr(state)
