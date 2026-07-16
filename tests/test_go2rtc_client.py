"""Direct contract tests for the operator-camera go2rtc transport."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp import ClientConnectionError, ClientTimeout

from custom_components.elektronny_gorod.go2rtc import (
    Go2RtcClient,
    Go2RtcRequestError,
)


class _AsyncCtxMgr:
    def __init__(self, response: Any) -> None:
        self._response = response

    async def __aenter__(self) -> Any:
        return self._response

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _response(
    status: int,
    *,
    payload: Any = None,
    json_error: Exception | None = None,
) -> AsyncMock:
    response = AsyncMock()
    response.status = status
    if json_error is not None:
        response.json = AsyncMock(side_effect=json_error)
    else:
        response.json = AsyncMock(return_value=payload)
    response.text = AsyncMock(return_value="response-body-must-not-leak")
    return response


def _verb(response: AsyncMock | Exception) -> MagicMock:
    if isinstance(response, Exception):
        return MagicMock(side_effect=response)
    return MagicMock(return_value=_AsyncCtxMgr(response))


def _session(
    *,
    patch: AsyncMock | Exception | None = None,
    get: AsyncMock | Exception | None = None,
    put: AsyncMock | Exception | None = None,
    delete: AsyncMock | Exception | None = None,
) -> MagicMock:
    session = MagicMock()
    session.patch = _verb(patch or _response(200))
    session.get = _verb(get or _response(200, payload={}))
    session.put = _verb(put or _response(204))
    session.delete = _verb(delete or _response(204))
    return session


def _client(session: MagicMock, **overrides: str | None):
    values = {
        "base_url": "http://go2rtc:1984/",
        "rtsp_host": "go2rtc.local",
        "session": session,
        "username": None,
        "password": None,
    }
    values.update(overrides)
    return Go2RtcClient(**values)


def test_matches_configuration_normalizes_url_and_empty_credentials() -> None:
    client = _client(_session())

    assert client.matches_configuration(
        base_url="http://go2rtc:1984/",
        rtsp_host="go2rtc.local",
        username="",
        password="",
    ) is True
    assert client.matches_configuration(
        base_url="http://other-go2rtc:1984",
        rtsp_host="go2rtc.local",
        username=None,
        password=None,
    ) is False


def test_matches_configuration_detects_auth_change() -> None:
    client = _client(_session(), username="admin", password="old-password")

    assert client.matches_configuration(
        base_url="http://go2rtc:1984",
        rtsp_host="go2rtc.local",
        username="admin",
        password="new-password",
    ) is False


@pytest.mark.parametrize("status", [200, 201, 204])
async def test_patch_stream_uses_patch_without_put_fallback(status: int) -> None:
    session = _session(patch=_response(status))
    client = _client(session)

    await client.async_patch_stream(
        "eg_42", "ffmpeg:https://operator/stream?token=SECRET#video=copy"
    )

    session.patch.assert_called_once()
    session.put.assert_not_called()
    url = session.patch.call_args.args[0]
    parsed = urlsplit(url)
    assert parsed.path == "/api/streams"
    assert parse_qs(parsed.query) == {
        "name": ["eg_42"],
        "src": ["ffmpeg:https://operator/stream?token=SECRET#video=copy"],
    }
    timeout = session.patch.call_args.kwargs["timeout"]
    assert isinstance(timeout, ClientTimeout)
    assert timeout.total == 10


async def test_patch_stream_accepts_missing_stream_creation() -> None:
    """A missing in-memory stream is created by the same successful PATCH."""
    session = _session(patch=_response(200))
    client = _client(session)

    await client.async_patch_stream("eg_missing", "ffmpeg:https://operator/new")

    session.patch.assert_called_once()
    session.get.assert_not_called()
    session.put.assert_not_called()


async def test_patch_failure_is_sanitized_and_never_uses_put() -> None:
    secret_source = "ffmpeg:https://operator/stream?token=OPERATOR_SECRET"
    session = _session(patch=_response(500))
    client = _client(session, username="admin", password="GO2RTC_SECRET")

    with pytest.raises(Go2RtcRequestError) as caught:
        await client.async_patch_stream("eg_42", secret_source)

    rendered = f"{caught.value!s} {caught.value!r}"
    assert "OPERATOR_SECRET" not in rendered
    assert "GO2RTC_SECRET" not in rendered
    assert "response-body-must-not-leak" not in rendered
    assert "http_500" in rendered
    assert caught.value.__cause__ is None
    session.put.assert_not_called()


async def test_client_error_does_not_expose_requested_url_or_auth() -> None:
    secret = "OPERATOR_SECRET"
    session = _session(
        patch=ClientConnectionError(
            f"https://operator/stream?token={secret} Authorization=Basic SECRET"
        )
    )
    client = _client(session, username="admin", password="GO2RTC_SECRET")

    with pytest.raises(Go2RtcRequestError) as caught:
        await client.async_patch_stream(
            "eg_42", f"ffmpeg:https://operator/stream?token={secret}"
        )

    rendered = f"{caught.value!s} {caught.value!r}"
    for forbidden in (secret, "SECRET", "GO2RTC_SECRET", "Authorization"):
        assert forbidden not in rendered
    assert "client_error" in rendered
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


async def test_list_streams_parses_complete_mapping() -> None:
    session = _session(
        get=_response(
            200,
            payload={
                "eg_1": {
                    "producers": [{"bytes_recv": 123}],
                    "consumers": [{"format_name": "rtsp"}, {}],
                },
                "eg_2": {"producers": None, "consumers": None},
                "broken": "not-a-stream-object",
            },
        )
    )
    client = _client(session)

    streams = await client.async_list_streams()

    assert set(streams) == {"eg_1", "eg_2"}
    assert streams["eg_1"].producers == ({"bytes_recv": 123},)
    assert streams["eg_1"].consumer_count == 2
    assert streams["eg_1"].producer_active is True
    assert streams["eg_2"].producers == ()
    assert streams["eg_2"].consumer_count == 0
    assert streams["eg_2"].producer_active is False
    url = session.get.call_args.args[0]
    assert url == "http://go2rtc:1984/api/streams"


async def test_get_stream_parses_single_stream_metadata() -> None:
    session = _session(
        get=_response(
            200,
            payload={
                "producers": [{"bytes_recv": 456}],
                "consumers": [{}],
            },
        )
    )
    client = _client(session)

    stream = await client.async_get_stream("eg_42")

    assert stream is not None
    assert stream.producers == ({"bytes_recv": 456},)
    assert stream.consumer_count == 1
    assert stream.producer_active is True
    url = session.get.call_args.args[0]
    assert parse_qs(urlsplit(url).query) == {"src": ["eg_42"]}


async def test_get_stream_returns_none_for_empty_object() -> None:
    session = _session(get=_response(200, payload={}))
    client = _client(session)

    assert await client.async_get_stream("eg_missing") is None


async def test_stream_info_strips_lazy_producer_source_and_reports_health() -> None:
    session = _session(
        get=_response(
            200,
            payload={
                "eg_lazy": {
                    "producers": [{
                        "url": "ffmpeg:https://operator/live?token=OPERATOR_SECRET"
                    }],
                    "consumers": [],
                },
                "eg_active": {
                    "producers": [{
                        "url": "ffmpeg:https://operator/live?token=OPERATOR_SECRET",
                        "bytes_recv": 0,
                        "medias": ["video, recvonly, H264"],
                    }],
                    "consumers": [{}],
                },
            },
        )
    )
    client = _client(session)

    streams = await client.async_list_streams()

    assert streams["eg_lazy"].producers == ({},)
    assert streams["eg_lazy"].producer_active is False
    assert streams["eg_active"].producers == ({"bytes_recv": 0},)
    assert streams["eg_active"].producer_active is True
    assert "OPERATOR_SECRET" not in repr(streams)


async def test_list_invalid_json_raises_sanitized_error() -> None:
    session = _session(
        get=_response(200, json_error=ValueError("body contains OPERATOR_SECRET"))
    )
    client = _client(session)

    with pytest.raises(Go2RtcRequestError) as caught:
        await client.async_list_streams()

    assert "invalid_response" in str(caught.value)
    assert "OPERATOR_SECRET" not in repr(caught.value)


async def test_delete_stream_uses_src_name() -> None:
    session = _session(delete=_response(204))
    client = _client(session)

    await client.async_delete_stream("eg_42")

    url = session.delete.call_args.args[0]
    assert parse_qs(urlsplit(url).query) == {"src": ["eg_42"]}


async def test_list_preloads_returns_only_string_names() -> None:
    session = _session(
        get=_response(
            200,
            payload={"eg_1": {"src": "eg_1"}, 42: {}, "eg_2": None},
        )
    )
    client = _client(session)

    preloads = await client.async_list_preloads()

    assert preloads == {"eg_1", "eg_2"}
    assert session.get.call_args.args[0] == "http://go2rtc:1984/api/preload"


async def test_list_preloads_rejects_non_mapping_response() -> None:
    session = _session(get=_response(200, payload=[]))
    client = _client(session)

    with pytest.raises(Go2RtcRequestError) as caught:
        await client.async_list_preloads()

    assert caught.value.operation == "preload_list"
    assert caught.value.category == "invalid_response"


@pytest.mark.parametrize("status", [200, 201, 204])
async def test_enable_preload_uses_put_with_stream_name(status: int) -> None:
    session = _session(put=_response(status))
    client = _client(session)

    await client.async_enable_preload("eg_42")

    url = session.put.call_args.args[0]
    assert urlsplit(url).path == "/api/preload"
    assert parse_qs(urlsplit(url).query) == {"src": ["eg_42"]}
    assert session.put.call_args.kwargs["timeout"].total == 10


@pytest.mark.parametrize("status", [200, 201, 204, 404])
async def test_disable_preload_is_idempotent(status: int) -> None:
    session = _session(delete=_response(status))
    client = _client(session)

    await client.async_disable_preload("eg_42")

    url = session.delete.call_args.args[0]
    assert urlsplit(url).path == "/api/preload"
    assert parse_qs(urlsplit(url).query) == {"src": ["eg_42"]}


@pytest.mark.parametrize(
    ("operation", "method", "failure", "expected_category"),
    [
        ("preload_enable", "async_enable_preload", _response(500), "http_500"),
        (
            "preload_disable",
            "async_disable_preload",
            ClientConnectionError("Authorization=Basic GO2RTC_SECRET"),
            "client_error",
        ),
        (
            "preload_enable",
            "async_enable_preload",
            asyncio.TimeoutError("GO2RTC_SECRET"),
            "timeout",
        ),
    ],
)
async def test_preload_failures_are_sanitized(
    operation: str,
    method: str,
    failure: AsyncMock | Exception,
    expected_category: str,
) -> None:
    session = (
        _session(delete=failure)
        if method == "async_disable_preload"
        else _session(put=failure)
    )
    client = _client(session, username="admin", password="GO2RTC_SECRET")

    with pytest.raises(Go2RtcRequestError) as caught:
        await getattr(client, method)("eg_42")

    rendered = f"{caught.value!s} {caught.value!r}"
    assert caught.value.operation == operation
    assert caught.value.category == expected_category
    assert "GO2RTC_SECRET" not in rendered
    assert "Authorization" not in rendered
    assert "response-body-must-not-leak" not in rendered
    assert caught.value.__cause__ is None


def test_rtsp_url_can_omit_credentials_for_diagnostics() -> None:
    session = _session()
    client = _client(
        session,
        username="user@example.com",
        password="p@ss/word",
    )

    assert client.rtsp_url("eg_42", include_credentials=False) == (
        "rtsp://go2rtc.local:8554/eg_42"
    )
    assert client.rtsp_url("eg_42", include_credentials=True) == (
        "rtsp://user%40example.com:p%40ss%2Fword@go2rtc.local:8554/eg_42"
    )


async def test_requests_include_basic_auth_without_exposing_it() -> None:
    session = _session()
    client = _client(session, username="user", password="pass")

    await client.async_patch_stream("eg_42", "ffmpeg:https://operator/source")

    headers = session.patch.call_args.kwargs["headers"]
    assert headers == {"Authorization": "Basic dXNlcjpwYXNz"}
