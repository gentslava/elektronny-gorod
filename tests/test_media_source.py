"""Tests for the forpost camera archive Media Source."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState

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
            # По умолчанию поток архива недоступен: тесты шага 1 (A-124)
            # проверяют эфир, то есть ветку отката шага 2.
            query_camera_archive_stream=AsyncMock(return_value=None),
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
    entry.runtime_data = coordinator
    entry.mock_state(hass, ConfigEntryState.LOADED)
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
    "recording_in_progress": "Идёт запись",
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
        for key in (
            "duration_min_sec",
            "duration_min",
            "duration_sec",
            "recording_in_progress",
        ):
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


def _resolve_item(
    hass, entry, camera_id=_INTERCOM_ID, event_id="3001", *, day_str: str | None = None
) -> MediaSourceItem:
    if day_str is None:
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


async def test_root_skips_entry_that_is_not_loaded(hass) -> None:
    """Незагруженная запись не роняет корень медиабраузера.

    Корень читает `runtime_data` напрямую, полагаясь на то, что перебираются
    только загруженные записи. Если это перестанет быть правдой, вторая
    учётная запись в состоянии повторной попытки — обычное дело при
    протухшей авторизации — уронит браузер целиком, вместе с архивом
    здорового аккаунта.
    """
    _entry(hass, _coordinator(), title="Loaded Account")
    MockConfigEntry(domain=DOMAIN, title="Not Loaded Account").add_to_hass(hass)

    result = await _source(hass).async_browse_media(_item(hass, ""))

    assert [child.title for child in result.children] == ["Loaded Account"]



# --- A-124: идущее событие открывает эфир камеры ---------------------------

_LIVE_EVENT_DURATION = 30
_LIVE_EVENT_END = _EVENT_TS + _LIVE_EVENT_DURATION
_LIVE_PLAY_URL = "/api/hls/test-token/master_playlist.m3u8"


def _local_hms(timestamp: int) -> str:
    return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).strftime(
        "%H:%M:%S"
    )


def _register_camera_entity(hass, entry, camera_id: str = _INTERCOM_ID) -> str:
    registry = er.async_get(hass)
    created = registry.async_get_or_create(
        "camera", DOMAIN, f"{DOMAIN}_camera_{camera_id}", config_entry=entry
    )
    return created.entity_id


def _live_event(event_id: str = "3001") -> CameraHistoryEvent:
    return _event(
        event_id=event_id, timestamp=_EVENT_TS, duration=_LIVE_EVENT_DURATION
    )


def _patch_camera_resolve(**kwargs):
    from homeassistant.components.media_source.models import PlayMedia

    kwargs.setdefault(
        "return_value",
        PlayMedia(url=_LIVE_PLAY_URL, mime_type="application/vnd.apple.mpegurl"),
    )
    return patch(
        "homeassistant.components.media_source.async_resolve_media",
        AsyncMock(**kwargs),
    )


async def test_day_marks_in_progress_event_and_keeps_it_playable(
    hass, freezer
) -> None:
    """Окончание в будущем → «● Идёт запись · HH:MM:SS», играемо."""
    finished_ts = _EVENT_TS - 600
    events = (
        _live_event(event_id="3002"),
        _event(event_id="3001", timestamp=finished_ts, duration=12),
    )
    entry = _entry(hass, _coordinator(events=events))
    # Оператор держит окончание идущего события на несколько секунд впереди.
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    hass.config.language = "ru"

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}")
    )

    live, finished = result.children
    assert live.title == f"● Идёт запись · {_local_hms(_EVENT_TS)}"
    assert live.can_play is True
    assert finished.title == f"{_local_hms(finished_ts)} · 12 сек"
    assert finished.can_play is True


async def test_day_event_past_grace_keeps_finished_title(hass, freezer) -> None:
    """Окончание ровно на границе grace — событие уже завершено."""
    from custom_components.elektronny_gorod.media_source import _LIVE_GRACE_SEC

    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    freezer.move_to(
        dt_util.utc_from_timestamp(_LIVE_EVENT_END + _LIVE_GRACE_SEC)
    )
    hass.config.language = "ru"

    result = await _source(hass).async_browse_media(
        _item(hass, f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}")
    )

    assert result.children[0].title == f"{_local_hms(_EVENT_TS)} · 30 сек"


def test_live_grace_is_fifteen_seconds() -> None:
    from custom_components.elektronny_gorod.media_source import _LIVE_GRACE_SEC

    assert _LIVE_GRACE_SEC == 15


async def test_resolve_in_progress_event_returns_camera_live_view(
    hass, freezer
) -> None:
    coordinator = _coordinator(events=(_live_event(),))
    entry = _entry(hass, coordinator)
    entity_id = _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))

    with _patch_camera_resolve() as camera_resolve:
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    camera_resolve.assert_awaited_once_with(
        hass, f"media-source://camera/{entity_id}", None
    )
    assert play.url == _LIVE_PLAY_URL
    assert "/api/elektronny_gorod/clips/" not in play.url
    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_live_view_hls_mime_normalised_for_frontend(
    hass, freezer
) -> None:
    """Плеер медиабраузера HA понимает только application/x-mpegURL."""
    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))

    with _patch_camera_resolve():
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert play.url == _LIVE_PLAY_URL
    assert play.mime_type == "application/x-mpegURL"


async def test_resolve_live_view_non_hls_mime_passes_through(
    hass, freezer
) -> None:
    from homeassistant.components.media_source.models import PlayMedia

    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    mjpeg = PlayMedia(
        url="/api/camera_proxy_stream/camera.x?token=t",
        mime_type="multipart/x-mixed-replace",
    )

    with _patch_camera_resolve(return_value=mjpeg):
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert play.url == mjpeg.url
    assert play.mime_type == "multipart/x-mixed-replace"


async def test_resolve_live_view_passes_target_media_player(hass, freezer) -> None:
    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    entity_id = _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    item = MediaSourceItem(
        hass=hass,
        domain=DOMAIN,
        identifier=(
            f"{entry.entry_id}/{_PLACE_ID}/{_INTERCOM_ID}/{_day_str()}/3001"
        ),
        target_media_player="media_player.tv",
    )

    with _patch_camera_resolve() as camera_resolve:
        await _source(hass).async_resolve_media(item)

    camera_resolve.assert_awaited_once_with(
        hass, f"media-source://camera/{entity_id}", "media_player.tv"
    )


async def test_resolve_grace_boundary(hass, freezer) -> None:
    """end > now - grace → эфир; end == now - grace → клип как раньше."""
    from custom_components.elektronny_gorod.media_source import _LIVE_GRACE_SEC

    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    _register_camera_entity(hass, entry)

    freezer.move_to(
        dt_util.utc_from_timestamp(_LIVE_EVENT_END + _LIVE_GRACE_SEC - 1)
    )
    with _patch_camera_resolve() as camera_resolve:
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))
    camera_resolve.assert_awaited_once()
    assert play.url == _LIVE_PLAY_URL

    freezer.move_to(
        dt_util.utc_from_timestamp(_LIVE_EVENT_END + _LIVE_GRACE_SEC)
    )
    with _patch_camera_resolve() as camera_resolve:
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))
    camera_resolve.assert_not_awaited()
    assert play.mime_type == "video/mp4"
    assert play.url.startswith(
        f"/api/elektronny_gorod/clips/{entry.entry_id}/3001?t="
    )


async def test_resolve_in_progress_without_camera_entity_is_unresolvable(
    hass, freezer
) -> None:
    coordinator = _coordinator(events=(_live_event(),))
    entry = _entry(hass, coordinator)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))

    with (
        _patch_camera_resolve() as camera_resolve,
        pytest.raises(Unresolvable, match="Live view is not available"),
    ):
        await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    camera_resolve.assert_not_awaited()
    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_in_progress_with_disabled_camera_is_unresolvable(
    hass, freezer
) -> None:
    entry = _entry(hass, _coordinator(events=(_live_event(),)))
    entity_id = _register_camera_entity(hass, entry)
    er.async_get(hass).async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))

    with (
        _patch_camera_resolve() as camera_resolve,
        pytest.raises(Unresolvable, match="Live view is not available"),
    ):
        await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    camera_resolve.assert_not_awaited()


async def test_resolve_in_progress_live_failure_does_not_fall_back_to_clip(
    hass, freezer, caplog
) -> None:
    import logging

    coordinator = _coordinator(events=(_live_event(),))
    entry = _entry(hass, coordinator)
    _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    caplog.set_level(logging.DEBUG)

    with (
        _patch_camera_resolve(
            side_effect=Unresolvable("Stream integration not loaded")
        ),
        pytest.raises(Unresolvable, match="Live view is not available"),
    ):
        await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_event_download.assert_not_awaited()
    assert "/api/elektronny_gorod/clips/" not in caplog.text
    assert "savevideo.example" not in caplog.text


async def test_resolve_live_view_uses_real_ha_resolver(hass, freezer) -> None:
    """Без мока: публичный `media_source.async_resolve_media` HA реально
    вызывается; его отказ (media_source не загружен) → наш Unresolvable."""
    coordinator = _coordinator(events=(_live_event(),))
    entry = _entry(hass, coordinator)
    _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    assert "media_source" not in hass.config.top_level_components

    with pytest.raises(Unresolvable, match="Live view is not available"):
        await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_event_download.assert_not_awaited()


async def test_resolve_finished_event_never_requests_archive_stream(
    hass, freezer
) -> None:
    """Завершённое событие остаётся MP4 через прокси клипа (A-124 шаг 2)."""
    from custom_components.elektronny_gorod.media_source import _LIVE_GRACE_SEC

    coordinator = _coordinator(events=(_live_event(),))
    entry = _entry(hass, coordinator)
    freezer.move_to(
        dt_util.utc_from_timestamp(_LIVE_EVENT_END + _LIVE_GRACE_SEC)
    )

    play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert play.mime_type == "video/mp4"
    coordinator.api.query_camera_archive_stream.assert_not_awaited()


# --- A-124 шаг 2: идущее событие играет с начала EVENT HLS архивом ----------

_ARCHIVE_URL = "https://forpost-1.example:18081/rtsp/STREAM-ID/SIGNED-TOKEN/d=1"
_HLS_MIME = "application/x-mpegURL"


def _patch_archive_start(
    *,
    ready_segments: int = 1,
    fail_async: bool = False,
    side_effect=None,
    created: list | None = None,
):
    """Синтетический старт `ArchiveHlsSession` без сети и PyAV."""
    from contextlib import ExitStack

    from custom_components.elektronny_gorod.archive_hls import ArchiveHlsSession

    async def _noop_stop(self) -> None:
        self._closed = True
        self._cancel_idle_timer()
        self.fail_event.set()
        self._segments.clear()

    def _fake_start(self, source_url: str) -> None:
        if created is not None:
            created.append((self, source_url))
        self.touch()
        if side_effect is not None:
            return side_effect(self, source_url)
        if fail_async:
            self.hass.loop.call_soon(self.mark_failed)
            return
        for idx in range(ready_segments):
            self.add_segment(2.0, f"SEG{idx}".encode())

    stack = ExitStack()
    stack.enter_context(
        patch.multiple(ArchiveHlsSession, start=_fake_start, stop=_noop_stop)
    )
    stack.enter_context(
        patch(
            "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
            AsyncMock(return_value=True),
        )
    )
    return stack


def _archive_entry(hass, *, url: str | None = _ARCHIVE_URL):
    coordinator = _coordinator(events=(_live_event(),))
    coordinator.api.query_camera_archive_stream = AsyncMock(return_value=url)
    entry = _entry(hass, coordinator)
    _register_camera_entity(hass, entry)
    return coordinator, entry


def _realtime_archive_entry(hass, *, url: str | None = _ARCHIVE_URL):
    """Идущее событие относительно реальных часов — без `freezer` для реальных таймаутов."""
    now_ts = int(dt_util.utcnow().timestamp())
    event = _event(event_id="3001", timestamp=now_ts - 10, duration=60)
    coordinator = _coordinator(events=(event,))
    coordinator.api.query_camera_archive_stream = AsyncMock(return_value=url)
    entry = _entry(hass, coordinator)
    _register_camera_entity(hass, entry)
    return coordinator, entry, _day_str(event.timestamp)


async def test_tz_offset_follows_ha_time_zone_at_event_time(hass) -> None:
    """TZ — смещение часового пояса HA в момент события, в секундах."""
    from datetime import datetime as dt, timezone

    from custom_components.elektronny_gorod.media_source import _tz_offset

    await hass.config.async_set_time_zone("Asia/Novosibirsk")
    assert _tz_offset(_EVENT_TS) == 25200

    await hass.config.async_set_time_zone("Europe/Berlin")
    winter = int(dt(2026, 1, 15, 12, tzinfo=timezone.utc).timestamp())
    summer = int(dt(2026, 7, 15, 12, tzinfo=timezone.utc).timestamp())
    assert _tz_offset(winter) == 3600
    assert _tz_offset(summer) == 7200


async def test_get_media_source_registers_clip_and_archive_views(hass) -> None:
    from homeassistant.setup import async_setup_component

    from custom_components.elektronny_gorod.media_source import (
        async_get_media_source,
    )

    assert await async_setup_component(hass, "http", {})
    source = await async_get_media_source(hass)
    assert source.domain == DOMAIN
    assert hass.data.get(f"{DOMAIN}_clip_view_registered") is True
    assert hass.data.get(f"{DOMAIN}_archive_view_registered") is True


async def test_resolve_in_progress_plays_archive_from_event_start_as_hls(
    hass, freezer, caplog
) -> None:
    """Поток архива с начала события → same-origin EVENT HLS с sequence 0."""
    import logging

    from homeassistant.setup import async_setup_component

    from custom_components.elektronny_gorod.archive_hls import (
        async_register_archive_view,
    )

    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, "http", {})
    async_register_archive_view(hass)
    await hass.config.async_set_time_zone("Asia/Novosibirsk")
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    created: list = []

    with _patch_archive_start(created=created), _patch_camera_resolve() as camera_resolve:
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_camera_archive_stream.assert_awaited_once_with(
        _INTERCOM_ID, _EVENT_TS, 25200
    )
    assert len(created) == 1
    session, source_url = created[0]
    assert source_url == _ARCHIVE_URL
    assert play.url.startswith(
        f"/api/elektronny_gorod/archive/{session.session_id}/playlist.m3u8?t="
    )
    assert "SIGNED-TOKEN" not in play.url
    assert "forpost-1.example" not in play.url
    assert "SIGNED-TOKEN" not in caplog.text
    # Плеер медиабраузера HA играет HLS только с этим MIME (прод 2026-10-26).
    assert play.mime_type == _HLS_MIME
    camera_resolve.assert_not_awaited()
    coordinator.api.query_event_download.assert_not_awaited()
    await session.stop()


async def test_resolve_in_progress_reuses_alive_archive_stream(
    hass, freezer
) -> None:
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created):
        first = await source.async_resolve_media(_resolve_item(hass, entry))
        second = await source.async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_camera_archive_stream.assert_awaited_once()
    assert len(created) == 1
    assert second.url.split("?t=", 1)[0] == first.url.split("?t=", 1)[0]
    await created[0][0].stop()


async def test_concurrent_resolves_share_one_archive_stream(hass, freezer) -> None:
    import asyncio

    coordinator, entry = _archive_entry(hass)

    async def _slow_archive(*_args):
        # Запрос к оператору уступает цикл: без этого два resolve не
        # переплетаются, и тест не отличает код с lock от кода без него.
        await asyncio.sleep(0)
        return _ARCHIVE_URL

    coordinator.api.query_camera_archive_stream = AsyncMock(
        side_effect=_slow_archive
    )
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created):
        first, second = await asyncio.gather(
            source.async_resolve_media(_resolve_item(hass, entry)),
            source.async_resolve_media(_resolve_item(hass, entry)),
        )

    coordinator.api.query_camera_archive_stream.assert_awaited_once()
    assert len(created) == 1
    assert first.url.split("?t=", 1)[0] == second.url.split("?t=", 1)[0]
    await created[0][0].stop()


async def test_resolve_after_idle_stop_requests_a_fresh_archive_link(
    hass, freezer
) -> None:
    """Остановленная сессия (idle/stop) не переиспользуется: ссылка новая."""
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created):
        await source.async_resolve_media(_resolve_item(hass, entry))
        await created[0][0].stop()
        await source.async_resolve_media(_resolve_item(hass, entry))

    assert coordinator.api.query_camera_archive_stream.await_count == 2
    assert len(created) == 2
    assert created[0][0].session_id != created[1][0].session_id
    await created[1][0].stop()


async def test_resolve_archive_unavailable_falls_back_to_live_view(
    hass, freezer
) -> None:
    coordinator, entry = _archive_entry(hass, url=None)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    created: list = []

    with _patch_archive_start(created=created), _patch_camera_resolve() as camera_resolve:
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    coordinator.api.query_camera_archive_stream.assert_awaited_once()
    camera_resolve.assert_awaited_once()
    assert play.url == _LIVE_PLAY_URL
    assert created == []


async def test_resolve_archive_start_failure_falls_back_to_live_view(
    hass, freezer, caplog
) -> None:
    import logging

    caplog.set_level(logging.DEBUG)
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)

    def _boom(_self, _url):
        raise RuntimeError("can't start new thread")

    with (
        _patch_archive_start(side_effect=_boom),
        _patch_camera_resolve() as camera_resolve,
    ):
        play = await source.async_resolve_media(_resolve_item(hass, entry))

    camera_resolve.assert_awaited_once()
    assert play.url == _LIVE_PLAY_URL
    assert not (hass.data.get("elektronny_gorod_archive_streams") or {})
    created: list = []
    with _patch_archive_start(created=created):
        await source.async_resolve_media(_resolve_item(hass, entry))
    assert coordinator.api.query_camera_archive_stream.await_count == 2
    assert "SIGNED-TOKEN" not in caplog.text
    await created[0][0].stop()


async def test_resolve_archive_worker_async_failure_falls_back_to_live_view(
    hass, caplog
) -> None:
    """Асинхронный отказ worker-а при открытии источника → эфир, без ожидания таймаута."""
    import logging

    caplog.set_level(logging.DEBUG)
    coordinator, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)
    created: list = []

    with (
        _patch_archive_start(fail_async=True, created=created),
        _patch_camera_resolve() as camera_resolve,
    ):
        play = await source.async_resolve_media(
            _resolve_item(hass, entry, day_str=day_str)
        )

    camera_resolve.assert_awaited_once()
    assert play.url == _LIVE_PLAY_URL
    assert len(created) == 1
    assert created[0][0].alive is False
    assert not (hass.data.get("elektronny_gorod_archive_streams") or {})
    assert "SIGNED-TOKEN" not in caplog.text

    # Повторное открытие после асинхронного отказа берёт свежую ссылку.
    with _patch_archive_start(created=created):
        recovered = await source.async_resolve_media(
            _resolve_item(hass, entry, day_str=day_str)
        )
    assert coordinator.api.query_camera_archive_stream.await_count == 2
    assert recovered.url.startswith("/api/elektronny_gorod/archive/")
    await created[1][0].stop()


async def test_resolve_archive_waits_for_first_segment_and_handles_failure(
    hass, monkeypatch
) -> None:
    """Готовность — первый сегмент EVENT HLS; отказ до него → откат на эфир."""
    import asyncio

    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        1.0,
    )
    _coord, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)

    def _delayed_segment(sess, _url):
        async def _produce() -> None:
            await asyncio.sleep(0.02)
            sess.add_segment(2.0, b"SEG0")

        hass.async_create_task(_produce())

    created: list = []
    with (
        _patch_archive_start(side_effect=_delayed_segment, created=created),
        _patch_camera_resolve() as camera_resolve,
    ):
        play = await source.async_resolve_media(
            _resolve_item(hass, entry, day_str=day_str)
        )

    camera_resolve.assert_not_awaited()
    assert play.url.startswith("/api/elektronny_gorod/archive/")
    assert created[0][0].segment_count == 1
    await created[0][0].stop()

    def _fail_before_segment(sess, _url):
        hass.loop.call_later(0.02, sess.mark_failed)

    with (
        _patch_archive_start(side_effect=_fail_before_segment, created=created),
        _patch_camera_resolve() as camera_resolve,
    ):
        fallback = await source.async_resolve_media(
            _resolve_item(hass, entry, day_str=day_str)
        )

    camera_resolve.assert_awaited_once()
    assert fallback.url == _LIVE_PLAY_URL
    assert not (hass.data.get("elektronny_gorod_archive_streams") or {})


async def test_resolve_archive_ready_timeout_falls_back_without_waiting_for_blocking_stop(
    hass, monkeypatch, caplog
) -> None:
    """Дедлайн ожидания не ждёт блокирующий `stop()` при зависшем upstream open."""
    import asyncio
    import logging
    import time

    from custom_components.elektronny_gorod.archive_hls import ArchiveHlsSession

    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        0.05,
    )
    _coordinator_unused, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)

    stop_started = asyncio.Event()
    stop_release = asyncio.Event()

    async def _slow_stop(self) -> None:
        self._closed = True
        self._cancel_idle_timer()
        self.fail_event.set()
        stop_started.set()
        await stop_release.wait()

    started_at = time.monotonic()
    try:
        with (
            patch.object(
                ArchiveHlsSession, "stop", autospec=True, side_effect=_slow_stop
            ),
            patch.object(ArchiveHlsSession, "start", lambda self, _url: self.touch()),
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            play = await source.async_resolve_media(
                _resolve_item(hass, entry, day_str=day_str)
            )
            elapsed = time.monotonic() - started_at

        assert elapsed < 0.5
        camera_resolve.assert_awaited_once()
        assert play.url == _LIVE_PLAY_URL
        assert stop_started.is_set()
        assert not (hass.data.get("elektronny_gorod_archive_streams") or {})
        assert "SIGNED-TOKEN" not in caplog.text
    finally:
        stop_release.set()
        await hass.async_block_till_done()


async def test_resolve_archive_cancellation_propagates_without_live_fallback(
    hass,
) -> None:
    """Отмена resolve пробрасывает `CancelledError` без эфира и без ожидания `stop()`."""
    import asyncio
    import time

    from custom_components.elektronny_gorod.archive_hls import ArchiveHlsSession

    _coordinator_unused, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)

    stop_started = asyncio.Event()
    stop_release = asyncio.Event()
    session_started = asyncio.Event()

    async def _slow_stop(self) -> None:
        self._closed = True
        self._cancel_idle_timer()
        self.fail_event.set()
        stop_started.set()
        await stop_release.wait()

    def _start_and_signal(self, _url: str) -> None:
        self.touch()
        session_started.set()

    try:
        with (
            patch.object(
                ArchiveHlsSession, "stop", autospec=True, side_effect=_slow_stop
            ),
            patch.object(ArchiveHlsSession, "start", _start_and_signal),
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            task = asyncio.create_task(
                source.async_resolve_media(
                    _resolve_item(hass, entry, day_str=day_str)
                )
            )
            await session_started.wait()
            await asyncio.sleep(0)
            t0 = time.monotonic()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            elapsed = time.monotonic() - t0

        assert elapsed < 0.5
        camera_resolve.assert_not_awaited()
        assert stop_started.is_set()
        assert not (hass.data.get("elektronny_gorod_archive_streams") or {})
    finally:
        stop_release.set()
        await hass.async_block_till_done()


async def test_stop_archive_streams_aborts_in_flight_wait_and_awaits_background_stop(
    hass,
) -> None:
    """Выгрузка прерывает ожидание готовности и дожидается фоновой остановки этого entry."""
    import asyncio

    from custom_components.elektronny_gorod.archive_hls import ArchiveHlsSession
    from custom_components.elektronny_gorod.media_source import (
        _ARCHIVE_IN_FLIGHT_KEY,
        async_stop_archive_streams,
    )

    _coordinator_unused, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)

    stop_started = asyncio.Event()
    stop_release = asyncio.Event()
    session_started = asyncio.Event()

    async def _slow_stop(self) -> None:
        self._closed = True
        self._cancel_idle_timer()
        self.fail_event.set()
        stop_started.set()
        await stop_release.wait()

    def _start_and_signal(self, _url: str) -> None:
        self.touch()
        session_started.set()

    try:
        with (
            patch.object(
                ArchiveHlsSession, "stop", autospec=True, side_effect=_slow_stop
            ),
            patch.object(ArchiveHlsSession, "start", _start_and_signal),
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            resolve = asyncio.create_task(
                source.async_resolve_media(
                    _resolve_item(hass, entry, day_str=day_str)
                )
            )
            await session_started.wait()
            while not (hass.data.get(_ARCHIVE_IN_FLIGHT_KEY) or {}).get(entry.entry_id):
                await asyncio.sleep(0)
            entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
            unload_stop = asyncio.create_task(
                async_stop_archive_streams(hass, entry.entry_id)
            )
            await stop_started.wait()
            assert not unload_stop.done()
            stop_release.set()
            await unload_stop
            with pytest.raises(Unresolvable):
                await resolve

        camera_resolve.assert_not_awaited()
        assert not (hass.data.get("elektronny_gorod_archive_streams") or {})
    finally:
        stop_release.set()
        await hass.async_block_till_done()


async def test_two_entries_use_independent_archive_locks_and_prune_only_own_streams(
    hass,
) -> None:
    """Per-entry lock и чистка только своих ключей: вторая запись не ждёт первую."""
    import asyncio

    from custom_components.elektronny_gorod.media_source import (
        _ARCHIVE_IN_FLIGHT_KEY,
        _ARCHIVE_STREAMS_KEY,
        async_stop_archive_streams,
    )

    _coord_a, entry_a, day_str = _realtime_archive_entry(hass)
    now_ts = int(dt_util.utcnow().timestamp())
    coord_b = _coordinator(
        events=(_event(event_id="3001", timestamp=now_ts - 10, duration=60),)
    )
    coord_b.api.query_camera_archive_stream = AsyncMock(return_value=_ARCHIVE_URL)
    entry_b = _entry(hass, coord_b, title="Second Account")
    source = _source(hass)

    created: list = []

    def _hang_a_ready_b(sess, _url):
        if sess.entry_id == entry_b.entry_id:
            sess.add_segment(2.0, b"SEG0")

    streams = hass.data.setdefault(_ARCHIVE_STREAMS_KEY, {})
    stale_b = MagicMock()
    stale_b.alive = False
    stale_b.session_id = "stale-b"
    streams[(entry_b.entry_id, _INTERCOM_ID, "stale")] = stale_b

    with (
        _patch_archive_start(side_effect=_hang_a_ready_b, created=created),
        _patch_camera_resolve() as camera_resolve,
    ):
        resolve_a = asyncio.create_task(
            source.async_resolve_media(
                _resolve_item(hass, entry_a, day_str=day_str)
            )
        )
        while not (hass.data.get(_ARCHIVE_IN_FLIGHT_KEY) or {}).get(entry_a.entry_id):
            await asyncio.sleep(0)

        # Пока entry_a ждёт под своим lock, stale-ключ entry_b ею не тронут.
        assert (entry_b.entry_id, _INTERCOM_ID, "stale") in streams

        # entry_b резолвится и выгружается без ожидания entry_a.
        play_b = await asyncio.wait_for(
            source.async_resolve_media(
                _resolve_item(hass, entry_b, day_str=day_str)
            ),
            timeout=1.0,
        )
        assert play_b.url.startswith("/api/elektronny_gorod/archive/")
        assert (entry_b.entry_id, _INTERCOM_ID, "stale") not in streams
        await asyncio.wait_for(
            async_stop_archive_streams(hass, entry_b.entry_id),
            timeout=1.0,
        )
        assert created[1][0].alive is False

        # Завершаем entry_a штатной выгрузкой.
        entry_a.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
        await async_stop_archive_streams(hass, entry_a.entry_id)
        with pytest.raises(Unresolvable):
            await resolve_a

    camera_resolve.assert_not_awaited()
    assert created[0][0].alive is False


async def test_unload_during_query_camera_events_skips_mint_and_live_fallback(
    hass,
) -> None:
    """Выгрузка во время `query_camera_events` отменяет resolve до минта и без эфира."""
    import asyncio

    coordinator, entry, day_str = _realtime_archive_entry(hass)
    requested = asyncio.Event()
    release = asyncio.Event()
    now_ts = int(dt_util.utcnow().timestamp())
    events = (_event(event_id="3001", timestamp=now_ts - 10, duration=60),)

    async def _slow_events(*_args, **_kwargs):
        requested.set()
        await release.wait()
        return events

    coordinator.api.query_camera_events = AsyncMock(side_effect=_slow_events)
    source = _source(hass)

    with _patch_camera_resolve() as camera_resolve:
        resolve = asyncio.create_task(
            source.async_resolve_media(_resolve_item(hass, entry, day_str=day_str))
        )
        await requested.wait()
        entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
        release.set()
        with pytest.raises(Unresolvable):
            await resolve

    coordinator.api.query_camera_archive_stream.assert_not_awaited()
    camera_resolve.assert_not_awaited()
    assert not (hass.data.get("elektronny_gorod_archive_streams") or {})


async def test_unload_during_archive_url_mint_skips_session_and_live_fallback(
    hass,
) -> None:
    """Выгрузка во время минта URL не создаёт сессию и не вызывает эфир."""
    import asyncio

    from custom_components.elektronny_gorod.media_source import (
        async_stop_archive_streams,
    )

    coordinator, entry, day_str = _realtime_archive_entry(hass)
    requested = asyncio.Event()
    release = asyncio.Event()

    async def _slow_mint(*_args, **_kwargs):
        requested.set()
        await release.wait()
        return _ARCHIVE_URL

    coordinator.api.query_camera_archive_stream = AsyncMock(side_effect=_slow_mint)
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created), _patch_camera_resolve() as camera_resolve:
        resolve = asyncio.create_task(
            source.async_resolve_media(_resolve_item(hass, entry, day_str=day_str))
        )
        await requested.wait()
        entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
        unload_stop = asyncio.create_task(
            async_stop_archive_streams(hass, entry.entry_id)
        )
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(Unresolvable):
            await resolve
        await unload_stop

    camera_resolve.assert_not_awaited()
    assert created == []


async def test_unload_right_after_archive_ready_stops_session_without_storing(
    hass,
) -> None:
    """Выгрузка сразу после готовности сегмента гасит сессию и не оставляет в кеше."""
    from custom_components.elektronny_gorod.media_source import _ARCHIVE_STREAMS_KEY

    _coord, entry, day_str = _realtime_archive_entry(hass)
    source = _source(hass)
    created: list = []

    def _unload_during_start(sess, _url):
        sess.add_segment(2.0, b"SEG0")
        entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)

    with (
        _patch_archive_start(side_effect=_unload_during_start, created=created),
        _patch_camera_resolve() as camera_resolve,
    ):
        with pytest.raises(Unresolvable):
            await source.async_resolve_media(
                _resolve_item(hass, entry, day_str=day_str)
            )

    camera_resolve.assert_not_awaited()
    assert len(created) == 1
    assert created[0][0].alive is False
    assert not (hass.data.get(_ARCHIVE_STREAMS_KEY) or {})


async def test_stop_archive_streams_stops_only_that_entry(hass, freezer) -> None:
    from custom_components.elektronny_gorod.media_source import (
        async_stop_archive_streams,
    )

    _coordinator_a, entry_a = _archive_entry(hass)
    coordinator_b = _coordinator(events=(_live_event(),))
    coordinator_b.api.query_camera_archive_stream = AsyncMock(
        return_value=_ARCHIVE_URL
    )
    entry_b = _entry(hass, coordinator_b, title="Second Account")
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created):
        await source.async_resolve_media(_resolve_item(hass, entry_a))
        await source.async_resolve_media(_resolve_item(hass, entry_b))
    sess_a, sess_b = created[0][0], created[1][0]

    await async_stop_archive_streams(hass, entry_a.entry_id)

    assert sess_a.alive is False
    assert sess_b.alive is True
    await sess_b.stop()


async def test_archive_stream_is_not_shared_between_events_of_one_camera(
    hass, freezer
) -> None:
    """Живая сессия одного события не отдаётся другому событию той же камеры."""
    first_event = _live_event(event_id="3001")
    second_event = _event(
        event_id="3002", timestamp=_EVENT_TS + 10, duration=_LIVE_EVENT_DURATION
    )
    coordinator = _coordinator(events=(second_event, first_event))
    coordinator.api.query_camera_archive_stream = AsyncMock(
        side_effect=[_ARCHIVE_URL, _ARCHIVE_URL.replace("SIGNED", "OTHER")]
    )
    entry = _entry(hass, coordinator)
    _register_camera_entity(hass, entry)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    source = _source(hass)
    created: list = []

    with _patch_archive_start(created=created):
        first = await source.async_resolve_media(
            _resolve_item(hass, entry, event_id="3001")
        )
        second = await source.async_resolve_media(
            _resolve_item(hass, entry, event_id="3002")
        )

    assert [call.args[1] for call in (
        coordinator.api.query_camera_archive_stream.await_args_list
    )] == [_EVENT_TS, _EVENT_TS + 10]
    assert len(created) == 2
    assert first.url.split("?t=", 1)[0] != second.url.split("?t=", 1)[0]
    for sess, _ in created:
        await sess.stop()


async def test_stop_archive_streams_waits_for_resolve_holding_the_lock(
    hass, freezer
) -> None:
    """Выгрузка при задержанном mint прерывает ожидание без блокировки 30с и без сессии/эфира."""
    import asyncio
    import time

    from custom_components.elektronny_gorod.media_source import (
        _ARCHIVE_STREAMS_KEY,
        async_stop_archive_streams,
    )

    coordinator, entry = _archive_entry(hass)
    requested = asyncio.Event()
    release = asyncio.Event()

    async def _hung_mint(*_args):
        requested.set()
        await release.wait()
        return _ARCHIVE_URL

    coordinator.api.query_camera_archive_stream = AsyncMock(side_effect=_hung_mint)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    created: list = []

    try:
        with (
            _patch_archive_start(created=created),
            _patch_camera_resolve() as camera_resolve,
        ):
            resolve = asyncio.ensure_future(
                _source(hass).async_resolve_media(_resolve_item(hass, entry))
            )
            await requested.wait()
            entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
            t0 = time.monotonic()
            await asyncio.wait_for(
                async_stop_archive_streams(hass, entry.entry_id), timeout=1.0
            )
            assert time.monotonic() - t0 < 0.5
            with pytest.raises(Unresolvable):
                await resolve

        camera_resolve.assert_not_awaited()
        assert created == []
        streams = hass.data.get(_ARCHIVE_STREAMS_KEY) or {}
        assert not [key for key in streams if key[0] == entry.entry_id]
    finally:
        release.set()


async def test_delayed_mint_respects_readiness_budget_and_falls_back(
    hass, monkeypatch
) -> None:
    """Задержанный mint (30с REST) укладывается в общий бюджет readiness и отдаёт эфир."""
    import asyncio
    import time

    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        0.05,
    )
    coordinator, entry, day_str = _realtime_archive_entry(hass)
    release = asyncio.Event()

    async def _slow_mint(*_args):
        await release.wait()
        return _ARCHIVE_URL

    coordinator.api.query_camera_archive_stream = AsyncMock(side_effect=_slow_mint)
    created: list = []
    try:
        with (
            _patch_archive_start(created=created),
            _patch_camera_resolve() as camera_resolve,
        ):
            t0 = time.monotonic()
            play = await _source(hass).async_resolve_media(
                _resolve_item(hass, entry, day_str=day_str)
            )
            assert time.monotonic() - t0 < 0.5

        camera_resolve.assert_awaited_once()
        assert play.url == _LIVE_PLAY_URL
        assert created == []
    finally:
        release.set()


async def test_missing_pyav_requirement_failure_falls_back_to_live_view(
    hass, freezer
) -> None:
    """Если HA не может обеспечить PyAV (`stream` requirements), безопасный fallback на эфир."""
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))

    with (
        patch(
            "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
            AsyncMock(return_value=False),
        ),
        _patch_camera_resolve() as camera_resolve,
    ):
        play = await _source(hass).async_resolve_media(_resolve_item(hass, entry))

    assert play.url == _LIVE_PLAY_URL
    camera_resolve.assert_awaited_once()
    coordinator.api.query_camera_archive_stream.assert_not_awaited()
    assert "stream" not in hass.config.components


async def test_pyav_ensure_abort_and_budget_exhaustion(hass, monkeypatch) -> None:
    """Выгрузка при проверке PyAV даёт Unresolvable; исчерпанный бюджет уходит в эфир."""
    import asyncio

    from custom_components.elektronny_gorod.media_source import (
        async_stop_archive_streams,
    )

    # 1) Unload while awaiting PyAV requirements -> Unresolvable without mint/live.
    coordinator, entry, day_str = _realtime_archive_entry(hass)
    pyav_started = asyncio.Event()
    pyav_release = asyncio.Event()

    async def _slow_pyav(_hass):
        pyav_started.set()
        await pyav_release.wait()
        return True

    try:
        with (
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                side_effect=_slow_pyav,
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            resolve = asyncio.create_task(
                _source(hass).async_resolve_media(
                    _resolve_item(hass, entry, day_str=day_str)
                )
            )
            await pyav_started.wait()
            entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
            await async_stop_archive_streams(hass, entry.entry_id)
            with pytest.raises(Unresolvable):
                await resolve
        camera_resolve.assert_not_awaited()
        coordinator.api.query_camera_archive_stream.assert_not_awaited()
    finally:
        pyav_release.set()

    # 2) PyAV consumes full readiness budget -> falls back without minting.
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        0.02,
    )
    coordinator2, entry2, day_str2 = _realtime_archive_entry(hass)

    async def _budget_eating_pyav(_hass):
        await asyncio.sleep(0.03)
        return True

    with (
        patch(
            "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
            side_effect=_budget_eating_pyav,
        ),
        _patch_camera_resolve() as camera_resolve2,
    ):
        play = await _source(hass).async_resolve_media(
            _resolve_item(hass, entry2, day_str=day_str2)
        )
    assert play.url == _LIVE_PLAY_URL
    camera_resolve2.assert_awaited_once()
    coordinator2.api.query_camera_archive_stream.assert_not_awaited()


async def test_parallel_stalled_resolves_share_single_budget_without_queue_stacking(
    hass, monkeypatch
) -> None:
    """Два параллельных stalled resolve на одной записи укладываются в один бюджет.

    Ожидание per-entry lock учитывается в общем deadline; второй запрос не
    вызывает минт после истечения бюджета и не держит lock при откате на эфир.
    """
    import asyncio
    import time

    from custom_components.elektronny_gorod.media_source import _archive_lock

    budget_sec = 0.08
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        budget_sec,
    )
    coordinator, entry, day_str = _realtime_archive_entry(hass)
    _register_camera_entity(hass, entry, camera_id=_PUBLIC_ID)

    release = asyncio.Event()
    minted_cameras: list[str] = []

    async def _stalled_mint(camera_id: str, *_args):
        minted_cameras.append(camera_id)
        await release.wait()
        return _ARCHIVE_URL

    coordinator.api.query_camera_archive_stream = AsyncMock(side_effect=_stalled_mint)
    source = _source(hass)

    try:
        with (
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            t0 = time.monotonic()
            play_1, play_2 = await asyncio.gather(
                source.async_resolve_media(
                    _resolve_item(
                        hass, entry, camera_id=_INTERCOM_ID, day_str=day_str
                    )
                ),
                source.async_resolve_media(
                    _resolve_item(
                        hass, entry, camera_id=_PUBLIC_ID, day_str=day_str
                    )
                ),
            )
            elapsed = time.monotonic() - t0

        assert play_1.url == _LIVE_PLAY_URL
        assert play_2.url == _LIVE_PLAY_URL
        # Bounded to ONE budget window (no linear 2x stacking).
        assert elapsed < budget_sec * 1.9
        # Only the first caller minted; the second never started mint after timeout.
        assert len(minted_cameras) == 1
        assert camera_resolve.await_count == 2
        assert _archive_lock(hass, entry.entry_id).locked() is False
    finally:
        release.set()


async def test_unload_during_archive_lock_wait_raises_unresolvable_without_live(
    hass, monkeypatch
) -> None:
    """Выгрузка во время ожидания lock даёт `Unresolvable` без отката на эфир."""
    import asyncio
    import time

    from custom_components.elektronny_gorod.media_source import _archive_lock

    monkeypatch.setattr(
        "custom_components.elektronny_gorod.media_source._ARCHIVE_READY_TIMEOUT_SEC",
        0.04,
    )
    coordinator, entry, day_str = _realtime_archive_entry(hass)
    lock = _archive_lock(hass, entry.entry_id)
    await lock.acquire()
    try:
        with (
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            resolve = asyncio.create_task(
                _source(hass).async_resolve_media(
                    _resolve_item(hass, entry, day_str=day_str)
                )
            )
            await asyncio.sleep(0)
            # Mark entry unloaded while the resolve is still queued on the lock.
            entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS)
            t0 = time.monotonic()
            with pytest.raises(Unresolvable, match="Unknown media item"):
                await resolve
            assert time.monotonic() - t0 < 0.25

        coordinator.api.query_camera_archive_stream.assert_not_awaited()
        camera_resolve.assert_not_awaited()
    finally:
        lock.release()


async def test_acquire_archive_lock_budgeted_edge_cases(hass) -> None:
    """Граничные ветки `_acquire_archive_lock_budgeted` и release на racing acquire."""
    import asyncio
    import time

    source = _source(hass)

    # Pre-set cancel_event returns 'aborted' immediately without touching lock.
    lock = asyncio.Lock()
    preset = asyncio.Event()
    preset.set()
    assert (
        await source._acquire_archive_lock_budgeted(
            lock, preset, time.monotonic() + 5.0
        )
        == "aborted"
    )
    assert lock.locked() is False

    # Already expired deadline returns 'timeout' immediately without touching lock.
    assert (
        await source._acquire_archive_lock_budgeted(
            lock, asyncio.Event(), time.monotonic() - 1.0
        )
        == "timeout"
    )
    assert lock.locked() is False

    # If abort triggers concurrently right as lock is acquired, lock is released cleanly.
    await lock.acquire()
    cancel_ev = asyncio.Event()
    task = asyncio.create_task(
        source._acquire_archive_lock_budgeted(
            lock, cancel_ev, time.monotonic() + 5.0
        )
    )
    await asyncio.sleep(0)
    cancel_ev.set()
    lock.release()
    assert await task == "aborted"
    assert lock.locked() is False


async def test_hass_stop_during_stalled_session_raises_unresolvable_without_live(
    hass,
) -> None:
    """Реальный `hass.async_stop()` без выгрузки entry режет live fallback."""
    import asyncio

    from aiohttp import web

    from custom_components.elektronny_gorod.archive_hls import (
        ARCHIVE_STREAMS_KEY,
        _ARCHIVE_BY_ID_KEY,
    )

    coordinator, entry, day_str = _realtime_archive_entry(hass)
    upstream_started = asyncio.Event()
    upstream_release = asyncio.Event()

    async def _stalled_get(*_args, **_kwargs):
        upstream_started.set()
        await upstream_release.wait()
        raise web.HTTPBadGateway

    http_session = MagicMock()
    http_session.get = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(side_effect=_stalled_get),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    source = _source(hass)
    try:
        with (
            patch(
                "custom_components.elektronny_gorod.media_source.async_ensure_archive_pyav",
                AsyncMock(return_value=True),
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
                return_value=http_session,
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls._import_av",
                side_effect=lambda: SimpleNamespace(
                    open=lambda pipe, **_kw: pipe.read(16)
                ),
            ),
            _patch_camera_resolve() as camera_resolve,
        ):
            resolve = asyncio.create_task(
                source.async_resolve_media(
                    _resolve_item(hass, entry, day_str=day_str)
                )
            )
            await upstream_started.wait()
            # Keep config entry LOADED: simulate real HA core stop directly.
            assert entry.state is ConfigEntryState.LOADED
            await hass.async_stop()
            with pytest.raises(Unresolvable, match="Unknown media item"):
                await resolve

        camera_resolve.assert_not_awaited()
        assert not (hass.data.get(ARCHIVE_STREAMS_KEY) or {})
        assert not (hass.data.get(_ARCHIVE_BY_ID_KEY) or {})
    finally:
        upstream_release.set()


async def test_media_source_budget_helpers_stopping_and_by_id_cleanup(
    hass, freezer
) -> None:
    """Граничные ветки `_await_budgeted`, `is_stopping`, неготовой сессии и `by_id` stop."""
    import asyncio
    import time

    from custom_components.elektronny_gorod.archive_hls import (
        ArchiveHlsSession,
        archive_sessions_by_id,
    )
    from custom_components.elektronny_gorod.media_source import (
        _ARCHIVE_STREAMS_KEY,
        async_stop_archive_streams,
    )

    source = _source(hass)

    # 1) `_await_budgeted` with pre-set cancel_event or expired deadline closes coro cleanly.
    preset = asyncio.Event()
    preset.set()

    async def _never():
        return 1

    assert await source._await_budgeted(_never(), preset, time.monotonic() + 5.0) == (
        "aborted",
        None,
    )
    assert await source._await_budgeted(
        _never(), asyncio.Event(), time.monotonic() - 1.0
    ) == ("timeout", None)

    # 2) Unready alive session in `streams` is detached/stopped before fresh mint.
    coordinator, entry = _archive_entry(hass)
    freezer.move_to(dt_util.utc_from_timestamp(_LIVE_EVENT_END - 5))
    unready = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_INTERCOM_ID,
        event_id="3001",
        coordinator=coordinator,
    )
    hass.data.setdefault(_ARCHIVE_STREAMS_KEY, {})[unready.key] = unready

    created: list = []
    with _patch_archive_start(created=created):
        play = await source.async_resolve_media(_resolve_item(hass, entry))
    assert play.url.startswith("/api/elektronny_gorod/archive/")
    assert unready.alive is False
    await created[0][0].stop()

    # 3) `async_stop_archive_streams` also stops sessions present only in `by_id`.
    orphan = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_INTERCOM_ID,
        event_id="orphan",
        coordinator=coordinator,
    )
    archive_sessions_by_id(hass)[orphan.session_id] = orphan
    await async_stop_archive_streams(hass, entry.entry_id)
    assert orphan.alive is False

    # 4) Stopping HA rejects new archive resolve without live fallback.
    with (
        patch.object(
            type(hass), "is_stopping", new_callable=lambda: property(lambda _s: True)
        ),
        _patch_camera_resolve() as camera_resolve,
        pytest.raises(Unresolvable, match="Unknown media item"),
    ):
        await source.async_resolve_media(_resolve_item(hass, entry))
    camera_resolve.assert_not_awaited()
