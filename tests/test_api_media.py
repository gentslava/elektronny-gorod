"""Contract tests for the forpost event-download API wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import (
    ForpostDownloadError,
    ElektronnyGorodAPI,
)
from custom_components.elektronny_gorod.user_agent import UserAgent


def _api(hass) -> ElektronnyGorodAPI:
    return ElektronnyGorodAPI(hass, UserAgent())


def _response(payload) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value=payload)
    return response


async def test_query_event_download_returns_signed_url(hass) -> None:
    """The endpoint returns `data` as a plain URL string, not an object."""
    api = _api(hass)
    api.http.get = AsyncMock(
        return_value=_response({"data": "https://myhome-savevideo.example/abc.mp4"})
    )

    url = await api.query_event_download("3001")

    api.http.get.assert_awaited_once_with(
        "/rest/v1/forpost/events/3001/downloads?container=mp4"
    )
    assert url == "https://myhome-savevideo.example/abc.mp4"


async def test_query_event_download_missing_data_is_no_recording(hass) -> None:
    """HTTP 200 with empty data degrades to a typed no-recording error."""
    api = _api(hass)
    api.http.get = AsyncMock(return_value=_response({"data": None}))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code is None
    else:
        raise AssertionError("ForpostDownloadError not raised")


async def test_query_event_download_parses_forpost_error_code(hass) -> None:
    """HTTP 500 business errors carry errorCode in the JSON body."""
    api = _api(hass)
    failed = _response({"errorCode": "11005", "errorMessage": "Архив доступен с 01.01"})
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code == "11005"
    else:
        raise AssertionError("ForpostDownloadError not raised")


async def test_query_event_download_non_json_error_body(hass) -> None:
    """A non-JSON error body still yields a typed error with no code."""
    api = _api(hass)
    failed = MagicMock(spec=ClientResponse)
    failed.json = AsyncMock(side_effect=ValueError("not json"))
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code is None
    else:
        raise AssertionError("ForpostDownloadError not raised")
