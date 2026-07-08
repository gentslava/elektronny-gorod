"""Тесты `event`-сущности вызова домофона (event.py).

Проверяем без реального FCM — через ручной `async_dispatcher_send(SIGNAL_DOORBELL)`:
- сущность создаётся (одна на домофон AC1);
- `ring` стреляет с атрибутами; `ended` стреляет;
- payload для чужого AC игнорируется.
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOORBELL_CALL_WINDOW_FALLBACK_SEC,
    DOMAIN,
    SIGNAL_DOORBELL,
)

# call_controller (A-72): ring fallback + grace + idle reset после `ended`
_CALL_TIMER_DRAIN_SEC = int(DOORBELL_CALL_WINDOW_FALLBACK_SEC + 3 + 6 + 2)
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
    entity_id = er.async_get(hass).async_get_entity_id("event", DOMAIN, _UID)
    assert entity_id is not None, "doorbell event entity не создана"
    return entity_id


async def _drain_call_controller_timers(hass: HomeAssistant) -> None:
    """Снять таймеры call_controller: ring watchdog и idle reset после `ended`.

    event.py и call_controller слушают один SIGNAL_DOORBELL; после A-72 teardown
    теста без дренажа pytest ловит lingering timer (_on_ring_expired / _on_idle_reset).
    """
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=_CALL_TIMER_DRAIN_SEC)
    )
    await hass.async_block_till_done()


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
        "attributes": {"gate_name": "Подъезд 1", "apartment": "57",
                       "call_id": "C1", "allow_open": "true"},
    })
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ring"
    assert state.attributes["call_id"] == "C1"
    assert state.attributes["gate_name"] == "Подъезд 1"
    await _drain_call_controller_timers(hass)


async def test_ended_event_fires(hass: HomeAssistant, mock_api):
    """CALL_END_ANSWERED_MOBILE-payload → event `ended`."""
    entity_id = await _setup(hass)
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ended", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"reason": "answered_elsewhere", "call_id": "C1"},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["event_type"] == "ended"
    await _drain_call_controller_timers(hass)


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
    await _drain_call_controller_timers(hass)


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
    await _drain_call_controller_timers(hass)


async def test_ring_auto_ends_on_call_invalidated(hass: HomeAssistant, mock_api):
    """Реальный `ended` не пришёл → по истечении call_invalidated авто-`ended`.

    Оператор шлёт `ended` только при «принят на другом устройстве»; на сброс/
    таймаут — ничего. Без авто-таймера статус завис бы на `ring` (баг прода).
    """
    entity_id = await _setup(hass)
    invalidated = (dt_util.utcnow() + timedelta(seconds=3)).isoformat()
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"call_id": "C1", "gate_name": "Подъезд 1",
                       "call_invalidated": invalidated},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["event_type"] == "ring"

    # перешагнуть call_invalidated + margin → авто-`ended`
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ended"
    assert state.attributes["reason"] == "timeout"
    assert state.attributes["call_id"] == "C1"
    await _drain_call_controller_timers(hass)


async def test_real_ended_cancels_auto_end(hass: HomeAssistant, mock_api):
    """Реальный `ended` до таймаута снимает авто-таймер — без дубля `timeout`."""
    entity_id = await _setup(hass)
    invalidated = (dt_util.utcnow() + timedelta(seconds=3)).isoformat()
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"call_id": "C1", "call_invalidated": invalidated},
    })
    await hass.async_block_till_done()
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ended", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"reason": "answered_elsewhere", "call_id": "C1"},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["reason"] == "answered_elsewhere"

    # таймер снят: после окна reason остаётся answered_elsewhere, не timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ended"
    assert state.attributes["reason"] == "answered_elsewhere"
    await _drain_call_controller_timers(hass)


async def test_apartment_fallback_keeps_push_value(hass: HomeAssistant, mock_api):
    """Нет канонической квартиры (place.address не dict) → остаётся номер из пуша."""
    entity_id = await _setup(hass)
    coordinator = next(iter(hass.data[DOMAIN].values()))
    coordinator.data["places"][0]["place"]["address"] = "addr-string"
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"apartment": "0009777", "call_id": "C2"},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["apartment"] == "0009777"
    await _drain_call_controller_timers(hass)


async def test_auto_end_call_invalidated_in_past(hass: HomeAssistant, mock_api):
    """call_invalidated уже в прошлом → delay clamp до 1с, авто-end почти сразу."""
    entity_id = await _setup(hass)
    past = (dt_util.utcnow() - timedelta(seconds=5)).isoformat()
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"call_id": "C1", "call_invalidated": past},
    })
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ended"
    assert state.attributes["reason"] == "timeout"
    await _drain_call_controller_timers(hass)


async def test_apartment_canonical_from_place_address(hass: HomeAssistant, mock_api):
    """Push шлёт gate-кодированную квартиру (с префиксом секции) — event подставляет
    каноническую из place.address оператора, не сырое значение пуша.
    """
    entity_id = await _setup(hass)
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"apartment": "0009057", "call_id": "C1"},
    })
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["apartment"] == "57"
    await _drain_call_controller_timers(hass)


async def test_auto_end_fallback_on_invalid_call_invalidated(hass: HomeAssistant, mock_api):
    """Невалидный call_invalidated → fallback-таймер 35с (не падаем, не сразу)."""
    entity_id = await _setup(hass)
    async_dispatcher_send(hass, SIGNAL_DOORBELL, {
        "event_type": "ring", "place_id": "P1", "access_control_id": "AC1",
        "attributes": {"call_id": "C1", "call_invalidated": "not-a-date"},
    })
    await hass.async_block_till_done()
    # до fallback (35с) — ещё ring
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["event_type"] == "ring"
    # после 35с — авто-end
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=40))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "ended"
    assert state.attributes["reason"] == "timeout"
    await _drain_call_controller_timers(hass)
