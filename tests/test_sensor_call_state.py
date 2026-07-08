"""Тесты `sensor.*_call_state` (sensor.py).

Сущность push-driven: слушает bus-событие `EVENT_CALL_STATE` (его шлёт
DoorbellCallController). Проверяем без SIP — ручным `hass.bus.async_fire`:
- одна сущность на домофон (P1/AC1), дефолт `idle`;
- состояние и атрибуты отражаются при совпадении place/AC;
- payload для чужого AC игнорируется;
- `started_at` ставится на `active` и снимается на `ended`.
"""
from __future__ import annotations

import json
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
    EVENT_CALL_STATE,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

_UID = "elektronny_gorod_call_state_P1_AC1"


@pytest.fixture
def mock_api():
    """Mock API: 1 place, 1 AC с 1 entrance → coordinator.data['locks'] = 1 lock."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        inst = mock_cls.return_value
        inst.http = AsyncMock()
        inst.http.user_agent = AsyncMock()
        inst.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": "P1", "address": {"apartment": "57", "house": "20"}},
        }])
        inst.query_balance = AsyncMock(return_value={})
        inst.query_access_controls = AsyncMock(return_value=[{
            "id": "AC1",
            "name": "Door",
            "entrances": [{
                "id": "E1", "externalCameraId": 100, "name": "Подъезд 1", "allowOpen": True,
            }],
        }])
        inst.query_cameras = AsyncMock(return_value=[])
        inst.query_public_cameras = AsyncMock(return_value=[])
        inst.query_screens_settings = AsyncMock(return_value={"screens": []})
        inst.query_dnd_settings = AsyncMock(return_value=[])
        yield mock_cls


def _entry() -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN, version=3, unique_id="test_S1", title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1", CONF_REFRESH_TOKEN: "R1", CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1", "subscriber_id": "S1", "use_go2rtc": False,
            "go2rtc_base_url": "http://127.0.0.1:1984", "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


async def _setup(hass: HomeAssistant) -> str:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, _UID)
    assert entity_id is not None, "call_state sensor не создан"
    return entity_id


async def test_call_state_entity_created(hass: HomeAssistant, mock_api):
    """Одна call_state-сущность на домофон создаётся из coordinator.data['locks']."""
    entity_id = await _setup(hass)
    assert hass.states.get(entity_id) is not None


async def test_default_idle(hass: HomeAssistant, mock_api):
    """До любого вызова состояние = idle (не unknown/unavailable)."""
    entity_id = await _setup(hass)
    assert hass.states.get(entity_id).state == "idle"


async def test_ringing_then_active_reflected(hass: HomeAssistant, mock_api):
    """EVENT_CALL_STATE для нашего домофона → state отражается."""
    entity_id = await _setup(hass)
    hass.bus.async_fire(EVENT_CALL_STATE, {
        "place_id": "P1", "access_control_id": "AC1", "state": "ringing",
        "call_id": "C1", "started_at": None,
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "ringing"

    hass.bus.async_fire(EVENT_CALL_STATE, {
        "place_id": "P1", "access_control_id": "AC1", "state": "active",
        "call_id": "C1", "started_at": "2026-06-25T10:00:00+00:00",
    })
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "active"
    assert state.attributes["call_id"] == "C1"
    assert state.attributes["started_at"] == "2026-06-25T10:00:00+00:00"
    assert state.attributes["intercom_name"]  # имя домофона присутствует


async def test_ended_clears_started_at(hass: HomeAssistant, mock_api):
    """На ended state=ended и started_at снимается."""
    entity_id = await _setup(hass)
    hass.bus.async_fire(EVENT_CALL_STATE, {
        "place_id": "P1", "access_control_id": "AC1", "state": "active",
        "call_id": "C1", "started_at": "2026-06-25T10:00:00+00:00",
    })
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_CALL_STATE, {
        "place_id": "P1", "access_control_id": "AC1", "state": "ended",
        "call_id": "C1", "started_at": None,
    })
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "ended"
    assert state.attributes["started_at"] is None


async def test_other_ac_ignored(hass: HomeAssistant, mock_api):
    """Вызов другого домофона (AC) не меняет наше состояние."""
    entity_id = await _setup(hass)
    before = hass.states.get(entity_id).state
    hass.bus.async_fire(EVENT_CALL_STATE, {
        "place_id": "P1", "access_control_id": "OTHER", "state": "ringing",
        "call_id": "C9", "started_at": None,
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == before
