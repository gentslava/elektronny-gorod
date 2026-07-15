"""Тесты `event`-сущности вызова домофона (event.py).

Проверяем без реального FCM — через ручной `async_dispatcher_send(SIGNAL_DOORBELL)`:
- сущность создаётся (одна на домофон AC1);
- `ring` стреляет с атрибутами; `ended` стреляет;
- payload для чужого AC игнорируется.
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from custom_components.elektronny_gorod.api import HistoryPage
from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOORBELL_CALL_WINDOW_FALLBACK_SEC,
    DOMAIN,
    SIGNAL_DOORBELL,
    SIP_DATA,
)
from custom_components.elektronny_gorod.history import SIGNAL_HISTORY_EVENT

# call_controller (A-72): ring fallback + grace + idle reset после `ended`
_CALL_TIMER_DRAIN_SEC = int(DOORBELL_CALL_WINDOW_FALLBACK_SEC + 3 + 6 + 2)
from custom_components.elektronny_gorod.user_agent import UserAgent

_UID = "elektronny_gorod_event_doorbell_P1_AC1"
_HISTORY_PLACE_UID = "elektronny_gorod_event_history_place_A1_S1_P1"
_HISTORY_PLACE_P2_UID = "elektronny_gorod_event_history_place_A1_S1_P2"
_HISTORY_AC_UID = "elektronny_gorod_event_history_access_P1_AC1"
_HISTORY_CAMERA_UID = "elektronny_gorod_event_history_camera_100"


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
        inst.query_events = AsyncMock(
            return_value=HistoryPage(events=(), number=0, last=True)
        )
        inst.query_camera_events = AsyncMock(return_value=())
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


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _cancel_call_controller_loop_timers(hass: HomeAssistant) -> None:
    """Отменить `loop.call_later` watchdog'и A-72 — они не привязаны к HA time.

    `async_fire_time_changed` снимает только datetime-таймеры event.py; на CI
    verify_cleanup всё равно ловит `_on_idle_reset` / `_on_ring_expired`.
    """
    for controller in hass.data.get(SIP_DATA, {}).values():
        controller._cancel_ring_timeout()
        controller._cancel_idle_timeout()
        controller._cancel_call_timeout()
        controller._cancel_hold_timeout()


async def _drain_call_controller_timers(hass: HomeAssistant) -> None:
    """Снять таймеры call_controller: ring watchdog и idle reset после `ended`.

    event.py и call_controller слушают один SIGNAL_DOORBELL; после A-72 teardown
    теста без дренажа pytest ловит lingering timer (_on_ring_expired / _on_idle_reset).
    """
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=_CALL_TIMER_DRAIN_SEC)
    )
    await hass.async_block_till_done()
    _cancel_call_controller_loop_timers(hass)


async def test_doorbell_event_entity_created(hass: HomeAssistant, mock_api):
    """Одна event-сущность на домофон создаётся из coordinator.data['locks']."""
    entity_id = await _setup(hass)
    assert hass.states.get(entity_id) is not None


async def test_history_event_entities_created(hass: HomeAssistant, mock_api):
    """Place, per-intercom and motion streams get EventEntity instances."""
    await _setup(hass)
    registry = er.async_get(hass)
    place_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_UID
    )
    access_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_AC_UID
    )
    camera_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_CAMERA_UID
    )

    assert place_entity_id is not None
    assert access_entity_id is not None
    assert camera_entity_id is not None
    assert hass.states.get(place_entity_id) is not None
    assert hass.states.get(access_entity_id) is not None
    assert hass.states.get(camera_entity_id) is not None


async def test_place_history_event_attached_to_place_device(
    hass: HomeAssistant, mock_api
):
    """Aggregate history is grouped under its existing place device."""
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_UID
    )
    assert entity_id == "event.account_a1_place_p1_event_history"

    registered_entity = er.async_get(hass).async_get(entity_id)
    assert registered_entity is not None
    assert registered_entity.device_id is not None

    place_device = dr.async_get(hass).async_get(registered_entity.device_id)
    assert place_device is not None
    assert place_device.identifiers == {(DOMAIN, "place_P1")}


async def test_single_place_migrates_prerelease_account_history_entity(
    hass: HomeAssistant, mock_api
):
    """The prerelease account entity becomes the explicit place entity."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "event",
        DOMAIN,
        "elektronny_gorod_event_history_account_A1_S1",
        suggested_object_id="account_event_history",
        config_entry=entry,
    )
    assert legacy.entity_id == "event.account_event_history"

    await _setup_entry(hass, entry)

    assert registry.async_get("event.account_event_history") is None
    migrated_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_UID
    )
    assert migrated_id == "event.account_a1_place_p1_event_history"


async def test_single_place_migration_preserves_custom_entity_id(
    hass: HomeAssistant, mock_api
):
    """A user-customized prerelease entity ID is not renamed by migration."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "event",
        DOMAIN,
        "elektronny_gorod_event_history_account_A1_S1",
        suggested_object_id="my_custom_history",
        config_entry=entry,
    )

    await _setup_entry(hass, entry)

    migrated = registry.async_get("event.my_custom_history")
    assert migrated is not None
    assert migrated.unique_id == _HISTORY_PLACE_UID


async def test_multiple_places_get_separate_history_entities(
    hass: HomeAssistant, mock_api
):
    """Every place gets an independently addressable aggregate history entity."""
    mock_api.return_value.query_places.return_value = [
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": "P1", "address": {"house": "20"}},
        },
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": "P2", "address": {"house": "22"}},
        },
    ]

    await _setup(hass)
    registry = er.async_get(hass)
    first_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_UID
    )
    second_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_P2_UID
    )
    assert first_entity_id == "event.account_a1_place_p1_event_history"
    assert second_entity_id == "event.account_a1_place_p2_event_history"

    devices = dr.async_get(hass)
    first_entity = registry.async_get(first_entity_id)
    second_entity = registry.async_get(second_entity_id)
    assert first_entity is not None and first_entity.device_id is not None
    assert second_entity is not None and second_entity.device_id is not None
    assert devices.async_get(first_entity.device_id).identifiers == {
        (DOMAIN, "place_P1")
    }
    assert devices.async_get(second_entity.device_id).identifiers == {
        (DOMAIN, "place_P2")
    }


async def test_place_history_event_keeps_source_metadata(
    hass: HomeAssistant, mock_api
):
    """The place stream identifies the intercom without exposing message."""
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, _HISTORY_PLACE_UID
    )
    assert entity_id is not None

    async_dispatcher_send(hass, SIGNAL_HISTORY_EVENT, {
        "event_type": "call_missed",
        "event_id": "event-new",
        "occurred_at": 1700000001,
        "place_id": "P1",
        "source_type": "accessControl",
        "source_id": "AC1",
        "message": "PII-SENTINEL",
    })
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "call_missed"
    assert state.attributes["place_id"] == "P1"
    assert state.attributes["source_id"] == "AC1"
    assert state.attributes["source_name"] == "Подъезд 1"
    assert "message" not in state.attributes
    assert "PII-SENTINEL" not in json.dumps(dict(state.attributes))


async def test_access_history_event_routes_sanitized_payload(
    hass: HomeAssistant, mock_api
):
    """Accepted/missed history routes by place + AC and exposes no message."""
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, _HISTORY_AC_UID
    )
    assert entity_id is not None

    async_dispatcher_send(hass, SIGNAL_HISTORY_EVENT, {
        "event_type": "call_missed",
        "event_id": "event-new",
        "occurred_at": 1700000001,
        "place_id": "P1",
        "source_type": "accessControl",
        "source_id": "AC1",
        "message": "PII-SENTINEL",
    })
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "call_missed"
    assert state.attributes["event_id"] == "event-new"
    assert state.attributes["occurred_at"] == 1700000001
    assert "message" not in state.attributes
    assert "PII-SENTINEL" not in json.dumps(dict(state.attributes))


async def test_camera_history_event_routes_motion_by_requested_camera(
    hass: HomeAssistant, mock_api
):
    """Motion state belongs to the requested camera and exposes availability."""
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, _HISTORY_CAMERA_UID
    )
    assert entity_id is not None

    async_dispatcher_send(hass, SIGNAL_HISTORY_EVENT, {
        "event_type": "motion",
        "event_id": "motion-new",
        "occurred_at": 1700000001,
        "camera_id": "100",
        "duration": 30,
        "recording_available": False,
        "message": "PII-SENTINEL",
    })
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "motion"
    assert state.attributes["event_id"] == "motion-new"
    assert state.attributes["duration"] == 30
    assert state.attributes["recording_available"] is False
    assert "message" not in state.attributes
    assert "PII-SENTINEL" not in json.dumps(dict(state.attributes))


async def test_history_manager_follows_config_entry_lifecycle(
    hass: HomeAssistant, mock_api
):
    """History starts after platforms and its timer is cancelled on unload."""
    managers: list[MagicMock] = []

    def _manager_factory(*_args) -> MagicMock:
        manager = MagicMock()
        manager.async_start = AsyncMock()
        manager.async_stop = MagicMock()
        managers.append(manager)
        return manager

    with patch(
        "custom_components.elektronny_gorod.HistoryManager",
        side_effect=_manager_factory,
        create=True,
    ) as manager_cls:
        entry = _entry()
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Первый setup может сделать one-time visibility reload; каждый manager
        # всё равно обязан иметь парный start/stop.
        assert manager_cls.call_count >= 1
        assert all(call.args[0] is hass for call in manager_cls.call_args_list)
        assert all(call.args[1] == entry.entry_id for call in manager_cls.call_args_list)
        for manager in managers:
            manager.async_start.assert_awaited_once_with()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        for manager in managers:
            manager.async_stop.assert_called_once_with()


async def test_history_ws_command_registers_during_config_entry_setup(
    hass: HomeAssistant, mock_api
):
    """The history browser command is available after integration setup."""
    with patch(
        "custom_components.elektronny_gorod.async_register_history_ws_command"
    ) as register:
        entry = _entry()
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert register.call_count >= 1
    register.assert_any_call(hass)


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
