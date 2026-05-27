"""Tests for A-70: cache invalidate on go2rtc PUT failure + revert A-66 update_source.

Контекст:
- A-66 ввёл `Stream.update_source()` после каждого go2rtc PUT для force
  restart worker (recovery после token expire).
- Production-лог 2026-05-27 показал: каждый restart прерывает video
  ~1-2 sec. Operator выдаёт unique URL/token на каждый запрос → cache
  miss (A-69 TTL 30s) = inevitable PUT = inevitable restart.
- Видео мигало каждые 30-60 сек в production setup с Frigate.

A-70 решение (revert update_source + invalidate on failure):
- Убрать `Stream.update_source()` — HA Stream lifecycle сам восстанавливается
  при producer fail через retry-backoff (10-30s). Trade-off: lag после
  token expire vs continuous flicker. Lag реже и acceptable.
- A-70: при go2rtc PUT failure (HTTP error) — invalidate `_cached_stream_url`
  чтобы next call сделал fresh fetch + PUT (faster recovery, не ждём TTL).

Acceptance:
- После успешного go2rtc PUT — `Stream.update_source()` НЕ вызывается.
- Если go2rtc PUT raises — cache invalidated → next call fetch fresh URL.
- Cache invalidation per-camera независим.
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [{"id": int(CAM_A), "externalCameraId": None, "name": "CamA"}]


def _screens_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [{"id": int(CAM_A), "type": "PUBLIC_CAMERA", "order": 0}],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api_with_go2rtc():
    """API mock + use_go2rtc=True (для теста PUT + update_source)."""
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


def _make_config_entry(*, use_go2rtc: bool = True) -> MockConfigEntry:
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


# ─── Test A: update_source НЕ вызывается после go2rtc PUT (revert A-66) ────


async def test_update_source_not_called_after_put(
    hass: HomeAssistant, mock_api_with_go2rtc
):
    """A-70 revert: после `_ensure_go2rtc_stream` PUT в go2rtc больше НЕ
    вызывается `Stream.update_source()` (A-66 partial revert)."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    assert cam is not None

    # Inject mock stream через private _stream attr (HA Camera internal).
    mock_stream = MagicMock()
    mock_stream.update_source = MagicMock()
    cam._stream = mock_stream

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ):
        await cam.stream_source()

    assert mock_stream.update_source.call_count == 0, (
        f"update_source НЕ должен вызываться после PUT (A-70 revert), "
        f"got call_count={mock_stream.update_source.call_count}"
    )


# ─── Test B: PUT failure → cache invalidated → next call fresh ──────────────


async def test_put_failure_invalidates_cache(
    hass: HomeAssistant, mock_api_with_go2rtc
):
    """A-70: go2rtc PUT failure → `_cached_stream_url = None` → next call
    fetch свежий URL (recovery sooner, не ждём TTL expire)."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_with_go2rtc.return_value
    instance.query_camera_stream.reset_mock()

    # PUT fails.
    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
        side_effect=RuntimeError("go2rtc down"),
    ):
        with pytest.raises(RuntimeError, match="go2rtc down"):
            await cam.stream_source()

    # Cache должен быть invalidated.
    assert cam._cached_stream_url is None, (
        f"PUT failure должен invalidate cache, got _cached_stream_url={cam._cached_stream_url!r}"
    )

    # Phase 2: PUT восстановился — next call fresh fetch.
    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ):
        result = await cam.stream_source()
        assert result is not None
        # 2 HTTP к operator (1 первый attempt + 1 recovery).
        assert instance.query_camera_stream.await_count == 2, (
            f"После cache invalidate next call должен fetch свежий URL, "
            f"got call_count={instance.query_camera_stream.await_count}"
        )


# ─── Test C: PUT success — cache populated normally ──────────────────────────


async def test_put_success_populates_cache(
    hass: HomeAssistant, mock_api_with_go2rtc
):
    """A-70 regression: successful PUT не trogaет cache invalidate path —
    cache populates как обычно (A-69 поведение сохранено)."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_with_go2rtc.return_value
    instance.query_camera_stream.reset_mock()

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ):
        await cam.stream_source()

    assert cam._cached_stream_url is not None, "Successful PUT должен populate cache"
    assert cam._cached_stream_ts > 0
