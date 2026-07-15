"""HAR-backed API contract tests for camera stream URLs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponse

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
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
