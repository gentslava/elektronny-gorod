"""Tests for durable event-history baseline, dedup and lifecycle."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.api import (
    CameraHistoryEvent,
    HistoryEvent,
    HistoryPage,
)
from custom_components.elektronny_gorod.const import DOMAIN


def test_watermark_baselines_then_emits_only_new_ids() -> None:
    """First page is a silent baseline; later overlap emits only unseen IDs."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    watermark = history.HistoryWatermark(max_ids=4)

    assert watermark.ingest("general", ["event-3", "event-2", "event-1"]) == ()
    assert watermark.ingest("general", ["event-4", "event-3", "event-2"]) == (
        "event-4",
    )
    assert watermark.ingest("general", ["event-4", "event-3"]) == ()


def test_watermark_round_trip_avoids_restart_duplicates_and_stays_bounded() -> None:
    """Persisted opaque IDs survive restart and keep a fixed storage bound."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    first = history.HistoryWatermark(max_ids=3)
    assert first.ingest("general", ["event-3", "event-2", "event-1"]) == ()

    restored = history.HistoryWatermark(first.as_dict(), max_ids=3)

    assert restored.ingest(
        "general", ["event-5", "event-4", "event-3"]
    ) == ("event-5", "event-4")
    assert restored.as_dict() == {
        "general": ["event-5", "event-4", "event-3"]
    }


@pytest.mark.asyncio
async def test_poller_baselines_then_emits_sanitized_whitelisted_event() -> None:
    """Initial events are silent; a later verified call event is dispatched."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    old = HistoryEvent(
        id="event-old",
        place_id="1001",
        event_type="accessControlCallAccepted",
        timestamp=1700000000,
        source_type="accessControl",
        source_id="2001",
    )
    new = HistoryEvent(
        id="event-new",
        place_id="1001",
        event_type="accessControlCallMissed",
        timestamp=1700000001,
        source_type="accessControl",
        source_id="2001",
    )
    unknown = HistoryEvent(
        id="event-unknown",
        place_id="1001",
        event_type="notRuntimeVerified",
        timestamp=1700000002,
        source_type="accessControl",
        source_id="2001",
    )
    api = SimpleNamespace(
        query_events=AsyncMock(
            side_effect=[
                HistoryPage(events=(old,), number=0, last=False),
                HistoryPage(events=(unknown, new, old), number=0, last=False),
            ]
        )
    )
    coordinator = SimpleNamespace(
        api=api,
        data={"places": [{"place": {"id": "1001"}}], "cameras": []},
    )
    emitted: list[dict] = []
    poller = history.HistoryPoller(
        coordinator,
        history.HistoryWatermark(),
        emitted.append,
    )

    assert await poller.async_poll() is True
    assert emitted == []
    assert api.query_events.await_args_list[0].args[0] == [1001]

    assert await poller.async_poll() is True
    assert emitted == [{
        "event_type": "call_missed",
        "event_id": "event-new",
        "occurred_at": 1700000001,
        "place_id": "1001",
        "source_type": "accessControl",
        "source_id": "2001",
    }]


@pytest.mark.asyncio
async def test_poller_baselines_then_emits_camera_motion_for_requested_id() -> None:
    """Motion routing uses requested camera ID and never the internal CameraID."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    old = CameraHistoryEvent(
        id="motion-old",
        camera_id="camera-public-1",
        backend_camera_id="internal-4001",
        timestamp=1700000000,
        duration=20,
        event_subject_id=126,
        available=True,
        goto_enabled=True,
    )
    new = CameraHistoryEvent(
        id="motion-new",
        camera_id="camera-public-1",
        backend_camera_id="internal-4001",
        timestamp=1700000001,
        duration=30,
        event_subject_id=126,
        available=True,
        goto_enabled=True,
    )
    api = SimpleNamespace(
        query_events=AsyncMock(
            return_value=HistoryPage(events=(), number=0, last=True)
        ),
        query_camera_events=AsyncMock(side_effect=[(old,), (new, old)]),
    )
    coordinator = SimpleNamespace(
        api=api,
        data={
            "places": [{"place": {"id": "1001"}}],
            "cameras": [
                {"id": "camera-public-1", "source": "public"},
                {"id": "camera-private-1", "source": "place"},
            ],
        },
    )
    emitted: list[dict] = []
    poller = history.HistoryPoller(
        coordinator,
        history.HistoryWatermark(),
        emitted.append,
    )

    assert await poller.async_poll() is True
    assert emitted == []

    assert await poller.async_poll() is True
    assert emitted == [{
        "event_type": "motion",
        "event_id": "motion-new",
        "occurred_at": 1700000001,
        "camera_id": "camera-public-1",
        "duration": 30,
        "recording_available": True,
    }]
    assert api.query_camera_events.await_count == 2


@pytest.mark.asyncio
async def test_camera_history_failure_does_not_block_general_history() -> None:
    """A tariff-gated camera endpoint cannot disable verified call history."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    old = HistoryEvent(
        id="event-old",
        place_id="1001",
        event_type="accessControlCallAccepted",
        timestamp=1700000000,
        source_type="accessControl",
        source_id="2001",
    )
    new = HistoryEvent(
        id="event-new",
        place_id="1001",
        event_type="accessControlCallAccepted",
        timestamp=1700000001,
        source_type="accessControl",
        source_id="2001",
    )
    api = SimpleNamespace(
        query_events=AsyncMock(
            side_effect=[
                HistoryPage(events=(old,), number=0, last=False),
                HistoryPage(events=(new, old), number=0, last=False),
            ]
        ),
        query_camera_events=AsyncMock(side_effect=RuntimeError("fixture failure")),
    )
    coordinator = SimpleNamespace(
        api=api,
        data={
            "places": [{"place": {"id": "1001"}}],
            "cameras": [{"id": "camera-public-1", "source": "public"}],
        },
    )
    emitted: list[dict] = []
    poller = history.HistoryPoller(
        coordinator,
        history.HistoryWatermark(),
        emitted.append,
    )

    assert await poller.async_poll() is True
    assert await poller.async_poll() is True
    assert [event["event_id"] for event in emitted] == ["event-new"]


@pytest.mark.asyncio
async def test_general_history_failure_isolated_from_integration() -> None:
    """History transport failure is optional and must not escape its poll task."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    api = SimpleNamespace(
        query_events=AsyncMock(side_effect=RuntimeError("fixture failure")),
    )
    coordinator = SimpleNamespace(
        api=api,
        data={"places": [{"place": {"id": "1001"}}], "cameras": []},
    )
    emitted: list[dict] = []
    poller = history.HistoryPoller(
        coordinator,
        history.HistoryWatermark(),
        emitted.append,
    )

    assert await poller.async_poll() is False
    assert emitted == []


@pytest.mark.asyncio
async def test_manager_loads_saves_and_unsubscribes(hass, monkeypatch) -> None:
    """Lifecycle restores opaque IDs, persists baseline and cancels polling."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    old = HistoryEvent(
        id="event-old",
        place_id="1001",
        event_type="accessControlCallAccepted",
        timestamp=1700000000,
        source_type="accessControl",
        source_id="2001",
    )
    api = SimpleNamespace(
        query_events=AsyncMock(
            return_value=HistoryPage(events=(old,), number=0, last=False)
        )
    )
    coordinator = SimpleNamespace(
        api=api,
        data={"places": [{"place": {"id": "1001"}}], "cameras": []},
    )
    store = SimpleNamespace(
        async_load=AsyncMock(return_value=None),
        async_save=AsyncMock(),
    )
    unsubscribe = MagicMock()
    track = MagicMock(return_value=unsubscribe)
    monkeypatch.setattr(
        history, "Store", lambda *_args, **_kwargs: store, raising=False
    )
    monkeypatch.setattr(history, "async_track_time_interval", track, raising=False)

    manager = history.HistoryManager(hass, "entry-1", coordinator)
    await manager.async_start()

    store.async_load.assert_awaited_once_with()
    store.async_save.assert_awaited_once_with(
        {"streams": {"general": ["event-old"]}}
    )
    track.assert_called_once()

    manager.async_stop()
    unsubscribe.assert_called_once_with()


@pytest.mark.asyncio
async def test_manager_skips_overlapping_poll(hass, monkeypatch) -> None:
    """A slow request cannot queue another complete poll behind its lock."""
    history = importlib.import_module(f"custom_components.{DOMAIN}.history")
    store = SimpleNamespace(
        async_load=AsyncMock(return_value=None),
        async_save=AsyncMock(),
    )
    monkeypatch.setattr(
        history, "Store", lambda *_args, **_kwargs: store, raising=False
    )
    manager = history.HistoryManager(hass, "entry-1", SimpleNamespace())

    poll_started = asyncio.Event()
    release_poll = asyncio.Event()

    async def slow_poll() -> bool:
        poll_started.set()
        await release_poll.wait()
        return True

    manager._poller = SimpleNamespace(async_poll=AsyncMock(side_effect=slow_poll))

    first_poll = hass.async_create_task(manager.async_poll())
    await poll_started.wait()

    assert await manager.async_poll() is False

    release_poll.set()
    assert await first_poll is True
    manager._poller.async_poll.assert_awaited_once_with()
