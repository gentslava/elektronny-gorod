"""Tests for A-61: `_collect_locks_for_place` не должен дублировать
`query_screens_settings` + `query_access_controls`.

Раньше:
- `_collect_cameras_for_place(place_id)` вызывал screens + access_controls.
- `_collect_locks_for_place(place_id)` вызывал screens + access_controls
  снова (+2 HTTP per place per refresh).

После A-61:
- Pre-fetch screens + access_controls в `_async_update_data` (один раз
  per place), передать в оба collectors как параметры.

Acceptance: 1 call для каждого endpoint per place. Поведение неизменно
(тесты A-57 / DND / visibility всё ещё pass).
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.user_agent import UserAgent


@pytest.fixture
def mock_api_counted():
    """Mock с реальным AsyncMock — call_count проверим напрямую."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": "P1", "address": "addr"},
        }])
        instance.query_balance = AsyncMock(return_value={})
        # Access controls: 1 AC с 1 entrance — чтобы locks builder отработал.
        instance.query_access_controls = AsyncMock(return_value=[
            {
                "id": "AC1",
                "name": "Door",
                "entrances": [
                    {
                        "id": "E1",
                        "externalCameraId": 100,
                        "name": "Подъезд 1",
                        "allowOpen": True,
                    }
                ],
            }
        ])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=[
            {"id": 200, "externalCameraId": None, "name": "City cam"}
        ])
        instance.query_screens_settings = AsyncMock(return_value={
            "screens": [
                {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
                {"type": "PUBLIC_CAMERAS", "entities": [], "hidden": []},
            ]
        })
        instance.query_dnd_settings = AsyncMock(return_value=[])
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


async def test_query_screens_settings_called_once_per_refresh(
    hass: HomeAssistant, mock_api_counted
):
    """A-61: screens settings вызывается 1 раз per place per refresh (раньше
    было 2 — дубликат из _collect_locks_for_place).

    Сравниваем с `query_places` (тоже 1 per refresh) — refactor success если
    отношение 1:1, независимо от количества refresh-циклов HA сделал на setup.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_counted.return_value
    refresh_count = instance.query_places.await_count
    assert instance.query_screens_settings.await_count == refresh_count, (
        f"screens settings должен быть == refresh_count={refresh_count} "
        f"(один раз per place per refresh), got {instance.query_screens_settings.await_count}"
    )


async def test_query_access_controls_called_once_per_refresh(
    hass: HomeAssistant, mock_api_counted
):
    """A-61: access_controls тоже не дублируется (cameras + locks delят один
    результат, ratio 1:1 c query_places)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance = mock_api_counted.return_value
    refresh_count = instance.query_places.await_count
    assert instance.query_access_controls.await_count == refresh_count, (
        f"access_controls должен быть == refresh_count={refresh_count} "
        f"(один раз per place per refresh), got {instance.query_access_controls.await_count}"
    )


async def test_data_still_correct_after_dedup(
    hass: HomeAssistant, mock_api_counted
):
    """Sanity: после dedup HTTP coordinator.data всё ещё содержит правильные
    cameras + locks (refactor не сломал бизнес-логику)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    # 1 intercom camera (от entrance.externalCameraId=100) + 1 public.
    assert len(data["cameras"]) == 2, (
        f"Expected 2 cameras (1 intercom + 1 public), got {len(data['cameras'])}"
    )
    # 1 lock (один entrance).
    assert len(data["locks"]) == 1, f"Expected 1 lock, got {len(data['locks'])}"
    lock = data["locks"][0]
    assert lock["place_id"] == "P1"
    assert lock["access_control_id"] == "AC1"
    assert lock["entrance_id"] == "E1"
    assert lock["name"] == "Подъезд 1"
