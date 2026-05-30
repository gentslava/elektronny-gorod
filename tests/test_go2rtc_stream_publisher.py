"""Tests for background go2rtc stream publishing."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.const import (
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_PUBLISH_HIDDEN,
    CONF_GO2RTC_RTSP_HOST,
    CONF_USE_GO2RTC,
)


def _entry(data: dict, options: dict | None = None):
    return SimpleNamespace(data=data, options=options or {}, entry_id="entry-1")


def _coordinator(cameras: list[dict]):
    return SimpleNamespace(
        data={"cameras": cameras},
        get_camera_stream=AsyncMock(
            side_effect=lambda camera_id: f"https://operator.example/{camera_id}.flv"
        ),
    )


@pytest.mark.asyncio
async def test_sync_once_publishes_all_operator_cameras_to_go2rtc():
    """Enabled go2rtc publishes streams without waiting for HA camera playback."""
    from custom_components.elektronny_gorod.go2rtc_stream_publisher import (
        Go2RtcStreamPublisher,
    )

    hass = MagicMock()
    session = MagicMock()
    response = AsyncMock()
    response.status = 200
    session.patch.return_value.__aenter__.return_value = response

    entry = _entry(
        {
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            CONF_GO2RTC_RTSP_HOST: "127.0.0.1",
        }
    )
    coordinator = _coordinator([
        {"id": "111", "name": "Подъезд"},
        {"id": "222", "name": "Двор"},
    ])

    with patch(
        "custom_components.elektronny_gorod.go2rtc_stream_publisher.async_get_clientsession",
        return_value=session,
    ):
        publisher = Go2RtcStreamPublisher(hass, entry, coordinator)
        await publisher.async_sync_once()

    assert coordinator.get_camera_stream.await_args_list[0].args == ("111",)
    assert coordinator.get_camera_stream.await_args_list[1].args == ("222",)
    assert session.patch.call_count == 2
    first_url = session.patch.call_args_list[0].args[0]
    second_url = session.patch.call_args_list[1].args[0]
    assert "name=eg_111" in first_url
    assert "src=https%3A%2F%2Foperator.example%2F111.flv" in first_url
    assert "name=eg_222" in second_url


@pytest.mark.asyncio
async def test_sync_once_does_nothing_when_go2rtc_disabled():
    """Disabled go2rtc does not fetch temporary operator stream URLs."""
    from custom_components.elektronny_gorod.go2rtc_stream_publisher import (
        Go2RtcStreamPublisher,
    )

    hass = MagicMock()
    entry = _entry({CONF_USE_GO2RTC: False})
    coordinator = _coordinator([{"id": "111", "name": "Подъезд"}])

    publisher = Go2RtcStreamPublisher(hass, entry, coordinator)
    await publisher.async_sync_once()

    coordinator.get_camera_stream.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_once_can_skip_hidden_cameras():
    """Publisher skips hidden cameras when configured to publish visible only."""
    from custom_components.elektronny_gorod.go2rtc_stream_publisher import (
        Go2RtcStreamPublisher,
    )

    hass = MagicMock()
    session = MagicMock()
    response = AsyncMock()
    response.status = 200
    session.patch.return_value.__aenter__.return_value = response

    entry = _entry(
        {
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            CONF_GO2RTC_RTSP_HOST: "127.0.0.1",
            CONF_GO2RTC_PUBLISH_HIDDEN: False,
        }
    )
    coordinator = _coordinator([
        {"id": "111", "name": "Подъезд"},
        {"id": "222", "name": "Скрытая", "hidden": True},
    ])

    with patch(
        "custom_components.elektronny_gorod.go2rtc_stream_publisher.async_get_clientsession",
        return_value=session,
    ):
        publisher = Go2RtcStreamPublisher(hass, entry, coordinator)
        await publisher.async_sync_once()

    coordinator.get_camera_stream.assert_awaited_once_with("111")
    assert session.patch.call_count == 1
