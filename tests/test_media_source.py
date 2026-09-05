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

    hass.config.language = "ru"
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
    assert result.children[0].title.endswith("· 12 сек")


RU_LABELS = {
    "duration_min_sec": "{minutes} мин {seconds} сек",
    "duration_min": "{minutes} мин",
    "duration_sec": "{seconds} сек",
}


async def test_duration_labels_follow_instance_language(hass) -> None:
    """Labels come from the `common` category keyed by HA instance lang."""
    source = _source(hass)
    hass.config.language = "ru"
    ru_payload = {
        f"component.{DOMAIN}.common.{key}": value
        for key, value in RU_LABELS.items()
    }
    with patch(
        "custom_components.elektronny_gorod.media_source.translation"
        ".async_get_translations",
        AsyncMock(return_value=ru_payload),
    ) as get_translations:
        labels = await source._duration_labels()

    assert labels == RU_LABELS
    get_translations.assert_awaited_once_with(hass, "ru", "common", {DOMAIN})


async def test_duration_labels_from_real_translation_files(hass) -> None:
    """Non-mocked: the loader serves our ru strings under `common` keys."""
    from homeassistant.helpers import translation

    source = _source(hass)
    hass.config.language = "ru"
    fetched = await translation.async_get_translations(
        hass, "ru", "common", {DOMAIN}
    )
    labels = await source._duration_labels()

    assert fetched.get(f"component.{DOMAIN}.common.duration_min") == (
        "{minutes} мин"
    )
    assert labels == RU_LABELS


async def test_duration_labels_fetch_error_falls_back(hass) -> None:
    """A crashing translation helper degrades to English labels."""
    source = _source(hass)
    hass.config.language = "ru"
    with patch(
        "custom_components.elektronny_gorod.media_source.translation"
        ".async_get_translations",
        AsyncMock(side_effect=RuntimeError("loader down")),
    ):
        labels = await source._duration_labels()

    assert labels["duration_min_sec"] == "{minutes} min {seconds} sec"


async def test_duration_labels_fallback_to_english(hass) -> None:
    """Missing translations degrade to built-in English labels."""
    source = _source(hass)
    hass.config.language = "de"
    with patch(
        "custom_components.elektronny_gorod.media_source.translation"
        ".async_get_translations",
        AsyncMock(return_value={}),
    ):
        labels = await source._duration_labels()

    assert labels["duration_min_sec"] == "{minutes} min {seconds} sec"
    assert labels["duration_min"] == "{minutes} min"
    assert labels["duration_sec"] == "{seconds} sec"


def test_translation_files_carry_duration_labels_in_common() -> None:
    """hassfest rejects non-standard categories; durations live in `common`."""
    import json
    from pathlib import Path

    base = (
        Path(__file__).parent.parent
        / "custom_components"
        / "elektronny_gorod"
    )
    for name in (
        "strings.json",
        "translations/en.json",
        "translations/ru.json",
    ):
        with (base / name).open(encoding="utf-8") as file:
            data = json.load(file)
        assert "media" not in data, name
        for key in ("duration_min_sec", "duration_min", "duration_sec"):
            assert key in data["common"], f"{name}: {key} missing in common"


def _event_title_for(duration: int, labels: dict) -> str:
    from custom_components.elektronny_gorod.media_source import (
        ElektronnyGorodMediaSource,
    )

    return ElektronnyGorodMediaSource._event_title(
        SimpleNamespace(timestamp=1770000000, duration=duration), labels
    )


async def test_event_title_formats_duration_localized(hass) -> None:
    """Duration renders localized: ru 'X мин Y сек', en 'X min Y sec'."""
    assert _event_title_for(45, RU_LABELS).endswith("· 45 сек")
    assert _event_title_for(125, RU_LABELS).endswith("· 2 мин 5 сек")
    assert _event_title_for(120, RU_LABELS).endswith("· 2 мин")
    assert _event_title_for(3661, RU_LABELS).endswith("· 61 мин 1 сек")

    en = {
        "duration_min_sec": "{minutes} min {seconds} sec",
        "duration_min": "{minutes} min",
        "duration_sec": "{seconds} sec",
    }
    assert _event_title_for(125, en).endswith("· 2 min 5 sec")
    assert _event_title_for(120, en).endswith("· 2 min")
    assert _event_title_for(45, en).endswith("· 45 sec")


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
    coordinator.api.query_event_download.assert_not_awaited()
    assert play.mime_type == "video/mp4"
    assert play.url.startswith(
        f"/api/elektronny_gorod/clips/{entry.entry_id}/3001?t="
    )
    assert "savevideo.example" not in play.url


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

    caplog.set_level(logging.DEBUG)

    with pytest.raises(Unresolvable, match="temporarily unavailable"):
        await _source(hass).async_resolve_media(
            _item(
                hass,
                f"{entry_a.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001",
            )
        )

    assert (
        caplog.text.count(
            "Media source resolve failed for camera_id=111 event_id=3001"
            " (RuntimeError)"
        )
        == 1
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

    # HA 2026.8 убрал `hass.data["media_source"]`: реестр платформ ленивый.
    # Регистрацию проверяем через публичный корневой browse.
    root = await async_browse_media(hass, "media-source://")
    assert any(
        child.identifier == DOMAIN or child.media_content_id.startswith(
            f"media-source://{DOMAIN}"
        )
        for child in root.children
    )
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


async def test_resolve_never_mints_the_operator_link(hass) -> None:
    """Регрессия: ожидание готовности жило и в resolve, и в прокси.

    Каждый минт запускает подготовку mp4 заново (снимок 2026-05-25: 4 отказа
    423 и ~11 с ожидания), поэтому минт должен быть ровно один — в прокси.
    """
    coordinator = _coordinator(events=(_event(),))
    coordinator.api.query_event_download = AsyncMock(
        return_value="https://savevideo.example/signed-clip.mp4"
    )
    entry = _entry(hass, coordinator)

    await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_event_download.assert_not_awaited()


async def test_hidden_camera_without_registry_entry_stays_hidden(hass) -> None:
    """Регрессия: видимость определялась только по entity registry.

    Камера, скрытая у оператора, но ещё не заведённая как сущность (появилась
    в аккаунте после setup либо сущность удалили), попадала в архив.
    """
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
                    "id": _PUBLIC_ID,
                    "name": "Двор",
                    "place_id": _PLACE_ID,
                    "source": "public",
                    "hidden": True,
                },
            ]
        ),
    )

    source = _source(hass)
    result = await source.async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}")
    )

    assert [child.title for child in result.children] == ["Подъезд"]
    assert source._camera(entry.entry_id, _PLACE_ID, _PUBLIC_ID) is None
