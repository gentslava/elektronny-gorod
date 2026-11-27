"""HAR-backed API contract tests for camera stream URLs."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.const import BASE_API_URL
from custom_components.elektronny_gorod.user_agent import UserAgent


async def test_live_stream_requests_explicit_h264_format(hass) -> None:
    """MyHome 9.9.0 live view sends LightStream=0 and Format=H264."""
    api = ElektronnyGorodAPI(hass, UserAgent())
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value={"data": {"URL": "https://stream.invalid/live"}})
    api.http.get = AsyncMock(return_value=response)

    assert await api.query_camera_stream("CAMERA") == "https://stream.invalid/live"
    api.http.get.assert_awaited_once_with(
        "/rest/v1/forpost/cameras/CAMERA/video?LightStream=0&Format=H264"
    )


# --- A-124 шаг 2: поток архива с начала события -----------------------------

_ARCHIVE_URL = "https://forpost.invalid:18081/rtsp/STREAM/SIGNED-TOKEN/d=1"


def _archive_api(hass, *, payload=None, side_effect=None) -> ElektronnyGorodAPI:
    api = ElektronnyGorodAPI(hass, UserAgent())
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(return_value=payload)
    api.http.get = AsyncMock(return_value=response, side_effect=side_effect)
    return api


async def test_archive_stream_mirrors_app_query_order(hass) -> None:
    """HAR 9.11.0: TS, TZ, LightStream, Format, Speed — именно в этом порядке."""
    api = _archive_api(
        hass,
        payload={
            "data": {
                "URL": _ARCHIVE_URL,
                "Error": None,
                "ErrorCode": None,
                "Status": None,
            }
        },
    )

    url = await api.query_camera_archive_stream("CAMERA", 1770000000, 25200)

    assert url == _ARCHIVE_URL
    api.http.get.assert_awaited_once_with(
        "/rest/v1/forpost/cameras/CAMERA/video"
        "?TS=1770000000&TZ=25200&LightStream=0&Format=H264&Speed=-1.0"
    )


@pytest.mark.parametrize(
    "data",
    [
        {"URL": _ARCHIVE_URL, "Error": "Архив недоступен", "ErrorCode": None},
        {"URL": _ARCHIVE_URL, "Error": None, "ErrorCode": 11005},
        {"URL": "", "Error": None, "ErrorCode": None},
        {"URL": None},
        {},
        "not-an-object",
    ],
)
async def test_archive_stream_business_error_or_bad_body_is_none(
    hass, data
) -> None:
    """Бизнес-ошибка при HTTP 200 и непригодное тело — None, без исключения."""
    api = _archive_api(hass, payload={"data": data})

    assert await api.query_camera_archive_stream("CAMERA", 1770000000, 25200) is None


@pytest.mark.parametrize("payload", [None, [], "text"])
async def test_archive_stream_non_object_payload_is_none(hass, payload) -> None:
    api = _archive_api(hass, payload=payload)

    assert await api.query_camera_archive_stream("CAMERA", 1770000000, 25200) is None


async def test_archive_stream_out_of_retention_500_is_none(hass) -> None:
    """HTTP 500 / errorCode 11005 («Архив доступен с …») не выходит из метода."""
    failed = MagicMock(spec=ClientResponse)
    failed.status = 500
    failed.json = AsyncMock(
        return_value={"errorCode": "11005", "errorMessage": "Архив доступен с 01.01"}
    )
    api = _archive_api(hass, side_effect=ClientError(failed))

    assert await api.query_camera_archive_stream("CAMERA", 1770000000, 25200) is None


@pytest.mark.parametrize(
    "error", [TimeoutError(), ClientError(), ValueError("<html>Bad Gateway</html>")]
)
async def test_archive_stream_transport_failure_is_none(hass, error) -> None:
    api = _archive_api(hass, side_effect=error)

    assert await api.query_camera_archive_stream("CAMERA", 1770000000, 25200) is None


async def test_archive_stream_real_http_never_logs_url_or_body(hass, caplog) -> None:
    """Через настоящий `http.py`: ни подписанная ссылка, ни тело — в логах."""
    caplog.set_level(logging.DEBUG)
    api = ElektronnyGorodAPI(hass, UserAgent())
    endpoint = (
        f"https://{BASE_API_URL}/rest/v1/forpost/cameras/CAMERA/video"
        "?TS=1770000000&TZ=25200&LightStream=0&Format=H264&Speed=-1.0"
    )
    response = MagicMock(spec=ClientResponse)
    response.url = endpoint
    response.method = "GET"
    response.status = 200
    response.reason = "OK"
    response.ok = True
    response.headers = {"Content-Length": "128"}
    response.json = AsyncMock(
        return_value={"data": {"URL": _ARCHIVE_URL, "Error": None, "ErrorCode": None}}
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=response)

    with patch(
        "custom_components.elektronny_gorod.http.async_get_clientsession",
        return_value=session,
    ):
        url = await api.query_camera_archive_stream("CAMERA", 1770000000, 25200)

    assert session.get.await_args.args[0] == endpoint
    assert url == _ARCHIVE_URL
    assert "SIGNED-TOKEN" not in caplog.text
    assert "forpost.invalid" not in caplog.text


async def test_archive_stream_failure_logs_never_carry_body(hass, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    api = _archive_api(
        hass,
        payload={"data": {"URL": _ARCHIVE_URL, "Error": "SECRET-ERROR-TEXT"}},
    )

    assert await api.query_camera_archive_stream("CAMERA", 1770000000, 25200) is None
    assert "SIGNED-TOKEN" not in caplog.text
    assert "SECRET-ERROR-TEXT" not in caplog.text
