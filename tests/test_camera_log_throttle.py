"""Tests for A-65: log throttling от broken cameras.

Контекст:
- Broken hardware-камера возвращает `null` source URL (operator API
  отвечает 500/204/...).
- `camera.py:stream_source` логирует WARNING на каждый такой вызов.
- HA Stream worker делает retry-with-backoff → много вызовов подряд.
- Production-лог 2026-05-26: 10× WARNING от одной камеры за полчаса.
- Spam перегружает лог, юзер не отличает «временный fail» от «постоянной
  проблемы», маскирует другие WARNING.

Acceptance (A-65):
- 1й fail в серии → WARNING (как сейчас).
- 2й+ подряд → DEBUG (тихо).
- Reset counter на первый успешный response → следующий fail снова WARNING.
- Per-camera counters независимы.
"""
from __future__ import annotations

import json
import logging
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

BROKEN_CAMERA_ID = "999"
OTHER_CAMERA_ID = "888"
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [
        {"id": int(BROKEN_CAMERA_ID), "externalCameraId": None, "name": "Broken"},
        {"id": int(OTHER_CAMERA_ID), "externalCameraId": None, "name": "Other"},
    ]


def _screens_all_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [
             {"id": int(BROKEN_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 0},
             {"id": int(OTHER_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 1},
         ],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api_broken_camera():
    """Broken camera возвращает None из get_camera_stream."""
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
        instance.query_screens_settings = AsyncMock(return_value=_screens_all_visible())
        instance.query_dnd_settings = AsyncMock(return_value=[])

        # Default: broken camera returns None. Other camera returns URL.
        async def _stream_side_effect(camera_id: str):
            if str(camera_id) == BROKEN_CAMERA_ID:
                return None
            return "https://example/working.flv"

        instance.query_camera_stream = AsyncMock(side_effect=_stream_side_effect)
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
    from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
    component = hass.data.get(CAMERA_DOMAIN)
    if component is None:
        return None
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("camera", DOMAIN, unique_id)
    if entity_id is None:
        return None
    return component.get_entity(entity_id)


def _empty_url_records(caplog) -> list[logging.LogRecord]:
    """Filter caplog для записей про empty source URL."""
    return [
        r for r in caplog.records
        if "empty source stream url" in r.getMessage()
    ]


# ─── Test A: 1й fail = WARNING, 2й+ = DEBUG ─────────────────────────────────


async def test_first_empty_warning_subsequent_debug(
    hass: HomeAssistant, mock_api_broken_camera, caplog
):
    """A-65: первый empty URL → WARNING, последующие подряд → DEBUG."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    broken = _get_camera_entity(hass, f"{DOMAIN}_camera_{BROKEN_CAMERA_ID}")
    assert broken is not None

    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="custom_components.elektronny_gorod.const")

    # First call → WARNING
    assert await broken.stream_source() is None
    # Subsequent 5 calls → DEBUG
    for _ in range(5):
        assert await broken.stream_source() is None

    records = _empty_url_records(caplog)
    assert len(records) == 6, f"Ожидаем 6 записей про empty source, got {len(records)}"
    assert records[0].levelno == logging.WARNING, (
        f"1й fail должен быть WARNING, got {records[0].levelname}"
    )
    for i, rec in enumerate(records[1:], start=2):
        assert rec.levelno == logging.DEBUG, (
            f"{i}й подряд fail должен быть DEBUG, got {rec.levelname}"
        )


# ─── Test B: reset counter после success ────────────────────────────────────


async def test_success_resets_counter(
    hass: HomeAssistant, mock_api_broken_camera, caplog
):
    """A-65: после первого успешного stream URL counter сбрасывается.
    Следующий fail снова → WARNING (не DEBUG)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_broken_camera.return_value
    broken = _get_camera_entity(hass, f"{DOMAIN}_camera_{BROKEN_CAMERA_ID}")
    assert broken is not None

    caplog.set_level(logging.DEBUG, logger="custom_components.elektronny_gorod.const")

    # Phase 1: 3 fail подряд (1 WARNING + 2 DEBUG)
    for _ in range(3):
        await broken.stream_source()

    # Phase 2: camera «починилась» — возвращает URL
    instance.query_camera_stream = AsyncMock(return_value="https://example/recovered.flv")
    result = await broken.stream_source()
    assert result == "https://example/recovered.flv"

    # Phase 3: камера снова сломалась. Invalidate A-69 cache, чтобы fail
    # path сработал (без invalidate cache hit вернул бы Phase 2 URL).
    instance.query_camera_stream = AsyncMock(return_value=None)
    broken._cached_stream_url = None
    caplog.clear()
    assert await broken.stream_source() is None

    # Должна быть 1 WARNING — counter был сброшен.
    records = _empty_url_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING, (
        f"После recovery следующий fail должен быть WARNING, got {records[0].levelname}"
    )


# ─── Test C: per-camera counters независимы ─────────────────────────────────


async def test_per_camera_counters_independent(
    hass: HomeAssistant, mock_api_broken_camera, caplog
):
    """A-65: counter — per-instance, разные камеры не влияют друг на друга.

    Если broken camera уже в DEBUG-режиме (counter>=1), а другая broken
    camera только что failed первый раз — она должна получить WARNING.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_broken_camera.return_value
    broken = _get_camera_entity(hass, f"{DOMAIN}_camera_{BROKEN_CAMERA_ID}")
    other = _get_camera_entity(hass, f"{DOMAIN}_camera_{OTHER_CAMERA_ID}")

    caplog.set_level(logging.DEBUG, logger="custom_components.elektronny_gorod.const")

    # Trigger broken несколько раз — counter > 1.
    for _ in range(3):
        await broken.stream_source()

    # Switch other camera в broken mode.
    instance.query_camera_stream = AsyncMock(return_value=None)
    caplog.clear()
    assert await other.stream_source() is None

    records = _empty_url_records(caplog)
    assert len(records) == 1
    # other camera должна получить WARNING — её собственный counter==0.
    assert records[0].levelno == logging.WARNING, (
        f"Другая broken camera независимо должна выдать WARNING, "
        f"got {records[0].levelname}"
    )
