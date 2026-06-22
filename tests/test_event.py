"""Тесты `event`-сущности вызова домофона (event.py).

Проверяем без реального FCM — через ручной `async_dispatcher_send(SIGNAL_DOORBELL)`:
- сущность создаётся (одна на домофон AC1);
- `ring` стреляет с атрибутами; `ended` стреляет;
- payload для чужого AC игнорируется.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
    SIGNAL_DOORBELL,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

_UID = "elektronny_gorod_event_doorbell_P1_AC1"


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
            "place": {"id": "P1", "address": "addr"},
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
    entity_id = er.async_get(hass).async_get_entity_id("event", DOMAIN, _UID)
    assert entity_id is not None, "doorbell event entity не создана"
    return entity_id


async def test_doorbell_event_entity_created(hass: HomeAssistant, mock_api):
    """Одна event-сущность на домофон создаётся из coordinator.data['locks']."""
    entity_id = await _setup(hass)
    assert hass.states.get(entity_id) is not None


async def test_initial_state_baseline_no_call(hass: HomeAssistant, mock_api):
    """Первый запуск (нечего восстанавливать) → baseline `ended` = «нет вызова».

    Сущность не должна висеть в `unknown` — иначе пустая карточка «Неизвестно».
    """
    entity_id = await _setup(hass)
    state = hass.states.get(entity_id)
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["event_type"] == "ended"


async def test_ring_event_fires(hass: HomeAssistant, mock_api):
    """CALL_INCOMING-payload → event `ring` с атрибутами."""
    entity_id = await _setup(hass)
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"gate_name": "Подъезд 1", "apartment": "143",
                       "call_id": "C1", "allow_open": "true"},
    })
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ring"
    assert state.attributes["call_id"] == "C1"
    assert state.attributes["gate_name"] == "Подъезд 1"


async def test_ended_event_fires(hass: HomeAssistant, mock_api):
    """CALL_END_ANSWERED_MOBILE-payload → event `ended`."""
    entity_id = await _setup(hass)
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ended", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"reason": "answered_elsewhere", "call_id": "C1"},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["event_type"] == "ended"


async def test_other_ac_ignored(hass: HomeAssistant, mock_api):
    """Вызов для другого AC не стреляет на нашей сущности."""
    entity_id = await _setup(hass)
    before = hass.states.get(entity_id).state
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "OTHER",
        "attributes": {},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == before


async def test_other_place_same_ac_ignored(hass: HomeAssistant, mock_api):
    """Тот же AC, но другой place — не стреляет (нет cross-place leak)."""
    entity_id = await _setup(hass)
    before = hass.states.get(entity_id).state
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "OTHER_PLACE", "access_control_id": "AC1",
        "attributes": {},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == before
