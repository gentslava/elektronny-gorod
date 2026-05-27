"""Tests for A-69: TTL cache stream URL для подавления sequential batches.

Контекст (extends A-68):
- A-68 (future-pattern) дедупит **одновременные** stream_source() calls
  внутри одной таски (overlap во времени).
- A-69 (TTL cache) дедупит **sequential** calls с интервалом 0.5-30 сек
  (HA Stream retry-with-backoff, Frigate prefetch, WebRTC requests
  батчами через несколько сек).
- Production-лог 2026-05-27: видны 2 batch'а через 0.5-7 сек после
  первого fetch — каждый делает свежий HTTP + PUT + `update_source()`
  restart → суммарно «мигание видео».

Acceptance (A-69):
- Sequential call в пределах TTL → cache hit → 0 новых HTTP к operator,
  оба возвращают одинаковый URL.
- Sequential call после `_cached_ts + TTL` → fresh HTTP fetch.
- Empty URL failure НЕ кэшируется → next call делает fresh fetch.
- Cache per-camera независим (CamA не влияет на CamB).
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

CAM_A = "100"
CAM_B = "200"
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [
        {"id": int(CAM_A), "externalCameraId": None, "name": "CamA"},
        {"id": int(CAM_B), "externalCameraId": None, "name": "CamB"},
    ]


def _screens_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [
             {"id": int(CAM_A), "type": "PUBLIC_CAMERA", "order": 0},
             {"id": int(CAM_B), "type": "PUBLIC_CAMERA", "order": 1},
         ],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api_unique_urls():
    """API mock: unique URL per call — позволяет detect cache hit."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=_places())
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(return_value=[])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=_public_cameras())
        instance.query_screens_settings = AsyncMock(return_value=_screens_visible())
        instance.query_dnd_settings = AsyncMock(return_value=[])

        call_counter = {"n": 0}

        async def _stream_side_effect(camera_id: str):
            call_counter["n"] += 1
            return f"https://op.example/{camera_id}/token{call_counter['n']}.flv"

        instance.query_camera_stream = AsyncMock(side_effect=_stream_side_effect)
        instance.query_camera_snapshot = AsyncMock(return_value=b"\x89PNG\r\n")
        yield mock_cls


def _make_config_entry(*, use_go2rtc: bool = False) -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": use_go2rtc,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


def _get_camera_entity(hass: HomeAssistant, unique_id: str):
    from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
    component = hass.data.get(CAMERA_DOMAIN)
    if component is None:
        return None
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("camera", DOMAIN, unique_id)
    if entity_id is None:
        return None
    return component.get_entity(entity_id)


# ─── Test A: sequential calls в пределах TTL — cache hit ────────────────────


async def test_sequential_call_within_ttl_returns_cached(
    hass: HomeAssistant, mock_api_unique_urls
):
    """A-69: второй sequential call в пределах TTL → cache hit, 0 новых HTTP."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_unique_urls.return_value
    instance.query_camera_stream.reset_mock()

    # Первый call — fresh fetch.
    result1 = await cam.stream_source()
    assert instance.query_camera_stream.await_count == 1
    assert result1 is not None

    # Второй call — должен hit cache.
    result2 = await cam.stream_source()
    assert instance.query_camera_stream.await_count == 1, (
        f"Sequential call в пределах TTL должен hit cache, "
        f"got call_count={instance.query_camera_stream.await_count}"
    )
    assert result2 == result1, "Cache hit должен вернуть тот же URL"


# ─── Test B: после TTL expire — fresh fetch ─────────────────────────────────


async def test_sequential_call_after_ttl_fetches_fresh(
    hass: HomeAssistant, mock_api_unique_urls
):
    """A-69: после `_cached_ts + TTL` следующий call fetch свежий URL."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_unique_urls.return_value
    instance.query_camera_stream.reset_mock()

    # Первый call — fresh fetch.
    result1 = await cam.stream_source()
    assert instance.query_camera_stream.await_count == 1

    # Симулируем expire: вручную откатываем `_cached_stream_ts` на TTL+1 в прошлое.
    from custom_components.elektronny_gorod.camera import _STREAM_URL_TTL_SECONDS
    cam._cached_stream_ts = time.monotonic() - _STREAM_URL_TTL_SECONDS - 1

    # Второй call — должен fetch свежий.
    result2 = await cam.stream_source()
    assert instance.query_camera_stream.await_count == 2, (
        f"Call после TTL expire должен fetch свежий URL, "
        f"got call_count={instance.query_camera_stream.await_count}"
    )
    assert result2 != result1, "Fresh fetch → unique URL (mock returns sequence)"


# ─── Test C: empty URL fail НЕ кэшируется ───────────────────────────────────


async def test_empty_url_failure_not_cached(
    hass: HomeAssistant, mock_api_unique_urls
):
    """A-69: failure (operator вернул None/empty) НЕ кэшируется — next call
    делает fresh fetch (после восстановления operator)."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_unique_urls.return_value

    # Phase 1: API возвращает None.
    instance.query_camera_stream = AsyncMock(return_value=None)
    result1 = await cam.stream_source()
    assert result1 is None
    assert instance.query_camera_stream.await_count == 1

    # Phase 2: API recovered — возвращает URL.
    instance.query_camera_stream = AsyncMock(return_value="https://op.example/recovered.flv")
    result2 = await cam.stream_source()
    assert result2 == "https://op.example/recovered.flv", (
        "После recovery должен fetch fresh URL (failure не должен быть в cache)"
    )
    assert instance.query_camera_stream.await_count == 1, "новый AsyncMock counter"


# ─── Test D: cache per-camera независим ─────────────────────────────────────


async def test_cache_per_camera_independent(
    hass: HomeAssistant, mock_api_unique_urls
):
    """A-69: cache per-instance. CamA fetch не влияет на CamB cache state."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam_a = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    cam_b = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_B}")
    instance = mock_api_unique_urls.return_value
    instance.query_camera_stream.reset_mock()

    # CamA: первый fetch — fresh.
    a1 = await cam_a.stream_source()
    assert instance.query_camera_stream.await_count == 1

    # CamA: второй call — cache hit.
    a2 = await cam_a.stream_source()
    assert instance.query_camera_stream.await_count == 1
    assert a2 == a1

    # CamB: первый fetch — fresh (cache CamA не влияет).
    b1 = await cam_b.stream_source()
    assert instance.query_camera_stream.await_count == 2, (
        f"CamB первый fetch должен дать +1 HTTP, "
        f"got call_count={instance.query_camera_stream.await_count}"
    )
    assert b1 != a1, "Разные cameras → разные URL"

    # CamB: второй call — cache hit (независим от CamA cache).
    b2 = await cam_b.stream_source()
    assert instance.query_camera_stream.await_count == 2
    assert b2 == b1
