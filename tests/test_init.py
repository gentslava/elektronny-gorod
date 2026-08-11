"""Config-entry migration tests (A-73 — async_migrate_entry v1→2→3).

Проверяют, что `async_migrate_entry` доводит старые entry до текущей VERSION=3
без потери данных: v1 добавляет `user_agent`, v2/v3 — go2rtc-дефолты.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod import (
    _async_register_fcm_listener,
    async_migrate_entry,
    async_remove_entry,
    async_unload_entry,
)
from custom_components.elektronny_gorod.const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    DEFAULT_GO2RTC_BASE_URL,
    DEFAULT_GO2RTC_RTSP_HOST,
)
from custom_components.elektronny_gorod.fcm import fcm_repair_issue_id
from custom_components.elektronny_gorod.user_agent import UserAgent


async def test_setup_with_surviving_fcm_owner_loads_without_replacement(
    hass: HomeAssistant,
) -> None:
    """A retained receiver degrades only FCM without starting a setup loop."""
    entry = MockConfigEntry(domain=DOMAIN, title="Account 1", version=3)
    entry.add_to_hass(hass)
    previous = MagicMock()
    previous.async_stop = AsyncMock(side_effect=RuntimeError("dependency failure"))
    hass.data[f"{DOMAIN}_fcm_listeners"] = {entry.entry_id: previous}

    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.api = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_unsubscribe = MagicMock(return_value=None)
    history_manager = MagicMock()
    history_manager.async_stop = AsyncMock()
    sip_controller = MagicMock()
    sip_controller.async_hangup = AsyncMock()
    replacement = MagicMock()
    replacement.async_start = MagicMock(return_value=MagicMock())
    replacement.async_stop = AsyncMock(return_value=True)
    unsubscribe = MagicMock(return_value=None)

    with (
        patch(
            "custom_components.elektronny_gorod.ElektronnyGorodUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "custom_components.elektronny_gorod.async_migrate_entity_unique_ids",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward_setups,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.elektronny_gorod.DoorbellFcmListener",
            return_value=replacement,
        ),
        patch(
            "custom_components.elektronny_gorod.HistoryManager",
            return_value=history_manager,
        ),
        patch(
            "custom_components.elektronny_gorod.DoorbellCallController",
            return_value=sip_controller,
        ) as call_controller_cls,
        patch(
            "custom_components.elektronny_gorod.async_dispatcher_connect",
            return_value=unsubscribe,
        ),
        patch("custom_components.elektronny_gorod._async_register_sip_services"),
        patch("custom_components.elektronny_gorod.async_register_history_ws_command"),
        patch("custom_components.elektronny_gorod.async_register_uplink_ws_command"),
        patch(
            "custom_components.elektronny_gorod.async_register_uplink_card",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.elektronny_gorod._migrate_legacy_disabled_state",
            return_value=False,
        ),
        patch("custom_components.elektronny_gorod._sync_visibility"),
        patch.object(entry, "async_create_background_task"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        assert entry.state is ConfigEntryState.LOADED
        forward_setups.assert_awaited_once()
        assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is previous
        replacement.async_start.assert_not_called()
        assert (
            ir.async_get(hass).async_get_issue(
                DOMAIN, fcm_repair_issue_id(entry.entry_id)
            )
            is not None
        )
        assert call_controller_cls.call_args.args[2]() is None

        previous.async_stop.side_effect = None
        previous.async_stop.return_value = True
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_remove_after_failed_unload_retains_fcm_owner_and_requires_restart(
    hass: HomeAssistant, mock_remove_entry_api
) -> None:
    """Unconfirmed dependency stop keeps ownership and asks HA for restart."""
    user_agent = UserAgent()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Account 1",
        version=3,
        data={
            CONF_USER_AGENT: json.dumps(user_agent.json()),
            CONF_OPERATOR_ID: "1",
        },
    )
    entry.add_to_hass(hass)
    retained = MagicMock()
    retained.async_stop = AsyncMock(return_value=False)
    hass.data[f"{DOMAIN}_fcm_listeners"] = {entry.entry_id: retained}

    entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    result = await hass.config_entries.async_remove(entry.entry_id)

    assert result == {"require_restart": True}
    assert retained.async_stop.await_count == 2
    assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is retained


async def test_fcm_registry_cleanup_is_valid_on_setup_failure(
    hass: HomeAssistant,
) -> None:
    """Core can process FCM cleanup callbacks after a failed entry setup."""
    entry = MockConfigEntry(domain=DOMAIN, title="Account 1")
    entry.add_to_hass(hass)
    listener = MagicMock()
    listener.async_stop = AsyncMock()

    await _async_register_fcm_listener(hass, entry, listener)
    await entry._async_process_on_unload(hass)

    listener.async_stop.assert_awaited_once()
    assert entry.entry_id not in hass.data[f"{DOMAIN}_fcm_listeners"]


async def test_fcm_registry_cleanup_retains_owner_after_failed_stop(
    hass: HomeAssistant,
) -> None:
    """A failed setup unwind must not lose the surviving FCM receiver owner."""
    entry = MockConfigEntry(domain=DOMAIN, title="Account 1")
    entry.add_to_hass(hass)
    listener = MagicMock()
    listener.async_stop = AsyncMock(return_value=False)

    await _async_register_fcm_listener(hass, entry, listener)
    await entry._async_process_on_unload(hass)

    listener.async_stop.assert_awaited_once()
    assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is listener

    replacement = MagicMock()
    replacement.async_stop = AsyncMock(return_value=True)
    assert await _async_register_fcm_listener(hass, entry, replacement) is False

    assert listener.async_stop.await_count == 2
    replacement.async_stop.assert_not_awaited()
    assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is listener

    listener.async_stop.return_value = True
    assert await _async_register_fcm_listener(hass, entry, replacement) is True

    assert listener.async_stop.await_count == 3
    assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is replacement


async def test_unload_stops_when_fcm_client_cannot_stop(
    hass: HomeAssistant,
) -> None:
    """Failed FCM cleanup blocks reload so a second receiver cannot overlap."""
    entry = MagicMock()
    entry.entry_id = "entry-1"
    listener = MagicMock()
    listener.async_stop = AsyncMock(return_value=False)
    hass.data[f"{DOMAIN}_fcm_listeners"] = {entry.entry_id: listener}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ) as unload_platforms:
        assert await async_unload_entry(hass, entry) is False

    listener.async_stop.assert_awaited_once()
    unload_platforms.assert_not_awaited()
    assert hass.data[f"{DOMAIN}_fcm_listeners"][entry.entry_id] is listener


async def test_migrate_v1_to_v3(hass: HomeAssistant) -> None:
    """v1 (без user_agent, без go2rtc) → v3: добавлены user_agent + go2rtc-дефолты."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # v1→2: user_agent появился и это валидный JSON с operator_id.
    assert CONF_USER_AGENT in entry.data
    ua = json.loads(entry.data[CONF_USER_AGENT])
    assert ua["operator_id"] == "1"
    # v2→3: go2rtc-дефолты.
    assert entry.data[CONF_USE_GO2RTC] is False
    assert entry.data[CONF_GO2RTC_BASE_URL] == DEFAULT_GO2RTC_BASE_URL
    assert entry.data[CONF_GO2RTC_RTSP_HOST] == DEFAULT_GO2RTC_RTSP_HOST
    # Исходные данные не потеряны.
    assert entry.data[CONF_ACCESS_TOKEN] == "AT"


async def test_migrate_v2_to_v3(hass: HomeAssistant) -> None:
    """v2 (user_agent есть, go2rtc нет) → v3: добавлены только go2rtc-дефолты."""
    existing_ua = json.dumps({"operator_id": "1", "marker": "kept"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: existing_ua,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # user_agent не перезаписан миграцией.
    assert entry.data[CONF_USER_AGENT] == existing_ua
    assert entry.data[CONF_USE_GO2RTC] is False
    assert entry.data[CONF_GO2RTC_BASE_URL] == DEFAULT_GO2RTC_BASE_URL
    assert entry.data[CONF_GO2RTC_RTSP_HOST] == DEFAULT_GO2RTC_RTSP_HOST


async def test_migrate_v3_noop(hass: HomeAssistant) -> None:
    """v3 (актуальная) → миграция ничего не ломает, версия остаётся 3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps({"operator_id": "1"}),
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://example:1984",
            CONF_GO2RTC_RTSP_HOST: "example",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # Существующие go2rtc-значения не сброшены дефолтами.
    assert entry.data[CONF_USE_GO2RTC] is True
    assert entry.data[CONF_GO2RTC_BASE_URL] == "http://example:1984"


async def test_remove_entry_deletes_fcm_repair_issue(
    hass: HomeAssistant, mock_remove_entry_api
) -> None:
    """Удаление config entry не оставляет orphan persistent issue."""
    user_agent = UserAgent()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Аккаунт 1",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(user_agent.json()),
        },
    )
    entry.add_to_hass(hass)
    issue_id = fcm_repair_issue_id(entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="fcm_receiver_unavailable",
    )

    await async_remove_entry(hass, entry)

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    mock_remove_entry_api.return_value.unregister_push_device.assert_awaited_once()
