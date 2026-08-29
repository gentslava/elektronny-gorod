"""Tests for the forpost camera archive Media Source."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import MediaSourceItem
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.api import CameraHistoryEvent
from custom_components.elektronny_gorod.const import DOMAIN

_PLACE_ID = "1001"
_INTERCOM_ID = "111"
_PUBLIC_ID = "222"


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
