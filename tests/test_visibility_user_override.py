"""Tests for A-64: user override tracking + reload cascade fix.

Контекст:
- Раньше `_sync_visibility` на каждом setup восстанавливал INTEGRATION
  для всех hidden-в-API камер, даже если юзер только что кликнул
  «Показывать на панели» (hidden_by=None). Это перезаписывало user choice
  каждые 5 минут (на refresh) — плохой UX.
- Также migration flag в `entry.options` триггерил `async_update_options`
  listener → reload cascade (4× reload в 34 сек при cold start).

A-64 fixes:
- Migration flag в `entry.data` (НЕ options) — listener не срабатывает.
- Reload только при migration_changed (sync_visibility — live registry update).
- `_sync_visibility` track per-entity flags в `entity.options[DOMAIN]`:
  - `we_set_integration`: True если мы set INTEGRATION
  - `user_shown`: True если юзер потом убрал (кликнул «Показывать на панели»)
- При API hidden + user_shown=True → НЕ восстанавливаем INTEGRATION.
- Если приложение тоже разрешит показ → user_shown auto-clear.
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


def _screens_all_visible() -> dict[str, Any]:
    return {
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
        {"id": int(VISIBLE_CAMERA_ID), "externalCameraId": None, "name": "Visible"},
        {"id": int(HIDDEN_CAMERA_ID), "externalCameraId": None, "name": "Hidden"},
    ]


@pytest.fixture
def mock_api():
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


# ─── A: Migration flag storage (entry.data, не options) ─────────────────────


async def test_migration_flag_stored_in_data_not_options(
    hass: HomeAssistant, mock_api
):
    """A-64: migration flag в entry.data — чтобы НЕ триггерить
    async_update_options listener (он делает reload → cascade)."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fresh = hass.config_entries.async_get_entry(entry.entry_id)
    assert fresh.data.get("visibility_migration_v2") is True, (
        f"Migration flag должен быть в entry.data, got data={dict(fresh.data)}"
    )
    assert "visibility_migration_v2" not in fresh.options, (
        f"Migration flag НЕ должен быть в entry.options (триггерит listener), "
        f"got options={dict(fresh.options)}"
    )


async def test_backward_compat_migrates_flag_from_options_to_data(
    hass: HomeAssistant, mock_api
):
    """A-64 backward-compat: если flag уже в options от старой версии —
    переносим в data при первом setup, миграцию НЕ повторяем."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    # Эмулируем старое состояние: flag в options.
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, "visibility_migration_v2": True},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fresh = hass.config_entries.async_get_entry(entry.entry_id)
    assert fresh.data.get("visibility_migration_v2") is True
    assert "visibility_migration_v2" not in fresh.options


# ─── B: User override tracking — «Показывать на панели» persists ────────────


async def test_user_shown_override_persists_across_reload(
    hass: HomeAssistant, mock_api
):
    """A-64: юзер кликнул «Показывать на панели» для INTEGRATION-hidden камеры —
    следующий sync (reload или 5-мин tick) НЕ восстанавливает INTEGRATION."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    eid = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)
    # Precondition: sync set INTEGRATION при первом setup.
    assert registry.async_get(eid).hidden_by == er.RegistryEntryHider.INTEGRATION

    # Юзер кликнул «Показывать на панели».
    registry.async_update_entity(eid, hidden_by=None)

    # Reload entry — sync пробежит заново.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    final = registry.async_get(eid)
    assert final.hidden_by is None, (
        f"После user «Показывать на панели» reload не должен возвращать "
        f"INTEGRATION, got {final.hidden_by!r}"
    )
    # Проверим что флаг сохранён в registry options.
    opts = final.options.get(DOMAIN, {})
    assert opts.get("user_shown") is True, (
        f"user_shown override должен быть сохранён, got options={opts!r}"
    )


async def test_user_show_override_cleared_when_app_un_hides(
    hass: HomeAssistant, mock_api
):
    """A-64: если приложение тоже разрешило показ (uid НЕ в hidden_uids API) —
    user_shown override автоматически снимается. На последующем «Скрыть в
    приложении» мы снова поставим INTEGRATION."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_uid = f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    eid = registry.async_get_entity_id("camera", DOMAIN, hidden_uid)

    # Юзер «Показал» в HA UI.
    registry.async_update_entity(eid, hidden_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Sanity: override сохранён.
    assert registry.async_get(eid).options.get(DOMAIN, {}).get("user_shown") is True

    # Теперь приложение тоже разрешило показ.
    instance = mock_api.return_value
    instance.query_screens_settings = AsyncMock(return_value=_screens_all_visible())

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    final = registry.async_get(eid)
    assert final.hidden_by is None
    opts = final.options.get(DOMAIN, {})
    assert "user_shown" not in opts, (
        f"После un-hide в приложении user_shown override должен сняться, "
        f"got options={opts!r}"
    )

    # Цикл закрылся: если теперь приложение снова скроет — sync set INTEGRATION.
    instance.query_screens_settings = AsyncMock(return_value=_screens_with_hidden())
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(eid).hidden_by == er.RegistryEntryHider.INTEGRATION, (
        "После очистки override sync снова должен set INTEGRATION на app-hidden"
    )


# ─── C: Idempotency / cascade fix ───────────────────────────────────────────


async def test_user_in_ha_ui_hide_still_respected(
    hass: HomeAssistant, mock_api
):
    """Regression (A-64 не должен сломать USER override): юзер сам Hide
    visible-в-API entity через HA UI (hidden_by=USER) — sync не trogaem."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    visible_uid = f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    visible_eid = registry.async_get_entity_id("camera", DOMAIN, visible_uid)
    # Юзер вручную Hide.
    registry.async_update_entity(visible_eid, hidden_by=er.RegistryEntryHider.USER)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(visible_eid).hidden_by == er.RegistryEntryHider.USER, (
        "USER hidden_by должен сохраниться через reload"
    )


@pytest.mark.parametrize(
    "bad_screens",
    [
        "client_error",
        {"screens": 5},
        ["unexpected-root"],
        None,
        {"unexpected": []},
    ],
)
async def test_screens_failure_or_unusable_preserves_overrides_and_integration_state(
    hass: HomeAssistant, mock_api, bad_screens
):
    """A-116: отказ или непригодный `/settings/screens` не стирает user_shown/we_set_integration."""
    from aiohttp import ClientError

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_eid = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    )
    visible_eid = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    )
    assert hidden_eid is not None and visible_eid is not None

    # Пользователь показал скрытую интеграцией камеру и скрыл видимую вручную.
    registry.async_update_entity(hidden_eid, hidden_by=None)
    registry.async_update_entity(visible_eid, hidden_by=er.RegistryEntryHider.USER)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(hidden_eid).options.get(DOMAIN, {}).get("user_shown") is True
    assert registry.async_get(hidden_eid).options.get(DOMAIN, {}).get("we_set_integration") is True
    assert registry.async_get(visible_eid).hidden_by == er.RegistryEntryHider.USER

    # Reload с отказом/битым /settings/screens (даже с spy на registry writes).
    instance = mock_api.return_value
    if bad_screens == "client_error":
        instance.query_screens_settings = AsyncMock(
            side_effect=ClientError("screens offline")
        )
    else:
        instance.query_screens_settings = AsyncMock(return_value=bad_screens)

    with (
        patch.object(registry, "async_update_entity", wraps=registry.async_update_entity) as upd_ent,
        patch.object(
            registry,
            "async_update_entity_options",
            wraps=registry.async_update_entity_options,
        ) as upd_opts,
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert upd_ent.call_count == 0
    assert upd_opts.call_count == 0
    assert registry.async_get(hidden_eid).options.get(DOMAIN, {}).get("user_shown") is True
    assert registry.async_get(hidden_eid).options.get(DOMAIN, {}).get("we_set_integration") is True
    assert registry.async_get(hidden_eid).hidden_by is None
    assert registry.async_get(visible_eid).hidden_by == er.RegistryEntryHider.USER

    # После восстановления /settings/screens user_shown по-прежнему уважается.
    instance.query_screens_settings = AsyncMock(return_value=_screens_with_hidden())
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(hidden_eid).hidden_by is None
    assert registry.async_get(visible_eid).hidden_by == er.RegistryEntryHider.USER


async def test_screens_valid_empty_dict_still_clears_integration_hidden_preserving_user(
    hass: HomeAssistant, mock_api
):
    """A-116: валидный пустой `{}` по-прежнему снимает hidden_by=INTEGRATION, не трогая USER."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    hidden_eid = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{HIDDEN_CAMERA_ID}"
    )
    visible_eid = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{VISIBLE_CAMERA_ID}"
    )
    registry.async_update_entity(visible_eid, hidden_by=er.RegistryEntryHider.USER)
    assert registry.async_get(hidden_eid).hidden_by == er.RegistryEntryHider.INTEGRATION

    mock_api.return_value.query_screens_settings = AsyncMock(return_value={})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(hidden_eid).hidden_by is None
    assert "we_set_integration" not in (registry.async_get(hidden_eid).options.get(DOMAIN) or {})
    assert registry.async_get(visible_eid).hidden_by == er.RegistryEntryHider.USER


async def test_screens_failure_in_place_a_does_not_block_verified_place_b(
    hass: HomeAssistant, mock_api
):
    """A-116: сбой `/settings/screens` в месте A не мешает синхронизации видимости места B."""
    from aiohttp import ClientError

    instance = mock_api.return_value
    instance.query_places = AsyncMock(return_value=[
        {"subscriber": {"id": "S1", "accountId": "A1", "name": "Test"}, "place": {"id": "PA", "address": "A"}},
        {"subscriber": {"id": "S1", "accountId": "A1", "name": "Test"}, "place": {"id": "PB", "address": "B"}},
    ])

    def _cams(place_id: str):
        if place_id == "PA":
            return [
                {"id": 101, "externalCameraId": None, "name": "PA Visible"},
                {"id": 102, "externalCameraId": None, "name": "PA Hidden"},
            ]
        return [
            {"id": 201, "externalCameraId": None, "name": "PB Visible"},
            {"id": 202, "externalCameraId": None, "name": "PB Hidden"},
        ]

    def _screens_initial(place_id: str):
        if place_id == "PA":
            return {"screens": [{"type": "PUBLIC_CAMERAS", "hidden": [{"id": 102}]}]}
        return {"screens": [{"type": "PUBLIC_CAMERAS", "hidden": [{"id": 202}]}]}

    instance.query_public_cameras = AsyncMock(side_effect=_cams)
    instance.query_screens_settings = AsyncMock(side_effect=_screens_initial)

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    eid_pa_102 = registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_102")
    eid_pb_201 = registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_201")
    eid_pb_202 = registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_202")

    # Пользователь включил 102 в месте PA.
    registry.async_update_entity(eid_pa_102, hidden_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(eid_pa_102).options.get(DOMAIN, {}).get("user_shown") is True

    # Теперь PA падает, а в PB изменилась видимость (201 стал hidden, 202 стал visible).
    def _screens_partial_fail(place_id: str):
        if place_id == "PA":
            raise ClientError("PA screens down")
        return {"screens": [{"type": "PUBLIC_CAMERAS", "hidden": [{"id": 201}]}]}

    instance.query_screens_settings = AsyncMock(side_effect=_screens_partial_fail)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # PA сохранил user_shown и we_set_integration, а PB применил новые правила.
    assert registry.async_get(eid_pa_102).options.get(DOMAIN, {}).get("user_shown") is True
    assert registry.async_get(eid_pa_102).options.get(DOMAIN, {}).get("we_set_integration") is True
    assert registry.async_get(eid_pb_201).hidden_by == er.RegistryEntryHider.INTEGRATION
    assert registry.async_get(eid_pb_202).hidden_by is None
