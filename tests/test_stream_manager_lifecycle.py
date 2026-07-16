"""Config-entry lifecycle and camera delegation integration tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod import async_update_options
from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
    STREAM_MANAGER_DATA,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcStreamInfo
from custom_components.elektronny_gorod.stream_manager import (
    CameraStreamManager,
    StreamRefreshResult,
)
from custom_components.elektronny_gorod.user_agent import UserAgent


CAMERA_ID = "100"


@pytest.fixture
def mock_api():
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as api_cls:
        api = api_cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(
            return_value=[{
                "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
                "place": {"id": "P1", "address": "addr"},
            }]
        )
        api.query_balance = AsyncMock(return_value={})
        api.query_access_controls = AsyncMock(return_value=[])
        api.query_cameras = AsyncMock(return_value=[])
        api.query_public_cameras = AsyncMock(
            return_value=[{
                "id": int(CAMERA_ID),
                "externalCameraId": None,
                "name": "Front door",
            }]
        )
        api.query_screens_settings = AsyncMock(
            return_value={
                "screens": [
                    {
                        "type": "PUBLIC_CAMERAS",
                        "entities": [{
                            "id": int(CAMERA_ID),
                            "type": "PUBLIC_CAMERA",
                            "order": 0,
                        }],
                        "hidden": [],
                    },
                    {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
                ]
            }
        )
        api.query_dnd_settings = AsyncMock(return_value=[])
        api.query_camera_stream = AsyncMock(
            return_value="https://operator/100?token=OPERATOR_TOKEN"
        )
        api.query_camera_snapshot = AsyncMock(return_value=b"\x89PNG\r\n")
        yield api_cls


def _entry(*, keep_warm: bool = False) -> MockConfigEntry:
    user_agent = UserAgent()
    user_agent.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(user_agent.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "visibility_migration_v2": True,
            "use_go2rtc": True,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
            CONF_GO2RTC_KEEP_WARM: keep_warm,
            CONF_GO2RTC_KEEP_WARM_HIDDEN: False,
        },
    )


def _camera(hass: HomeAssistant):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "camera", DOMAIN, f"{DOMAIN}_camera_{CAMERA_ID}"
    )
    assert entity_id is not None
    return hass.data["camera"].get_entity(entity_id)


async def test_setup_exposes_one_started_manager_to_camera_platform(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=False)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
    assert isinstance(manager, CameraStreamManager)
    assert manager._started is True
    assert _camera(hass)._stream_manager is manager


async def test_visibility_sync_happens_before_manager_start(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=True)
    entry.add_to_hass(hass)
    events: list[str] = []

    with (
        patch(
            "custom_components.elektronny_gorod._sync_visibility",
            side_effect=lambda *args: events.append("visibility"),
        ),
        patch.object(
            CameraStreamManager,
            "async_start",
            new=AsyncMock(side_effect=lambda: events.append("start")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert events == ["visibility", "start"]


async def test_unload_stops_and_removes_manager(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert manager._started is False
    assert entry.entry_id not in hass.data.get(STREAM_MANAGER_DATA, {})
    assert manager._inflight == {}
    assert manager._due_unsubs == {}


async def test_unload_removes_adopted_manager_preload(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=True)
    entry.add_to_hass(hass)
    active = Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=1,
        producer_active=True,
    )

    with (
        patch.object(
            CameraStreamManager,
            "async_reconcile",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.elektronny_gorod.go2rtc.Go2RtcClient.async_list_preloads",
            new=AsyncMock(return_value={"eg_100"}),
        ),
        patch(
            "custom_components.elektronny_gorod.go2rtc.Go2RtcClient.async_list_streams",
            new=AsyncMock(return_value={"eg_100": active}),
        ),
        patch(
            "custom_components.elektronny_gorod.go2rtc.Go2RtcClient.async_disable_preload",
            new=AsyncMock(),
        ) as disable_preload,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
        manager._owned_preloads.add("eg_100")

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    disable_preload.assert_awaited_once_with("eg_100")


async def test_policy_only_options_update_skips_config_entry_reload(
    hass: HomeAssistant,
) -> None:
    entry = _entry(keep_warm=True)
    manager = MagicMock()
    manager.async_apply_entry_options = AsyncMock(return_value=True)
    hass.data.setdefault(STREAM_MANAGER_DATA, {})[entry.entry_id] = manager

    with patch.object(
        hass.config_entries,
        "async_reload",
        new=AsyncMock(),
    ) as reload_entry:
        await async_update_options(hass, entry)

    manager.async_apply_entry_options.assert_awaited_once_with()
    reload_entry.assert_not_awaited()


async def test_transport_options_update_keeps_config_entry_reload(
    hass: HomeAssistant,
) -> None:
    entry = _entry(keep_warm=True)
    manager = MagicMock()
    manager.async_apply_entry_options = AsyncMock(return_value=False)
    hass.data.setdefault(STREAM_MANAGER_DATA, {})[entry.entry_id] = manager

    with patch.object(
        hass.config_entries,
        "async_reload",
        new=AsyncMock(),
    ) as reload_entry:
        await async_update_options(hass, entry)

    manager.async_apply_entry_options.assert_awaited_once_with()
    reload_entry.assert_awaited_once_with(entry.entry_id)


async def test_camera_open_uses_manager_patch_not_legacy_writer(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=False)
    entry.add_to_hass(hass)
    new_patch = AsyncMock()

    with (
        patch(
            "custom_components.elektronny_gorod.go2rtc.Go2RtcClient.async_patch_stream",
            new=new_patch,
        ),
        patch(
            "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
            new=AsyncMock(),
            create=True,
        ) as legacy_patch,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        camera = _camera(hass)
        results = await asyncio.gather(
            camera.stream_source(),
            camera.stream_source(),
            camera.stream_source(),
        )

    assert results == [
        "rtsp://127.0.0.1:8554/eg_100",
        "rtsp://127.0.0.1:8554/eg_100",
        "rtsp://127.0.0.1:8554/eg_100",
    ]
    assert mock_api.return_value.query_camera_stream.await_count == 1
    assert new_patch.await_count == 1
    legacy_patch.assert_not_awaited()


async def test_recovery_refreshes_proxy_without_restarting_stable_ha_stream(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    camera = _camera(hass)
    manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
    manager.async_refresh = AsyncMock(
        return_value=StreamRefreshResult(
            url="rtsp://127.0.0.1:8554/eg_100",
            proxied=True,
        )
    )
    stream = MagicMock()
    stream.available = False
    camera.stream = stream
    camera._last_recovery_monotonic = -100.0

    camera._on_stream_state_change()
    await hass.async_block_till_done()

    manager.async_refresh.assert_awaited_once_with(CAMERA_ID, "recovery")
    stream.update_source.assert_not_called()


async def test_manager_stream_info_read_is_sanitized(
    hass: HomeAssistant,
    mock_api,
) -> None:
    entry = _entry(keep_warm=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[STREAM_MANAGER_DATA][entry.entry_id]
    manager.client.async_get_stream = AsyncMock(return_value=None)

    assert await manager.async_get_stream_info(CAMERA_ID) is None
    manager.client.async_get_stream.assert_awaited_once_with("eg_100")
