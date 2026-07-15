"""HAR-backed API contract tests for durable event history."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.user_agent import UserAgent


_FIXTURES = Path(__file__).parent / "fixtures" / "mobile_app_9_9_0"


async def test_query_events_posts_exact_contract_and_returns_typed_page(hass) -> None:
    """9.9.0 sends place IDs in JSON and uses numeric page + DESC sort."""
    payload = json.loads((_FIXTURES / "events_search_page_0.json").read_text())
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value=payload)

    api = ElektronnyGorodAPI(hass, UserAgent())
    api.http.post = AsyncMock(return_value=response)

    page = await api.query_events([1001], page=0)

    api.http.post.assert_awaited_once_with(
        "/rest/v1/events/search?page=0&sort=occurredAt%2CDESC",
        json.dumps({"placeIds": [1001]}),
    )
    assert page.number == 0
    assert page.last is False
    assert [event.id for event in page.events] == [
        "event-accepted-001",
        "event-missed-002",
    ]
    assert page.events[0].event_type == "accessControlCallAccepted"
    assert page.events[0].source_type == "accessControl"
    assert page.events[0].source_id == "2001"
    assert page.events[0].timestamp == 1700000001
    assert not hasattr(page.events[0], "message")


async def test_query_events_does_not_immediately_retry_502(hass) -> None:
    """The caller owns recovery after a failed history request."""
    failed_response = MagicMock(spec=ClientResponse)
    failed_response.status = 502

    api = ElektronnyGorodAPI(hass, UserAgent())
    api.http.post = AsyncMock(side_effect=ClientError(failed_response))

    with pytest.raises(ClientError):
        await api.query_events([1001], page=0)

    api.http.post.assert_awaited_once()


async def test_query_camera_events_uses_requested_camera_identity(hass) -> None:
    """The response CameraID is internal; routing keeps the ID from the URL."""
    payload = json.loads((_FIXTURES / "camera_motion_event.json").read_text())
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value=payload)

    api = ElektronnyGorodAPI(hass, UserAgent())
    api.http.get = AsyncMock(return_value=response)

    events = await api.query_camera_events(
        "camera-public-1",
        lower_date="2026-07-15T00:00:00Z",
        upper_date="2026-07-15T01:00:00Z",
    )

    api.http.get.assert_awaited_once_with(
        "/rest/v2/forpost/cameras/camera-public-1/events"
        "?UpperDate=2026-07-15T01%3A00%3A00Z"
        "&LowerDate=2026-07-15T00%3A00%3A00Z"
        "&Count=100&orderByTime=DESC"
    )
    assert len(events) == 1
    assert events[0].id == "3001"
    assert events[0].camera_id == "camera-public-1"
    assert events[0].backend_camera_id == "4001"
    assert events[0].event_subject_id == 126
    assert events[0].available is True
    assert events[0].goto_enabled is True
    assert not hasattr(events[0], "message")
