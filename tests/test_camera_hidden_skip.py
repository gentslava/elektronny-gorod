"""Tests for A-63: skip stream/snapshot если entity скрыта в HA UI.

Контекст:
- HA core + downstream-интеграции (frigate, webrtc preview, advanced
  lovelace) могут вызывать `stream_source()` для всех зарегистрированных
  camera entities — включая те, что `hidden_by != None`.
- Hidden камера в UI юзеру не видна → fetcher live stream бесполезен.
- Production-лог 2026-05-26 показал такие prefetch.

Skip когда `registry_entry.hidden_by is not None` (любой reason):
- INTEGRATION: наш `_sync_visibility` пометил на основе API hidden=True;
- USER: юзер выключил «Показывать на панели» через HA UI;
- DEVICE: каскад от device-level (не используем сейчас).

Юзер может easily включить обратно — toggle «Показывать на панели» в
entity-edit page (HA устанавливает `hidden_by=None`).
"""
from __future__ import annotations

import json
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

VISIBLE_CAMERA_ID = "111"
HIDDEN_CAMERA_ID = "222"
PLACE_ID = "P1"


def _screens_with_hidden() -> dict[str, Any]:
    return {
        "screens": [
            {
                "type": "PUBLIC_CAMERAS",
                "entities": [
                    {"id": int(VISIBLE_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 0},
                ],
                "hidden": [
                    {"id": int(HIDDEN_CAMERA_ID), "type": "PUBLIC_CAMERA"},
                ],
            },
            {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
        ]
    }


def _places() -> list[dict[str, Any]]:
    return [
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }
    ]


def _public_cameras() -> list[dict[str, Any]]:
    return [
        {"id": int(VISIBLE_CAMERA_ID), "externalCameraId": None, "name": "Двор"},
        {"id": int(HIDDEN_CAMERA_ID), "externalCameraId": None, "name": "Скрытая"},
    ]


@pytest.fixture
def mock_api_with_streams():
    """API mock + AsyncMock на get_camera_stream/snapshot — будем проверять call_count."""
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
        instance.query_screens_settings = AsyncMock(return_value=_screens_with_hidden())
        instance.query_dnd_settings = AsyncMock(return_value=[])
        # Эти два — реальная цель проверки.
        instance.query_camera_stream = AsyncMock(return_value="https://example/stream.flv")
        instance.query_camera_snapshot = AsyncMock(return_value=b"\x89PNG\r\n")
        yield mock_cls


def _make_config_entry() -> MockConfigEntry:
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
            "use_go2rtc": False,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


def _get_camera_entity(hass: HomeAssistant, unique_id: str):
    """Возвращает camera entity instance из platform component."""
    from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN

    component = hass.data.get(CAMERA_DOMAIN)
    if component is None:
        return None
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("camera", DOMAIN, unique_id)
    if entity_id is None:
        return None
    return component.get_entity(entity_id)


# ─── Test A: hidden camera — stream_source returns None, no API call ─────────


async def test_stream_source_returns_url_for_hidden_camera_v3(
    hass: HomeAssistant, mock_api_with_streams
):
    """A-66v3: hidden_by=INTEGRATION → stream_source() ВСЁ РАВНО возвращает URL.

    Skip для stream_source убран (см. A-66v3): HA Stream worker pin-ится к
    RTSP URL который мы вернули один раз; повторно stream_source не
    вызывается. Если возвращаем None после того как stream была активна,
    worker зависает в retry-loop. Skip применяется ТОЛЬКО к snapshot
    (async_camera_image — on-demand, lifecycle проблем нет).
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_with_streams.return_value
    instance.query_camera_stream.reset_mock()

    hidden_camera = _get_camera_entity(
        hass, f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    )
    assert hidden_camera is not None

    # Precondition.
    registry = er.async_get(hass)
    assert registry.async_get(hidden_camera.entity_id).hidden_by == er.RegistryEntryHider.INTEGRATION

    result = await hidden_camera.stream_source()
    assert result == "https://example/stream.flv", (
        f"v3: hidden camera stream_source ВСЁ РАВНО возвращает URL (HA Stream "
        f"lifecycle requirement), got {result!r}"
    )
    assert instance.query_camera_stream.await_count == 1


# ─── Test B: visible camera — поведение не меняется ──────────────────────────


async def test_stream_source_visible_camera_still_works(
    hass: HomeAssistant, mock_api_with_streams
):
    """Regression: visible camera (hidden_by=None) всё ещё получает stream URL."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_with_streams.return_value
    instance.query_camera_stream.reset_mock()

    visible_camera = _get_camera_entity(
        hass, f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    )
    assert visible_camera is not None

    registry = er.async_get(hass)
    reg_entry = registry.async_get(visible_camera.entity_id)
    assert reg_entry.hidden_by is None, (
        f"precondition: visible camera hidden_by должен быть None, "
        f"got {reg_entry.hidden_by!r}"
    )

    result = await visible_camera.stream_source()
    assert result == "https://example/stream.flv", (
        f"visible camera stream_source должен вернуть URL, got {result!r}"
    )
    assert instance.query_camera_stream.await_count == 1


# ─── Test C: hidden camera — snapshot тоже skip ──────────────────────────────


async def test_async_camera_image_returns_none_for_hidden_camera(
    hass: HomeAssistant, mock_api_with_streams
):
    """A-63: hidden_by=INTEGRATION → async_camera_image() тоже возвращает None
    БЕЗ вызова coordinator.get_camera_snapshot → API."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_with_streams.return_value
    instance.query_camera_snapshot.reset_mock()

    hidden_camera = _get_camera_entity(
        hass, f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    )
    assert hidden_camera is not None

    result = await hidden_camera.async_camera_image()
    assert result is None, f"async_camera_image() для hidden должен вернуть None, got {result!r}"
    assert instance.query_camera_snapshot.await_count == 0, (
        f"query_camera_snapshot НЕ должен вызываться для hidden camera, "
        f"got call_count={instance.query_camera_snapshot.await_count}"
    )


# ─── Test D: USER-hidden — skip (юзер отключил «Показывать на панели») ──────


async def test_stream_source_returns_url_for_user_hidden_camera_v3(
    hass: HomeAssistant, mock_api_with_streams
):
    """A-66v3: USER hidden_by → stream_source() всё равно возвращает URL
    (HA Stream lifecycle requirement). Snapshot skip — отдельно."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    visible_uid = f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    visible_entity_id = registry.async_get_entity_id("camera", DOMAIN, visible_uid)
    # Юзер выключил «Показывать на панели».
    registry.async_update_entity(
        visible_entity_id, hidden_by=er.RegistryEntryHider.USER
    )

    instance = mock_api_with_streams.return_value
    instance.query_camera_stream.reset_mock()

    visible_camera = _get_camera_entity(hass, visible_uid)
    result = await visible_camera.stream_source()
    assert result == "https://example/stream.flv", (
        f"v3: USER-hidden stream_source всё равно возвращает URL, got {result!r}"
    )
    assert instance.query_camera_stream.await_count == 1


# ─── Test E: юзер включил «Показывать на панели» для INTEGRATION-hidden → отдаём


async def test_stream_source_works_after_user_show_override(
    hass: HomeAssistant, mock_api_with_streams
):
    """A-63: юзер развернул hidden-в-приложении камеру в HA UI и включил
    «Показывать на панели» (hidden_by=None). Видео ДОЛЖНО работать —
    это явный user choice (отдаёт пока наш sync не вернёт INTEGRATION,
    что само по себе отдельная UX-проблема — см. follow-up в audit)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    hidden_entity_id = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    # Precondition: после setup наш sync поставил INTEGRATION.
    assert registry.async_get(hidden_entity_id).hidden_by == er.RegistryEntryHider.INTEGRATION

    # Юзер включил «Показывать на панели» в HA UI.
    registry.async_update_entity(hidden_entity_id, hidden_by=None)

    instance = mock_api_with_streams.return_value
    instance.query_camera_stream.reset_mock()

    hidden_camera = _get_camera_entity(hass, hidden_uid)
    result = await hidden_camera.stream_source()
    assert result == "https://example/stream.flv", (
        f"После user «Показывать на панели» stream должен работать, got {result!r}"
    )
    assert instance.query_camera_stream.await_count == 1
