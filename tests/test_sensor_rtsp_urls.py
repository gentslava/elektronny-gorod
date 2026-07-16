"""Truthful, credential-free diagnostics for published external RTSP streams."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.elektronny_gorod import sensor as sensor_platform
from custom_components.elektronny_gorod.const import (
    DOMAIN,
    STREAM_MANAGER_DATA,
)
from custom_components.elektronny_gorod.stream_manager import (
    BACKGROUND_REFRESH_INTERVAL,
    ManagedCameraState,
)


class _ManagerStub:
    """Small sanitized manager surface consumed by the sensor."""

    def __init__(self, states: list[ManagedCameraState]) -> None:
        self.states = states
        self.listeners: set = set()
        self.operator_url = "https://operator/live?token=OPERATOR_TOKEN"
        self.client = MagicMock()
        self.client.rtsp_url.side_effect = (
            lambda name, *, include_credentials: (
                f"rtsp://user:SECRET_PASSWORD@go2rtc:8554/{name}"
                if include_credentials
                else f"rtsp://go2rtc:8554/{name}"
            )
        )

    def camera_states(self) -> tuple[ManagedCameraState, ...]:
        return tuple(self.states)

    def async_subscribe(self, listener):
        self.listeners.add(listener)

        def _unsubscribe() -> None:
            self.listeners.discard(listener)

        return _unsubscribe

    def notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()


def _state(
    camera_id: str,
    *,
    eligible: bool = True,
    present: bool = True,
    age: float | None = 60.0,
    status: str = "ready",
    name: str | None = None,
    preloaded: bool | None = None,
    producer_active: bool | None = None,
) -> ManagedCameraState:
    now = time.monotonic()
    return ManagedCameraState(
        camera_id=camera_id,
        stream_name=f"eg_{camera_id}",
        display_name=name or f"Camera {camera_id}",
        eligible=eligible,
        present=present,
        consumer_count=1 if present else 0,
        preloaded=present if preloaded is None else preloaded,
        producer_active=(
            present if producer_active is None else producer_active
        ),
        last_success=(
            datetime.now(timezone.utc) if age is not None else None
        ),
        last_success_monotonic=(now - age if age is not None else None),
        status=status,
    )


async def _platform_sensor(
    hass: HomeAssistant,
    manager: _ManagerStub | None,
):
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = MagicMock()
    coordinator.data = {"balances": [], "locks": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if manager is not None:
        hass.data.setdefault(STREAM_MANAGER_DATA, {})[
            entry.entry_id
        ] = manager

    entities = []
    await sensor_platform.async_setup_entry(hass, entry, entities.extend)
    sensor_type = getattr(
        sensor_platform,
        "ElektronnyGorodRtspUrlsSensor",
    )
    return next(entity for entity in entities if isinstance(entity, sensor_type))


async def test_sensor_counts_only_present_fresh_eligible_streams(
    hass: HomeAssistant,
) -> None:
    manager = _ManagerStub([
        _state("100", name="Front door"),
        _state(
            "200",
            age=BACKGROUND_REFRESH_INTERVAL.total_seconds() + 1,
        ),
        _state("300", eligible=False),
        _state("400", present=False, age=None, status="empty_source"),
    ])

    sensor = await _platform_sensor(hass, manager)

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["urls"] == {
        "Front door": "rtsp://go2rtc:8554/eg_100"
    }


async def test_sensor_does_not_claim_desired_but_failed_stream(
    hass: HomeAssistant,
) -> None:
    manager = _ManagerStub([
        _state(
            "100",
            present=False,
            age=None,
            status="patch_http_500",
        )
    ])

    sensor = await _platform_sensor(hass, manager)

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["urls"] == {}
    assert sensor.extra_state_attributes["streams"] == [{
        "camera_id": "100",
        "status": "patch_http_500",
        "present": False,
        "consumer_count": 0,
        "preloaded": False,
        "producer_active": False,
        "last_success": None,
    }]


async def test_sensor_requires_preload_and_active_producer(
    hass: HomeAssistant,
) -> None:
    manager = _ManagerStub([
        _state("100", preloaded=False),
        _state("200", producer_active=False),
        _state("300"),
    ])

    sensor = await _platform_sensor(hass, manager)

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["urls"] == {
        "Camera 300": "rtsp://go2rtc:8554/eg_300"
    }
    by_camera = {
        item["camera_id"]: item
        for item in sensor.extra_state_attributes["streams"]
    }
    assert by_camera["100"]["preloaded"] is False
    assert by_camera["200"]["producer_active"] is False
    assert by_camera["300"]["preloaded"] is True
    assert by_camera["300"]["producer_active"] is True


async def test_sensor_updates_when_manager_state_changes(
    hass: HomeAssistant,
) -> None:
    manager = _ManagerStub([
        _state("100", present=False, age=None, status="empty_source")
    ])
    sensor = await _platform_sensor(hass, manager)
    sensor.hass = hass
    sensor.async_write_ha_state = MagicMock()
    await sensor.async_added_to_hass()

    manager.states = [_state("100")]
    manager.notify()

    sensor.async_write_ha_state.assert_called_once_with()
    assert sensor.native_value == 1


async def test_sensor_urls_are_credential_free(hass: HomeAssistant) -> None:
    manager = _ManagerStub([_state("100", name="Front door")])

    sensor = await _platform_sensor(hass, manager)
    attributes = sensor.extra_state_attributes

    manager.client.rtsp_url.assert_called_with(
        "eg_100",
        include_credentials=False,
    )
    assert attributes["urls"]["Front door"] == (
        "rtsp://go2rtc:8554/eg_100"
    )
    assert "SECRET_PASSWORD" not in repr(attributes)
    assert "user:" not in repr(attributes)


async def test_sensor_attributes_never_contain_operator_url_or_token(
    hass: HomeAssistant,
) -> None:
    manager = _ManagerStub([
        _state("100", status="patch_client_error", name="Front door")
    ])

    sensor = await _platform_sensor(hass, manager)
    serialized = repr(sensor.extra_state_attributes)

    assert "operator/live" not in serialized
    assert "OPERATOR_TOKEN" not in serialized
    assert "SECRET_PASSWORD" not in serialized
    assert set(sensor.extra_state_attributes["streams"][0]) == {
        "camera_id",
        "status",
        "present",
        "consumer_count",
        "preloaded",
        "producer_active",
        "last_success",
    }


async def test_sensor_is_absent_when_go2rtc_is_disabled(
    hass: HomeAssistant,
) -> None:
    entry = SimpleNamespace(entry_id="entry-disabled")
    coordinator = MagicMock()
    coordinator.data = {"balances": [], "locks": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entities = []

    await sensor_platform.async_setup_entry(hass, entry, entities.extend)

    assert not any(
        type(entity).__name__ == "ElektronnyGorodRtspUrlsSensor"
        for entity in entities
    )
