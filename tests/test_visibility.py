"""Tests for visibility sync (hidden_by) ↔ /settings/screens.

Architecture (после PR #35 refinement):
- Camera/Lock entities управляются через `hidden_by`, не `disabled_by`.
- `hidden_by=INTEGRATION` — entity скрыта из default UI views, но state
  machine работает (automations доступны). Пользователь может easily
  Show через Settings → Entities (без UX-блока «деактивировано интеграцией»).
- Sync двунаправленный: hidden↔visible в API → hidden_by INTEGRATION↔None.
- `hidden_by=USER` (пользователь явно Hide через HA UI) — НЕ trogaem.
- Migration: one-time reset legacy disabled_by markers (от старых версий).
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


def _make_screens_response() -> dict[str, Any]:
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


def _make_places_response() -> list[dict[str, Any]]:
    return [
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }
    ]


def _make_public_cameras_response() -> list[dict[str, Any]]:
    return [
        {"id": int(VISIBLE_CAMERA_ID), "externalCameraId": None, "name": "Двор"},
        {"id": int(HIDDEN_CAMERA_ID), "externalCameraId": None, "name": "Скрытая"},
    ]


@pytest.fixture
def mock_api_class():
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=_make_places_response())
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(return_value=[])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(
            return_value=_make_public_cameras_response()
        )
        instance.query_screens_settings = AsyncMock(
            return_value=_make_screens_response()
        )
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


# ─── Test A: first add — hidden_by установлен правильно ─────────────────────


async def test_first_add_hidden_camera_gets_hidden_by_integration(
    hass: HomeAssistant, mock_api_class
):
    """При первом setup: hidden-в-API camera получает hidden_by=INTEGRATION.
    Visible — hidden_by=None. Disabled_by НЕ используется (= None для обеих)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    camera_entries = {
        e.unique_id: e for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == "camera"
    }

    visible = camera_entries[f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"]
    hidden = camera_entries[f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"]

    # Visible: ничего не скрыто/не отключено.
    assert visible.hidden_by is None, f"Visible camera hidden_by должен быть None, got {visible.hidden_by!r}"
    assert visible.disabled_by is None, f"Visible camera disabled_by должен быть None, got {visible.disabled_by!r}"

    # Hidden: hidden_by=INTEGRATION (state machine работает, но скрыта в UI).
    assert hidden.hidden_by == er.RegistryEntryHider.INTEGRATION, (
        f"Hidden camera hidden_by должен быть INTEGRATION, got {hidden.hidden_by!r}"
    )
    assert hidden.disabled_by is None, (
        f"Hidden camera disabled_by должен оставаться None (мы используем hidden_by, "
        f"не disabled_by, чтобы не блокировать UI override), got {hidden.disabled_by!r}"
    )


# ─── Test B: user hide через HA UI — sync уважает ───────────────────────────


async def test_user_hidden_in_ha_ui_is_never_touched(
    hass: HomeAssistant, mock_api_class
):
    """USER override: если пользователь руками Hide visible-в-API entity через
    HA UI (hidden_by=USER), наш sync НЕ должен её обратно Show."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    visible_uid = f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    visible_entity_id = registry.async_get_entity_id("camera", DOMAIN, visible_uid)
    assert visible_entity_id is not None

    # Пользователь руками Hide через HA UI.
    registry.async_update_entity(
        visible_entity_id, hidden_by=er.RegistryEntryHider.USER
    )

    # Reload — sync должен пробежать заново, но USER уважить.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    final = registry.async_get(visible_entity_id)
    assert final.hidden_by == er.RegistryEntryHider.USER, (
        f"USER hidden_by должен сохраниться через reload, got {final.hidden_by!r}"
    )


# ─── Test C: un-hide в приложении → Show в HA ───────────────────────────────


async def test_camera_unhidden_in_app_gets_shown_on_next_setup(
    hass: HomeAssistant, mock_api_class
):
    """Bi-directional: если пользователь показал ранее скрытую camera в
    приложении (она ушла из screens.hidden в screens.entities), наш sync на
    следующем setup должен установить hidden_by=None."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    hidden_entity_id = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    assert registry.async_get(hidden_entity_id).hidden_by == er.RegistryEntryHider.INTEGRATION

    # Меняем mock — теперь камера visible в API.
    instance = mock_api_class.return_value
    instance.query_screens_settings = AsyncMock(return_value={
        "screens": [
            {
                "type": "PUBLIC_CAMERAS",
                "entities": [
                    {"id": int(VISIBLE_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 0},
                    {"id": int(HIDDEN_CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 1},
                ],
                "hidden": [],
            },
            {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
        ]
    })

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    final = registry.async_get(hidden_entity_id)
    assert final.hidden_by is None, (
        f"После un-hide в приложении hidden_by должен стать None, got {final.hidden_by!r}"
    )


# ─── Test D: re-add config_entry — hidden state применяется правильно ───────


async def test_camera_with_hidden_in_api_disabled_on_readd(
    hass: HomeAssistant, mock_api_class
):
    """Re-add config_entry: HA восстанавливает entity из deleted_entities,
    но наш sync на post-setup восстанавливает hidden_by согласно current API.

    (Не путать с `disabled_by` ситуацией — hidden_by не сбрасывается HA core,
    но если пользователь ранее Show'нул entity → hidden_by=USER → мы не trogaem.
    Этот тест проверяет default path: hidden_by was None, then re-add → hidden_by=INTEGRATION.)
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    eid = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    assert registry.async_get(eid).hidden_by == er.RegistryEntryHider.INTEGRATION

    # Remove → re-add (entity уходит в deleted_entities + восстанавливается).
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    entry2 = _make_config_entry()
    entry2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    eid2 = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    assert eid2 is not None
    assert registry.async_get(eid2).hidden_by == er.RegistryEntryHider.INTEGRATION, (
        "После re-add hidden camera должна снова получить hidden_by=INTEGRATION"
    )
