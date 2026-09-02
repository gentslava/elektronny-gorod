"""Contract tests for the forpost event-download API wrapper."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponse
from aioresponses import aioresponses

from custom_components.elektronny_gorod.api import (
    ForpostDownloadError,
    ElektronnyGorodAPI,
)
from custom_components.elektronny_gorod.const import BASE_API_URL
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


async def test_query_event_download_non_json_error_body_propagates(hass) -> None:
    """A 502-style non-JSON body is transient, not a business 'no recording'."""
    api = _api(hass)
    failed = MagicMock(spec=ClientResponse)
    failed.json = AsyncMock(side_effect=ValueError("<html>Bad Gateway</html>"))
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    with pytest.raises(ClientError) as excinfo:
        await api.query_event_download("3001")

    assert excinfo.value.args[0] is failed


async def test_query_event_download_timeout_propagates_as_client_error(
    hass,
) -> None:
    """A transport timeout (no ClientResponse in args) is not 'no recording'."""
    from aiohttp import ServerTimeoutError

    api = _api(hass)
    api.http.get = AsyncMock(side_effect=ClientError(ServerTimeoutError("t")))

    with pytest.raises(ClientError) as excinfo:
        await api.query_event_download("3001")

    assert not isinstance(excinfo.value, ForpostDownloadError)


def test_forpost_download_error_sanitizes_message() -> None:
    """The backend-controlled code enters the message only if charset-safe."""
    clean = ForpostDownloadError("11005")
    assert str(clean) == "forpost_download_failed_11005"
    assert clean.error_code == "11005"

    dirty = ForpostDownloadError("code with spaces\nand newline")
    assert str(dirty) == "forpost_download_failed_unknown"
    assert dirty.error_code == "code with spaces\nand newline"

    assert str(ForpostDownloadError(None)) == "forpost_download_failed_unknown"
    assert str(ForpostDownloadError("a1-b.c")) == "forpost_download_failed_a1-b.c"


async def test_query_event_download_real_http_never_logs_signed_url(
    hass, caplog
) -> None:
    """End-to-end through the real HTTP layer: the signed URL never hits logs."""
    api = _api(hass)
    caplog.set_level(logging.DEBUG)

    with aioresponses() as m:
        m.get(
            f"https://{BASE_API_URL}"
            "/rest/v1/forpost/events/3001/downloads?container=mp4",
            payload={"data": "https://savevideo.example/signed-clip.mp4"},
        )
        url = await api.query_event_download("3001")

    assert url == "https://savevideo.example/signed-clip.mp4"
    assert "savevideo.example" not in caplog.text


async def test_query_event_download_parses_prepare_pending_shape(hass) -> None:
    """423 preparation carries PascalCase ErrorCode as an int (runtime 2026-08-30)."""
    api = _api(hass)
    failed = _response(
        {"Error": "Файл не готов для загрузки", "ErrorCode": 102, "status": 423}
    )
    api.http.get = AsyncMock(side_effect=ClientError(failed))

    try:
        await api.query_event_download("3001")
    except ForpostDownloadError as ex:
        assert ex.error_code == "102"
    else:
        raise AssertionError("ForpostDownloadError not raised")
