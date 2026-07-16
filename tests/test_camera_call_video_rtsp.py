"""A-88 A3: `async_go2rtc_video_rtsp` — reuse eg_<id> без operator-pull."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.elektronny_gorod.camera import ElektronnyGorodCamera


def _bare_camera(*, use_go2rtc: bool = True) -> ElektronnyGorodCamera:
    cam = ElektronnyGorodCamera.__new__(ElektronnyGorodCamera)
    cam._use_go2rtc = use_go2rtc
    cam._id = "1013"
    cam._name = "Door"
    cam._go2rtc_rtsp_host = "127.0.0.1"
    cam._go2rtc_username = None
    cam._go2rtc_password = None
    cam._go2rtc_stream_name = "eg_1013"
    cam._stream_manager = MagicMock() if use_go2rtc else None
    if cam._stream_manager is not None:
        cam._stream_manager.client.rtsp_url.return_value = (
            "rtsp://127.0.0.1:8554/eg_1013"
        )
    return cam


async def test_async_go2rtc_video_rtsp_reuses_when_producer_exists():
    cam = _bare_camera()
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 100}], [])
    )
    cam.stream_source = AsyncMock()
    url = await cam.async_go2rtc_video_rtsp()
    assert url == "rtsp://127.0.0.1:8554/eg_1013"
    cam.stream_source.assert_not_awaited()


async def test_async_go2rtc_video_rtsp_bootstraps_when_no_producer():
    cam = _bare_camera()
    cam._fetch_go2rtc_stream_info = AsyncMock(return_value=([], []))
    cam.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    url = await cam.async_go2rtc_video_rtsp()
    assert url == "rtsp://127.0.0.1:8554/eg_1013"
    cam.stream_source.assert_awaited_once()


async def test_async_go2rtc_video_rtsp_bootstraps_when_producer_has_no_traffic():
    """A-88: producer есть, но `bytes_recv`==0 (пустой/handshake) → НЕ reuse,
    иначе переиспользуем мёртвую operator-сессию → замороженное видео (A-71)."""
    cam = _bare_camera()
    cam._fetch_go2rtc_stream_info = AsyncMock(return_value=([{"bytes_recv": 0}], []))
    cam.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    url = await cam.async_go2rtc_video_rtsp()
    assert url == "rtsp://127.0.0.1:8554/eg_1013"
    cam.stream_source.assert_awaited_once()  # bootstrap, не reuse


async def test_async_go2rtc_video_rtsp_bootstraps_when_bytes_recv_missing():
    """Producer без поля `bytes_recv` (нестандартный ответ) → НЕ reuse (bootstrap)."""
    cam = _bare_camera()
    cam._fetch_go2rtc_stream_info = AsyncMock(return_value=([{}], []))
    cam.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    url = await cam.async_go2rtc_video_rtsp()
    assert url == "rtsp://127.0.0.1:8554/eg_1013"
    cam.stream_source.assert_awaited_once()


async def test_async_go2rtc_video_rtsp_without_go2rtc_uses_stream_source():
    cam = _bare_camera(use_go2rtc=False)
    cam.stream_source = AsyncMock(return_value="https://operator/flv")
    url = await cam.async_go2rtc_video_rtsp()
    assert url == "https://operator/flv"
    cam.stream_source.assert_awaited_once()
