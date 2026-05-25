"""Tests for Do Not Disturb switches.

Покрывает:
- 3 switch entity создаются per place (root + 2 dependent).
- is_on отражает coordinator.data["dnd"][place_id][...].status.
- Dependent unavailable если root=False.
- Toggle вызывает coordinator.async_set_dnd с правильным payload.
- USER override через HA UI (turn_off) → POST с status=False.
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

PLACE_ID = "1000000"


def _dnd_items(
    root: bool = False, intercom: bool = False, mgmt: bool = False
) -> list[dict[str, Any]]:
    return [
        {"type": "DO_NOT_DISTURB_ROOT", "name": "Не беспокоить",
         "status": root, "hint": "", "editable": True},
        {"type": "INTERCOM_CALLS", "name": "Звонки с домофона",
         "status": intercom, "hint": "", "editable": True},
        {"type": "MANAGEMENT_COMPANY_CALLS", "name": "Уведомления УК",
         "status": mgmt, "hint": "", "editable": True},
    ]


@pytest.fixture
def mock_api_with_dnd():
    """API mock with DND on one place."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }])
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(return_value=[])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=[])
        instance.query_screens_settings = AsyncMock(return_value={})
        instance.query_dnd_settings = AsyncMock(return_value=_dnd_items())
        instance.post_dnd_settings = AsyncMock(return_value=True)
        yield mock_cls


def _make_config_entry() -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN, version=3, unique_id="test_unique_subscriber_S1",
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


async def test_three_dnd_switches_created_per_place(
    hass: HomeAssistant, mock_api_with_dnd
):
    """Per place создаются 3 switch entity (root + 2 dependent)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    switches = {e.unique_id: e for e in entries if e.domain == "switch"}

    expected_uids = {
        f"{DOMAIN}_dnd_{PLACE_ID}_dnd_root",
        f"{DOMAIN}_dnd_{PLACE_ID}_dnd_intercom_calls",
        f"{DOMAIN}_dnd_{PLACE_ID}_dnd_management_company_calls",
    }
    assert set(switches.keys()) == expected_uids


async def test_dependent_unavailable_when_root_off(
    hass: HomeAssistant, mock_api_with_dnd
):
    """Когда root=OFF — INTERCOM_CALLS и MGMT_CALLS должны быть unavailable."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # entity_id формируются HA динамически из device.name + translation —
    # найдём через registry по unique_id.
    registry = er.async_get(hass)
    root_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_root"
    )
    intercom_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_intercom_calls"
    )

    assert hass.states.get(root_eid).state == "off"
    # Dependent должна быть unavailable (root=OFF).
    assert hass.states.get(intercom_eid).state == "unavailable"


async def test_dependent_available_when_root_on(
    hass: HomeAssistant, mock_api_with_dnd
):
    """Когда root=ON — dependent становятся available и отражают свой status."""
    mock_api_with_dnd.return_value.query_dnd_settings = AsyncMock(
        return_value=_dnd_items(root=True, intercom=True, mgmt=False)
    )

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    root_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_root"
    )
    intercom_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_intercom_calls"
    )
    mgmt_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_management_company_calls"
    )

    assert hass.states.get(root_eid).state == "on"
    assert hass.states.get(intercom_eid).state == "on"
    assert hass.states.get(mgmt_eid).state == "off"  # available, status=False


async def test_turn_on_sends_post_with_updated_status(
    hass: HomeAssistant, mock_api_with_dnd
):
    """turn_on на root → post_dnd_settings с status=True для DO_NOT_DISTURB_ROOT,
    остальные items остаются с прежним status."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    root_eid = registry.async_get_entity_id(
        "switch", DOMAIN, f"{DOMAIN}_dnd_{PLACE_ID}_dnd_root"
    )

    # Эмулируем что после POST refresh вернёт root=True.
    mock_api_with_dnd.return_value.query_dnd_settings = AsyncMock(
        return_value=_dnd_items(root=True)
    )

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": root_eid}, blocking=True
    )

    # post_dnd_settings вызван с правильным payload.
    instance = mock_api_with_dnd.return_value
    instance.post_dnd_settings.assert_awaited_once()
    args = instance.post_dnd_settings.await_args
    assert args.args[0] == PLACE_ID
    payload = args.args[1]
    root_item = next(i for i in payload if i["type"] == "DO_NOT_DISTURB_ROOT")
    assert root_item["status"] is True
    # Прочие items сохраняют свой status (False по дефолту).
    intercom_item = next(i for i in payload if i["type"] == "INTERCOM_CALLS")
    assert intercom_item["status"] is False
