"""Production-replica visibility test для hidden_by model + migration.

Использует точную структуру из реального HAR-снимка:
- 19 public_cameras, все с `externalCameraId=null` (fallback на `id`).
- 12 hidden + 7 visible в screens.PUBLIC_CAMERAS.

Покрывает:
1. Migration legacy disabled_by → None (one-time).
2. Sync visibility через hidden_by.
3. USER override safety.
4. Bi-directional un-hide.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

# Anonymized — public-камеры на перекрёстках, не PII.
PLACE_ID = "1000000"
VISIBLE_IDS = [5593570, 5593590, 5593592, 5593594, 5595471, 5595472, 5595470]
HIDDEN_IDS = [5593568, 5593572, 5593574, 5593576, 5593578, 5593580,
              5593582, 5593584, 5593586, 5593587, 5593589, 8861620]


def _make_public_cameras_response() -> list[dict[str, Any]]:
    return [
        {"id": cam_id, "externalCameraId": None, "name": f"Camera {cam_id}"}
        for cam_id in (VISIBLE_IDS + HIDDEN_IDS)
    ]


def _make_screens_response() -> dict[str, Any]:
    return {
        "screens": [
            {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
            {
                "type": "PUBLIC_CAMERAS",
                "entities": [
                    {"id": cid, "type": "PUBLIC_CAMERA", "order": idx}
                    for idx, cid in enumerate(VISIBLE_IDS)
                ],
                "hidden": [
                    {"id": cid, "type": "PUBLIC_CAMERA"} for cid in HIDDEN_IDS
                ],
            },
        ]
    }


def _make_places_response() -> list[dict[str, Any]]:
    return [
        {
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }
    ]


@pytest.fixture
def mock_api_real():
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


async def test_real_har_data_first_add(hass: HomeAssistant, mock_api_real):
    """Реальные HAR-данные: 19 cameras, 12 → hidden_by=INTEGRATION,
    7 → hidden_by=None. Никакого disabled_by manipulation."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    cams = {
        e.unique_id: e for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == "camera"
    }

    # Все 19 cameras зарегистрированы.
    expected = {f"{DOMAIN}_camera_{cid}" for cid in VISIBLE_IDS + HIDDEN_IDS}
    assert set(cams.keys()) == expected, f"Missing: {expected - set(cams.keys())}"

    # 7 visible — hidden_by=None, disabled_by=None.
    for cam_id in VISIBLE_IDS:
        e = cams[f"{DOMAIN}_camera_{cam_id}"]
        assert e.hidden_by is None, f"visible {cam_id}: hidden_by={e.hidden_by!r}"
        assert e.disabled_by is None, f"visible {cam_id}: disabled_by={e.disabled_by!r}"

    # 12 hidden — hidden_by=INTEGRATION, disabled_by=None.
    for cam_id in HIDDEN_IDS:
        e = cams[f"{DOMAIN}_camera_{cam_id}"]
        assert e.hidden_by == er.RegistryEntryHider.INTEGRATION, (
            f"hidden {cam_id}: hidden_by={e.hidden_by!r}"
        )
        assert e.disabled_by is None, f"hidden {cam_id}: disabled_by={e.disabled_by!r}"


async def test_migration_resets_legacy_disabled_by_markers(
    hass: HomeAssistant, mock_api_real
):
    """Migration v2: на первом setup после обновления сбрасываются все
    legacy disabled_by markers (INTEGRATION/DEVICE/USER) от старых версий
    интеграции. Затем sync устанавливает hidden_by согласно API."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    dev_registry = dr.async_get(hass)

    # Эмулируем legacy state: пользователь до bi-dir sync bulk-disabled через UI.
    for cam_id in VISIBLE_IDS + HIDDEN_IDS:
        uid = f"{DOMAIN}_camera_{cam_id}"
        eid = registry.async_get_entity_id("camera", DOMAIN, uid)
        if eid:
            registry.async_update_entity(eid, disabled_by=er.RegistryEntryDisabler.USER)

    # И device.disabled_by=INTEGRATION (от старой device-level sync).
    for device in dr.async_entries_for_config_entry(dev_registry, entry.entry_id):
        if device.disabled_by is None:
            dev_registry.async_update_device(
                device.id, disabled_by=dr.DeviceEntryDisabler.INTEGRATION
            )

    # Удаляем migration flag — эмулируем что entry — pre-migration.
    # После A-64 fix flag в entry.data, не options (backward-compat читает оба).
    hass.config_entries.async_update_entry(
        entry,
        data={k: v for k, v in entry.data.items() if k != "visibility_migration_v2"},
        options={k: v for k, v in entry.options.items() if k != "visibility_migration_v2"},
    )

    # Reload → migration сработает.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Проверяем: legacy disabled_by сброшен на entities + devices.
    for cam_id in VISIBLE_IDS + HIDDEN_IDS:
        uid = f"{DOMAIN}_camera_{cam_id}"
        eid = registry.async_get_entity_id("camera", DOMAIN, uid)
        e = registry.async_get(eid)
        assert e.disabled_by is None, (
            f"Migration не сбросил disabled_by для {cam_id}: {e.disabled_by!r}"
        )

    for device in dr.async_entries_for_config_entry(dev_registry, entry.entry_id):
        assert device.disabled_by is None, (
            f"Migration не сбросил device.disabled_by для {device.id}: {device.disabled_by!r}"
        )

    # И hidden_by установлен правильно через sync.
    for cam_id in HIDDEN_IDS:
        e = registry.async_get(registry.async_get_entity_id(
            "camera", DOMAIN, f"{DOMAIN}_camera_{cam_id}"
        ))
        assert e.hidden_by == er.RegistryEntryHider.INTEGRATION, (
            f"Sync после migration не set hidden_by для {cam_id}: {e.hidden_by!r}"
        )

    # Flag установлен в entry.data (A-64: убран из options чтобы не триггерить listener).
    assert entry.data.get("visibility_migration_v2") is True


async def test_user_hidden_via_ha_ui_is_preserved(
    hass: HomeAssistant, mock_api_real
):
    """USER override: пользователь руками Hide visible-в-API camera через
    HA UI — sync не должен её Show обратно."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    visible_uid = f"{DOMAIN}_camera_{VISIBLE_IDS[0]}"
    eid = registry.async_get_entity_id("camera", DOMAIN, visible_uid)
    registry.async_update_entity(eid, hidden_by=er.RegistryEntryHider.USER)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(eid).hidden_by == er.RegistryEntryHider.USER, (
        "USER hidden_by должен сохраниться"
    )


async def test_camera_unhidden_in_app_gets_shown(
    hass: HomeAssistant, mock_api_real
):
    """Bi-directional: пользователь показал в приложении ранее скрытую camera
    (например 5593578 «Площадь Ленина - Красный пр-кт») → она получает
    hidden_by=None в HA на следующем reload."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    now_visible_id = HIDDEN_IDS[0]  # one из ранее hidden
    uid = f"{DOMAIN}_camera_{now_visible_id}"
    eid = registry.async_get_entity_id("camera", DOMAIN, uid)
    assert registry.async_get(eid).hidden_by == er.RegistryEntryHider.INTEGRATION

    # API теперь возвращает её в visible.
    new_visible = VISIBLE_IDS + [now_visible_id]
    new_hidden = [c for c in HIDDEN_IDS if c != now_visible_id]
    mock_api_real.return_value.query_screens_settings = AsyncMock(return_value={
        "screens": [
            {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
            {
                "type": "PUBLIC_CAMERAS",
                "entities": [
                    {"id": c, "type": "PUBLIC_CAMERA", "order": i}
                    for i, c in enumerate(new_visible)
                ],
                "hidden": [{"id": c, "type": "PUBLIC_CAMERA"} for c in new_hidden],
            },
        ]
    })

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    final = registry.async_get(eid)
    assert final.hidden_by is None, (
        f"После un-hide в приложении camera должна быть Shown, "
        f"got hidden_by={final.hidden_by!r}"
    )
