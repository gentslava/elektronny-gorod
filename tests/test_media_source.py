"""Tests for the forpost camera archive Media Source."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import MediaSourceItem
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.elektronny_gorod.api import (
    CameraHistoryEvent,
    ForpostDownloadError,
)
from custom_components.elektronny_gorod.const import DOMAIN

_PLACE_ID = "1001"
_INTERCOM_ID = "111"
_PUBLIC_ID = "222"

_EVENT_TS = 1770000000


def _day_str(timestamp: int = _EVENT_TS) -> str:
    """Local calendar day (yyyymmdd) of an event timestamp."""
    from homeassistant.util import dt as dt_util

    return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).strftime(
        "%Y%m%d"
    )


def _coordinator(
    *,
    cameras: list | None = None,
    places: list | None = None,
    events: tuple = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        api=SimpleNamespace(
            query_camera_events=AsyncMock(return_value=tuple(events)),
            query_event_download=AsyncMock(
                return_value="https://savevideo.example/signed-clip.mp4"
            ),
        ),
        data={
            "places": (
                places
                if places is not None
                else [{"place": {"id": _PLACE_ID, "address": "ул. Тестовая 1"}}]
            ),
            "cameras": (
                cameras
                if cameras is not None
                else [
                    {
                        "id": _INTERCOM_ID,
                        "name": "Подъезд",
                        "place_id": _PLACE_ID,
                        "source": "intercom",
                    },
                    {
                        "id": _PUBLIC_ID,
                        "name": "Двор",
                        "place_id": _PLACE_ID,
                        "source": "public",
                    },
                ]
            ),
        },
    )


def _entry(hass, coordinator, *, title: str = "Test Account") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=title)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    return entry


def _source(hass):
    from custom_components.elektronny_gorod.media_source import (
        ElektronnyGorodMediaSource,
    )

    return ElektronnyGorodMediaSource(hass)


def _item(hass, identifier: str) -> MediaSourceItem:
    return MediaSourceItem(
        hass=hass, domain=DOMAIN, identifier=identifier, target_media_player=None
    )


async def test_root_lists_entries_with_places(hass) -> None:
    entry = _entry(hass, _coordinator())
    _entry(hass, _coordinator(places=[]), title="Empty Account")

    result = await _source(hass).async_browse_media(_item(hass, ""))

    assert [child.title for child in result.children] == ["Test Account"]
    assert result.media_content_id == f"media-source://{DOMAIN}"
    assert result.children[0].media_content_id == (
        f"media-source://{DOMAIN}/{entry.entry_id}"
    )
    assert result.children[0].can_expand is True
    assert result.children[0].can_play is False


async def test_root_without_entries_is_empty(hass) -> None:
    result = await _source(hass).async_browse_media(_item(hass, ""))
    assert result.children == []


async def test_browse_unknown_shape_raises(hass) -> None:
    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(_item(hass, "one-part"))


def _hide_camera(hass, entry, camera_id: str) -> None:
    registry = er.async_get(hass)
    created = registry.async_get_or_create(
        "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}", config_entry=entry
    )
    entity_id = getattr(created, "entity_id", created)
    registry.async_update_entity(entity_id, hidden_by=er.RegistryEntryHider.USER)


async def test_place_lists_intercom_and_public_cameras(hass) -> None:
    entry = _entry(hass, _coordinator())

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
    )

    assert [child.title for child in result.children] == ["Подъезд", "Двор"]
    assert result.children[0].media_content_id == (
        f"media-source://{DOMAIN}/{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}"
    )
    assert result.title == "ул. Тестовая 1"


async def test_place_omits_personal_and_hidden_cameras(hass) -> None:
    entry = _entry(
        hass,
        _coordinator(
            cameras=[
                {
                    "id": _INTERCOM_ID,
                    "name": "Подъезд",
                    "place_id": _PLACE_ID,
                    "source": "intercom",
                },
                {
                    "id": "333",
                    "name": "Личная",
                    "place_id": _PLACE_ID,
                    "source": "place",
                },
                {
                    "id": _PUBLIC_ID,
                    "name": "Двор",
                    "place_id": _PLACE_ID,
                    "source": "public",
                },
            ]
        ),
    )
    _hide_camera(hass, entry, _PUBLIC_ID)

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
    )

    assert [child.title for child in result.children] == ["Подъезд"]


async def test_place_without_cameras_hidden_from_root(hass) -> None:
    entry = _entry(hass, _coordinator(cameras=[]))

    root = await _source(hass).async_browse_media(_item(hass, ""))

    assert root.children == []
    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
        )


async def test_unknown_place_raises_browse_error(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/9999")
        )


async def test_camera_lists_retention_day_folders(hass) -> None:
    from homeassistant.util import dt as dt_util

    entry = _entry(hass, _coordinator())
    now = dt_util.now()

    intercom = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}")
    )
    public = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_PUBLIC_ID}")
    )

    assert len(intercom.children) == 14
    assert len(public.children) == 7
    today = now.date().isoformat()
    assert intercom.children[0].title == today
    assert intercom.children[0].media_content_id.endswith(
        now.strftime("%Y%m%d")
    )


async def test_unknown_camera_raises_browse_error(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/999")
        )


def _event(
    event_id: str = "3001",
    timestamp: int = 1770000000,
    duration: int = 12,
    subject: int = 126,
    available: bool = True,
    goto: bool = True,
) -> CameraHistoryEvent:
    return CameraHistoryEvent(
        id=event_id,
        camera_id=_INTERCOM_ID,
        backend_camera_id="4001",
        timestamp=timestamp,
        duration=duration,
        event_subject_id=subject,
        available=available,
        goto_enabled=goto,
    )


async def test_day_lists_motion_events_with_playability(hass) -> None:
    from homeassistant.util import dt as dt_util

    events = (
        _event(event_id="3002", timestamp=1770000060),
        _event(event_id="3001", timestamp=1770000000, goto=False),
        _event(event_id="9999", subject=99),
    )
    coordinator = _coordinator(events=events)
    entry = _entry(hass, coordinator)
    day = dt_util.as_local(dt_util.utc_from_timestamp(1770000000))
    day_str = day.strftime("%Y%m%d")
    day_start = dt_util.start_of_local_day(day)

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}")
    )

    coordinator.api.query_camera_events.assert_awaited_once_with(
        _INTERCOM_ID,
        lower_date=dt_util.as_utc(day_start).isoformat().replace("+00:00", "Z"),
        upper_date=dt_util.as_utc(day_start + timedelta(days=1))
        .isoformat()
        .replace("+00:00", "Z"),
    )
    assert [child.media_content_id.rsplit("/", 1)[-1] for child in result.children] == [
        "3002",
        "3001",
    ]
    assert result.children[0].can_play is True
    assert result.children[1].can_play is False
    assert result.children[0].title.endswith("· 12s")


async def test_day_api_failure_is_temporarily_unavailable(hass) -> None:
    from homeassistant.util import dt as dt_util

    coordinator = _coordinator()
    coordinator.api.query_camera_events.side_effect = RuntimeError("operator down")
    entry = _entry(hass, coordinator)
    day_str = dt_util.now().strftime("%Y%m%d")

    with pytest.raises(BrowseError, match="temporarily unavailable"):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day_str}")
        )


async def test_day_invalid_or_unknown_path_raises(hass) -> None:
    entry = _entry(hass, _coordinator())

    with pytest.raises(BrowseError, match="Unknown media item"):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/20261399")
        )


async def test_resolve_returns_play_media_for_valid_event(hass) -> None:
    coordinator = _coordinator(events=(_event(event_id="3001"),))
    entry = _entry(hass, coordinator)
    identifier = f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001"

    play = await _source(hass).async_resolve_media(_item(hass, identifier))

    coordinator.api.query_camera_events.assert_awaited_once()
    coordinator.api.query_event_download.assert_awaited_once_with("3001")
    assert play.url == "https://savevideo.example/signed-clip.mp4"
    assert play.mime_type == "video/mp4"


async def test_resolve_cross_camera_event_id_is_not_available(hass) -> None:
    """An event_id of another camera must not resolve via a visible path."""
    coordinator = _coordinator(events=(_event(event_id="3002"),))
    entry = _entry(hass, coordinator)

    with pytest.raises(Unresolvable, match="not available"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )

    coordinator.api.query_camera_events.assert_awaited_once()
    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_event_without_goto_is_not_available(hass) -> None:
    coordinator = _coordinator(events=(_event(event_id="3001", goto=False),))
    entry = _entry(hass, coordinator)

    with pytest.raises(Unresolvable, match="not available"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )

    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_rejects_malformed_event_id_and_day(hass) -> None:
    coordinator = _coordinator(events=(_event(event_id="3001"),))
    entry = _entry(hass, coordinator)
    day = _day_str()

    for bad_identifier in (
        f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day}/3001?x=1",
        f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{day}/../x",
        f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/20261399/3001",
    ):
        with pytest.raises(Unresolvable, match="Unknown media item"):
            await _source(hass).async_resolve_media(_item(hass, bad_identifier))

    coordinator.api.query_camera_events.assert_not_awaited()
    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_events_lookup_failure_is_temporarily_unavailable(
    hass,
) -> None:
    coordinator = _coordinator()
    coordinator.api.query_camera_events.side_effect = RuntimeError("operator down")
    entry = _entry(hass, coordinator)

    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )

    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_outside_retention(hass) -> None:
    from custom_components.elektronny_gorod.api import ForpostDownloadError

    coordinator = _coordinator(events=(_event(event_id="3001"),))
    coordinator.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError("11005")
    )
    entry = _entry(hass, coordinator)

    with pytest.raises(Unresolvable, match="outside the retention window"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )


async def test_resolve_no_recording_and_transport_error(hass) -> None:
    from custom_components.elektronny_gorod.api import ForpostDownloadError

    base = f"/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001"

    no_recording = _coordinator(events=(_event(event_id="3001"),))
    no_recording.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError(None)
    )
    entry_a = _entry(hass, no_recording)
    with pytest.raises(Unresolvable, match="not available"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry_a.entry_id}{base}")
        )

    transport = _coordinator(events=(_event(event_id="3001"),))
    transport.api.query_event_download = AsyncMock(
        side_effect=RuntimeError("operator down")
    )
    entry_b = _entry(hass, transport)
    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry_b.entry_id}{base}")
        )


async def test_resolve_rejects_unknown_and_hidden_paths(hass) -> None:
    coordinator = _coordinator()
    entry = _entry(hass, coordinator)
    _hide_camera(hass, entry, _PUBLIC_ID)
    day_str = _day_str()

    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/999/{day_str}/3001")
        )
    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_PUBLIC_ID}/{day_str}/3001")
        )
    with pytest.raises(Unresolvable, match="Unknown media item"):
        await _source(hass).async_resolve_media(_item(hass, "too/few/parts"))


async def test_resolve_never_logs_signed_url(hass, caplog) -> None:
    import logging

    coordinator = _coordinator(events=(_event(event_id="3001"),))
    entry = _entry(hass, coordinator)
    caplog.set_level(logging.DEBUG)

    await _source(hass).async_resolve_media(
        _item(
            hass,
            f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
        )
    )

    assert "savevideo.example" not in caplog.text


async def test_day_browse_failure_logs_opaque_context_only(hass, caplog) -> None:
    import logging

    coordinator = _coordinator()
    coordinator.api.query_camera_events.side_effect = RuntimeError("boom-secret")
    entry = _entry(hass, coordinator)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(BrowseError, match="temporarily unavailable"):
        await _source(hass).async_browse_media(
            _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}")
        )

    assert (
        "Media source day browse failed for camera_id=111 (RuntimeError)"
        in caplog.text
    )
    assert "boom-secret" not in caplog.text


async def test_resolve_failures_log_opaque_context_only(hass, caplog) -> None:
    import logging

    lookup = _coordinator()
    lookup.api.query_camera_events.side_effect = RuntimeError("boom-secret")
    entry_a = _entry(hass, lookup)

    download = _coordinator(events=(_event(event_id="3001"),))
    download.api.query_event_download.side_effect = RuntimeError("boom-secret")
    entry_b = _entry(hass, download)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry_a.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )
    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry_b.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )

    assert (
        caplog.text.count(
            "Media source resolve failed for camera_id=111 event_id=3001"
            " (RuntimeError)"
        )
        == 2
    )
    assert "boom-secret" not in caplog.text


def _full_config_entry() -> MockConfigEntry:
    import json

    from custom_components.elektronny_gorod.const import (
        CONF_ACCESS_TOKEN,
        CONF_OPERATOR_ID,
        CONF_REFRESH_TOKEN,
        CONF_USER_AGENT,
    )
    from custom_components.elektronny_gorod.user_agent import UserAgent

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
        },
    )


@pytest.fixture
def mock_full_api():
    from unittest.mock import patch

    from custom_components.elektronny_gorod.api import HistoryPage

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = MagicMock()
        instance.query_places = AsyncMock(
            return_value=[
                {
                    "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
                    "place": {"id": _PLACE_ID, "address": "ул. Тестовая 1"},
                }
            ]
        )
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(
            return_value=[
                {
                    "id": 2001,
                    "name": "Домофон",
                    "entrances": [
                        {
                            "id": 3001,
                            "name": "Подъезд",
                            "externalCameraId": int(_INTERCOM_ID),
                            "allowOpen": True,
                        }
                    ],
                }
            ]
        )
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(
            return_value=[{"id": int(_PUBLIC_ID), "name": "Двор"}]
        )
        instance.query_screens_settings = AsyncMock(
            return_value={"screens": []}
        )
        instance.query_dnd_settings = AsyncMock(return_value=[])
        instance.query_events = AsyncMock(
            return_value=HistoryPage(events=(), number=0, last=True)
        )
        yield mock_cls


async def test_media_source_registered_on_integration_setup(
    hass, mock_full_api
) -> None:
    from homeassistant.components.media_source import async_browse_media
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "media_source", {})
    entry = _full_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data["media_source"]
    browse = await async_browse_media(hass, f"media-source://{DOMAIN}")
    assert browse.children[0].title == "Test"


async def test_public_camera_grouped_under_place_end_to_end(
    hass, mock_full_api
) -> None:
    """The coordinator place_id fix routes public cameras into the place."""
    from homeassistant.components.media_source import async_browse_media
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "media_source", {})
    entry = _full_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    place = await async_browse_media(
        hass, f"media-source://{DOMAIN}/{entry.entry_id}/{_PLACE_ID}"
    )
    assert [child.title for child in place.children] == ["Подъезд", "Двор"]


async def test_root_aggregates_multiple_entries(hass) -> None:
    _entry(hass, _coordinator(), title="Account B")
    _entry(hass, _coordinator(), title="Account A")

    result = await _source(hass).async_browse_media(_item(hass, ""))

    assert [child.title for child in result.children] == ["Account A", "Account B"]


async def test_entry_lists_place_folders(hass) -> None:
    """Expanding the account folder must list its places (regression: A)."""
    entry = _entry(hass, _coordinator())

    result = await _source(hass).async_browse_media(_item(hass, entry.entry_id))

    assert result.title == "Test Account"
    assert [child.title for child in result.children] == ["ул. Тестовая 1"]
    assert result.children[0].media_content_id == (
        f"media-source://{DOMAIN}/{entry.entry_id}/{_PLACE_ID}"
    )
    assert result.children[0].can_expand is True


async def test_entry_lists_only_places_with_cameras(hass) -> None:
    places = [
        {"place": {"id": _PLACE_ID, "address": "ул. Тестовая 1"}},
        {"place": {"id": "1002", "address": "ул. Вторая 2"}},
    ]
    entry = _entry(hass, _coordinator(places=places))

    result = await _source(hass).async_browse_media(_item(hass, entry.entry_id))

    assert [child.title for child in result.children] == ["ул. Тестовая 1"]


async def test_entry_without_cameras_or_unknown_entry_raises(hass) -> None:
    empty = _entry(hass, _coordinator(cameras=[]))
    _entry(hass, _coordinator())

    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(_item(hass, empty.entry_id))
    with pytest.raises(BrowseError):
        await _source(hass).async_browse_media(_item(hass, "no-such-entry"))


def _resolve_item(hass, entry, camera_id=_INTERCOM_ID, event_id="3001") -> MediaSourceItem:
    day_str = dt_util.as_local(dt_util.utc_from_timestamp(_EVENT_TS)).strftime(
        "%Y%m%d"
    )
    return _item(
        hass,
        f"{entry.entry_id}/{_PLACE_ID}/{camera_id}/{day_str}/{event_id}",
    )


def _patched_prepare_clock(ticks):
    fake_time = MagicMock()
    fake_time.monotonic.side_effect = ticks
    return patch(
        "custom_components.elektronny_gorod.media_source.time", fake_time
    )


async def test_resolve_polls_while_file_prepares(hass) -> None:
    """ErrorCode 102 = server-side rendering: bounded poll until the link."""
    coordinator = _coordinator(events=(_event(),))
    coordinator.api.query_event_download = AsyncMock(
        side_effect=[
            ForpostDownloadError("102"),
            ForpostDownloadError("102"),
            "https://savevideo.example/signed-clip.mp4",
        ]
    )
    entry = _entry(hass, coordinator)

    with patch(
        "custom_components.elektronny_gorod.media_source.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock, _patched_prepare_clock([0, 1, 3]):
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert play.url == "https://savevideo.example/signed-clip.mp4"
    assert coordinator.api.query_event_download.await_count == 3
    assert sleep_mock.await_count == 2


async def test_resolve_prepare_timeout_is_being_prepared(hass) -> None:
    coordinator = _coordinator(events=(_event(),))
    coordinator.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError("102")
    )
    entry = _entry(hass, coordinator)

    with patch(
        "custom_components.elektronny_gorod.media_source.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock, _patched_prepare_clock([0, 1, 3, 5, 7, 100]):
        with pytest.raises(Unresolvable, match="being prepared"):
            await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert coordinator.api.query_event_download.await_count == 5
    assert sleep_mock.await_count == 4
