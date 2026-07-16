"""Registry policy and full-chain reconciliation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import (
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    DOMAIN,
)
from custom_components.elektronny_gorod.go2rtc import (
    Go2RtcRequestError,
    Go2RtcStreamInfo,
)
from custom_components.elektronny_gorod.stream_manager import CameraStreamManager


def _stream(*, consumers: int = 0) -> Go2RtcStreamInfo:
    return Go2RtcStreamInfo(
        producers=({"bytes_recv": 100},),
        consumer_count=consumers,
    )


def _setup(
    hass: HomeAssistant,
    *,
    keep_warm: bool = True,
    keep_hidden: bool = False,
    streams: dict[str, Go2RtcStreamInfo] | None = None,
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_GO2RTC_KEEP_WARM: keep_warm,
            CONF_GO2RTC_KEEP_WARM_HIDDEN: keep_hidden,
        },
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.data = {
        "cameras": [
            {"id": "100", "name": "Front door", "hidden": True},
            {"id": "200", "name": "Lift", "hidden": False},
        ]
    }
    counter = {"value": 0}

    async def mint(camera_id: str) -> str:
        counter["value"] += 1
        return (
            f"https://operator/{camera_id}"
            f"?token=MINT_{counter['value']}"
        )

    coordinator.get_camera_stream = AsyncMock(side_effect=mint)

    client = MagicMock()
    client.async_list_streams = AsyncMock(return_value=streams or {})
    client.async_patch_stream = AsyncMock()
    client.async_delete_stream = AsyncMock()
    client.rtsp_url = MagicMock(
        side_effect=lambda name, *, include_credentials: (
            f"rtsp://go2rtc:8554/{name}"
        )
    )
    manager = CameraStreamManager(
        hass=hass,
        entry=entry,
        coordinator=coordinator,
        client=client,
    )

    registry = er.async_get(hass)
    entries = {}
    for camera_id in ("100", "200"):
        entries[camera_id] = registry.async_get_or_create(
            "camera",
            DOMAIN,
            f"{DOMAIN}_camera_{camera_id}",
            suggested_object_id=f"camera_{camera_id}",
            config_entry=entry,
        )
    return manager, coordinator, client, registry, entries


@pytest.mark.parametrize(
    (
        "keep_warm",
        "disabled_by",
        "hidden_by",
        "keep_hidden",
        "expected",
    ),
    [
        (False, None, None, False, False),
        (True, None, None, False, True),
        (True, er.RegistryEntryDisabler.INTEGRATION, None, False, False),
        (True, er.RegistryEntryDisabler.USER, None, True, False),
        (True, None, er.RegistryEntryHider.INTEGRATION, False, False),
        (True, None, er.RegistryEntryHider.USER, False, False),
        (True, None, er.RegistryEntryHider.INTEGRATION, True, True),
        (True, None, er.RegistryEntryHider.USER, True, True),
    ],
)
async def test_registry_eligibility_matrix(
    hass: HomeAssistant,
    keep_warm,
    disabled_by,
    hidden_by,
    keep_hidden,
    expected,
) -> None:
    manager, _, _, registry, entries = _setup(
        hass,
        keep_warm=keep_warm,
        keep_hidden=keep_hidden,
    )
    registry.async_update_entity(
        entries["100"].entity_id,
        disabled_by=disabled_by,
        hidden_by=hidden_by,
    )

    assert manager.is_camera_eligible("100") is expected


async def test_api_hidden_flag_does_not_override_registry(
    hass: HomeAssistant,
) -> None:
    manager, _, _, _, _ = _setup(hass, keep_warm=True, keep_hidden=False)

    assert manager.coordinator.data["cameras"][0]["hidden"] is True
    assert manager.is_camera_eligible("100") is True


async def test_reconcile_uses_one_complete_stream_list_request(
    hass: HomeAssistant,
) -> None:
    manager, _, client, _, _ = _setup(
        hass,
        streams={"eg_100": _stream(), "eg_200": _stream(consumers=1)},
    )

    await manager.async_reconcile()

    client.async_list_streams.assert_awaited_once_with()
    client.async_patch_stream.assert_not_awaited()


async def test_missing_eligible_stream_runs_full_refresh_chain(
    hass: HomeAssistant,
) -> None:
    manager, coordinator, client, _, _ = _setup(hass, streams={})

    await manager.async_reconcile()

    assert coordinator.get_camera_stream.await_count == 2
    assert client.async_patch_stream.await_count == 2
    patched_names = {
        call.args[0] for call in client.async_patch_stream.await_args_list
    }
    assert patched_names == {"eg_100", "eg_200"}
    for call in client.async_patch_stream.await_args_list:
        assert call.args[1].startswith("ffmpeg:https://operator/")
        assert call.args[1].endswith("#video=copy#audio=aac#audio=opus")


async def test_go2rtc_restart_is_recovered_on_next_reconcile(
    hass: HomeAssistant,
) -> None:
    manager, coordinator, client, _, _ = _setup(hass, streams={})

    await manager.async_reconcile()
    assert client.async_patch_stream.await_count == 2

    # Simulated process restart: the in-memory go2rtc map is empty again.
    client.async_list_streams.return_value = {}
    await manager.async_reconcile()

    assert coordinator.get_camera_stream.await_count == 4
    assert client.async_patch_stream.await_count == 4


async def test_disabled_stream_with_no_consumers_is_deleted(
    hass: HomeAssistant,
) -> None:
    manager, coordinator, client, registry, entries = _setup(
        hass,
        streams={"eg_100": _stream(), "eg_200": _stream()},
    )
    registry.async_update_entity(
        entries["100"].entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await manager.async_reconcile()

    client.async_delete_stream.assert_awaited_once_with("eg_100")
    coordinator.get_camera_stream.assert_not_awaited()
    state = manager.camera_state("100")
    assert state is not None
    assert state.eligible is False
    assert state.present is False
    assert state.cleanup_pending is False


async def test_disabled_stream_with_consumers_defers_delete(
    hass: HomeAssistant,
) -> None:
    manager, _, client, registry, entries = _setup(
        hass,
        streams={"eg_100": _stream(consumers=2), "eg_200": _stream()},
    )
    registry.async_update_entity(
        entries["100"].entity_id,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await manager.async_reconcile()

    client.async_delete_stream.assert_not_awaited()
    state = manager.camera_state("100")
    assert state is not None
    assert state.present is True
    assert state.consumer_count == 2
    assert state.cleanup_pending is True
    assert state.status == "cleanup_pending"


async def test_deferred_cleanup_runs_when_consumers_reach_zero(
    hass: HomeAssistant,
) -> None:
    manager, _, client, registry, entries = _setup(
        hass,
        streams={"eg_100": _stream(consumers=1), "eg_200": _stream()},
    )
    registry.async_update_entity(
        entries["100"].entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await manager.async_reconcile()
    assert manager.camera_state("100").cleanup_pending is True

    client.async_list_streams.return_value = {
        "eg_100": _stream(consumers=0),
        "eg_200": _stream(),
    }
    await manager.async_reconcile()

    client.async_delete_stream.assert_awaited_once_with("eg_100")
    state = manager.camera_state("100")
    assert state is not None
    assert state.present is False
    assert state.cleanup_pending is False


@pytest.mark.parametrize(
    ("keep_hidden", "deleted", "eligible"),
    [(False, True, False), (True, False, True)],
)
async def test_hidden_stream_requires_hidden_suboption(
    hass: HomeAssistant,
    keep_hidden: bool,
    deleted: bool,
    eligible: bool,
) -> None:
    manager, _, client, registry, entries = _setup(
        hass,
        keep_hidden=keep_hidden,
        streams={"eg_100": _stream(), "eg_200": _stream()},
    )
    registry.async_update_entity(
        entries["100"].entity_id,
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )

    await manager.async_reconcile()

    if deleted:
        client.async_delete_stream.assert_awaited_once_with("eg_100")
    else:
        client.async_delete_stream.assert_not_awaited()
    assert manager.camera_state("100").eligible is eligible


async def test_keep_warm_off_does_not_delete_on_demand_streams(
    hass: HomeAssistant,
) -> None:
    manager, coordinator, client, _, _ = _setup(
        hass,
        keep_warm=False,
        streams={"eg_100": _stream(), "eg_200": _stream()},
    )

    await manager.async_reconcile()

    client.async_list_streams.assert_not_awaited()
    client.async_delete_stream.assert_not_awaited()
    coordinator.get_camera_stream.assert_not_awaited()


async def test_unknown_list_response_preserves_existing_streams(
    hass: HomeAssistant,
) -> None:
    manager, coordinator, client, _, _ = _setup(hass)
    client.async_list_streams.side_effect = Go2RtcRequestError(
        "list", "invalid_response"
    )

    await manager.async_reconcile()

    client.async_delete_stream.assert_not_awaited()
    client.async_patch_stream.assert_not_awaited()
    coordinator.get_camera_stream.assert_not_awaited()
