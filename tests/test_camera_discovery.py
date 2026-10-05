"""Regression coverage for cameras first returned after config-entry setup."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod import _sync_visibility
from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
    STREAM_MANAGER_DATA,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcClient
from custom_components.elektronny_gorod.stream_manager import CameraStreamManager
from custom_components.elektronny_gorod.user_agent import UserAgent


def _controls(camera_id: int | None = None) -> list[dict]:
    return [{
        "id": "AC1",
        "name": "Intercom",
        "entrances": [{
            "id": "E1", "name": "Entrance", "allowOpen": True,
            "externalCameraId": camera_id,
        }],
    }]


def _entry(*, go2rtc: bool = False) -> MockConfigEntry:
    user_agent = UserAgent()
    user_agent.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(user_agent.json()),
            "account_id": "A1", "subscriber_id": "S1",
            "visibility_migration_v2": True,
            "use_go2rtc": go2rtc,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
            "go2rtc_keep_warm": go2rtc,
        },
    )


@pytest.fixture
def mock_api():
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as api_cls:
        api = api_cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": "P1", "address": "Address"},
        }])
        api.query_balance = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=_controls())
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(return_value=[])
        api.query_screens_settings = AsyncMock(return_value={"screens": []})
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_camera_stream = AsyncMock(return_value="https://operator/video")
        yield api


def _registry_camera(hass: HomeAssistant, camera_id: str = "100"):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}"
    )
    return registry.async_get(entity_id) if entity_id else None


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_refresh_discovers_camera_on_existing_intercom(
    hass: HomeAssistant, mock_api
) -> None:
    """A partial initial response must not require a reload to add its camera."""
    entry = _entry(go2rtc=True)
    published = asyncio.Event()
    with (
        patch.object(Go2RtcClient, "async_list_streams", new=AsyncMock(return_value={})),
        patch.object(Go2RtcClient, "async_list_preloads", new=AsyncMock(return_value=set())),
        patch.object(Go2RtcClient, "async_patch_stream", new=AsyncMock(side_effect=lambda *_: published.set())) as publish,
        patch.object(Go2RtcClient, "async_enable_preload", new=AsyncMock(return_value=True)),
        patch.object(Go2RtcClient, "async_disable_preload", new=AsyncMock(return_value=True)),
    ):
        await _setup(hass, entry)
        registry = er.async_get(hass)
        intercom = registry.async_get_entity_id(
            "lock", DOMAIN, f"{DOMAIN}_lock_P1_AC1_E1"
        )
        assert intercom is not None
        assert _registry_camera(hass) is None

        mock_api.query_access_controls.return_value = _controls(100)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        camera = _registry_camera(hass)
        assert camera is not None
        assert camera.device_id == registry.async_get(intercom).device_id
        assert hass.data["camera"].get_entity(camera.entity_id).available
        manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
        assert manager.is_camera_eligible("100")
        # Exercise the real registry event and zero-delay reconcile timer;
        # an executor-dispatched listener cannot schedule this HA timer.
        await asyncio.wait_for(published.wait(), timeout=1)
        await hass.async_block_till_done()
        publish.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_discovery_deduplicates_and_retains_temporarily_missing_camera(
    hass: HomeAssistant, mock_api
) -> None:
    entry = _entry()
    await _setup(hass, entry)
    coordinator = entry.runtime_data
    data = coordinator.data
    camera = {"id": 100, "name": "Camera", "source": "public"}
    coordinator.async_set_updated_data({**data, "cameras": [camera, {**camera, "id": "100"}]})
    # Both callbacks run before HA finishes adding the first batch.
    coordinator.async_set_updated_data({**data, "cameras": [camera]})
    await hass.async_block_till_done()
    registered = _registry_camera(hass)
    assert registered is not None
    entity = hass.data["camera"].get_entity(registered.entity_id)
    assert len([e for e in hass.data["camera"].entities if e.unique_id == registered.unique_id]) == 1

    coordinator.async_set_updated_data({**data, "cameras": []})
    await hass.async_block_till_done()
    assert not entity.available
    assert _registry_camera(hass) == registered
    coordinator.async_set_updated_data({**data, "cameras": [camera]})
    await hass.async_block_till_done()
    assert hass.data["camera"].get_entity(registered.entity_id) is entity
    assert entity.available


async def test_discovery_ignores_empty_camera_ids(
    hass: HomeAssistant, mock_api
) -> None:
    mock_api.query_public_cameras.return_value = [{"id": None}, {"id": ""}]
    entry = _entry()
    await _setup(hass, entry)
    assert _registry_camera(hass, "") is None
    entry.runtime_data.async_set_updated_data({
        **entry.runtime_data.data, "cameras": [{}, {"id": None}, {"id": ""}],
    })
    await hass.async_block_till_done()
    assert _registry_camera(hass, "") is None


async def test_unload_stops_discovery_and_reload_rediscovers(
    hass: HomeAssistant, mock_api
) -> None:
    entry = _entry()
    await _setup(hass, entry)
    coordinator = entry.runtime_data
    data = coordinator.data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    coordinator.async_set_updated_data({**data, "cameras": [{"id": 100}]})
    await hass.async_block_till_done()
    assert _registry_camera(hass) is None

    mock_api.query_access_controls.return_value = _controls(100)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _registry_camera(hass) is not None


@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize("disabled", [False, True])
async def test_late_discovery_preserves_existing_user_controls(
    hass: HomeAssistant, mock_api, hidden: bool, disabled: bool
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "camera", DOMAIN, f"{DOMAIN}_camera_100", config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
        hidden_by=er.RegistryEntryHider.USER,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.async_set_updated_data({
        **entry.runtime_data.data,
        "cameras": [{"id": 100, "hidden": hidden}],
    })
    await hass.async_block_till_done()
    discovered = _registry_camera(hass)
    assert discovered.entity_id == existing.entity_id
    assert discovered.disabled_by == (er.RegistryEntryDisabler.USER if disabled else None)
    assert discovered.hidden_by is er.RegistryEntryHider.USER
    entity = hass.data["camera"].get_entity(discovered.entity_id)
    assert (entity is None) == disabled


@pytest.mark.parametrize("start_late", [False, True])
async def test_late_hidden_camera_is_not_published_and_user_show_survives_sync(
    hass: HomeAssistant, mock_api, start_late: bool
) -> None:
    entry = _entry(go2rtc=True)
    original_start = CameraStreamManager.async_start
    with (
        patch.object(Go2RtcClient, "async_list_streams", new=AsyncMock(return_value={})),
        patch.object(Go2RtcClient, "async_list_preloads", new=AsyncMock(return_value=set())),
        patch.object(Go2RtcClient, "async_patch_stream", new=AsyncMock(return_value=True)) as publish,
        patch.object(Go2RtcClient, "async_enable_preload", new=AsyncMock(return_value=True)),
        patch.object(Go2RtcClient, "async_disable_preload", new=AsyncMock(return_value=True)),
    ):
        if start_late:
            with patch.object(CameraStreamManager, "async_start", new=AsyncMock()):
                await _setup(hass, entry)
        else:
            await _setup(hass, entry)
        coordinator = entry.runtime_data
        coordinator.async_set_updated_data({
            **coordinator.data,
            "cameras": [{"id": 100, "hidden": True, "source": "public"}],
        })
        await hass.async_block_till_done()
        registered = _registry_camera(hass)
        assert registered is not None
        assert registered.hidden_by is er.RegistryEntryHider.INTEGRATION
        assert registered.options[DOMAIN]["we_set_integration"] is True
        manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
        if start_late:
            await original_start(manager)
        await manager.async_reconcile()
        assert not manager.is_camera_eligible("100")
        mock_api.query_camera_stream.assert_not_awaited()
        publish.assert_not_awaited()

        registry = er.async_get(hass)
        registry.async_update_entity(registered.entity_id, hidden_by=None)
        _sync_visibility(hass, entry, coordinator.data)
        shown = _registry_camera(hass)
        assert shown.hidden_by is None
        assert shown.options[DOMAIN]["user_shown"] is True
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
