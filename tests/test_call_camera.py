# tests/test_call_camera.py
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.elektronny_gorod.call_camera import ElektronnyGorodCallCamera

_CC = "custom_components.elektronny_gorod.call_camera"


def _cam(controller, doorbell_lookup, entry_id="e1"):
    return ElektronnyGorodCallCamera(
        controller_getter=lambda: controller,
        go2rtc_base_url="http://g:1984",
        go2rtc_headers={}, rtsp_host="127.0.0.1",
        doorbell_lookup=doorbell_lookup,
        entry_id=entry_id,
    )


async def test_stream_source_none_without_active_call():
    c = MagicMock(); c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    assert await cam.stream_source() is None


async def test_stream_source_none_when_controller_not_ready():
    """controller_getter() возвращает None (контроллер ещё не создан) → None без падения."""
    cam = ElektronnyGorodCallCamera(
        controller_getter=lambda: None,
        go2rtc_base_url="http://g:1984",
        go2rtc_headers={}, rtsp_host="127.0.0.1",
        doorbell_lookup=lambda cid: None,
        entry_id="e1",
    )
    assert await cam.stream_source() is None


async def test_stream_source_builds_fresh_combined_and_returns_rtsp():
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus"
    c = MagicMock(); c.active_call_media.return_value = ("5593590", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_5593590")
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell if cid == "5593590" else None)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        url = await cam.stream_source()
    doorbell.stream_source.assert_awaited_once()  # рефреш видео-источника
    # eg_intercom_call собран: свежее видео (copy) + аудио моста
    srcs = upsert.await_args.args[2]
    assert srcs == [
        "rtsp://127.0.0.1:8554/eg_5593590#video=copy",
        "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus",
    ]
    assert url == "rtsp://127.0.0.1:8554/eg_intercom_call"


async def test_unique_id_includes_entry_id():
    """unique_id должен содержать entry_id для scoping по entry."""
    c = MagicMock()
    cam = _cam(c, lambda cid: None, entry_id="abc123")
    assert cam.unique_id == "elektronny_gorod_abc123_intercom_call"


async def test_stream_source_none_when_no_doorbell_for_camera_id():
    """Нет doorbell-камеры для данного camera_id → None."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac"
    c = MagicMock(); c.active_call_media.return_value = ("999", bridge)
    cam = _cam(c, lambda cid: None)  # doorbell не найден
    assert await cam.stream_source() is None


async def test_stream_source_none_when_doorbell_stream_source_empty():
    """doorbell.stream_source() вернул None → None из call camera."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac"
    c = MagicMock(); c.active_call_media.return_value = ("5593590", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value=None)
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        result = await cam.stream_source()
    assert result is None
    upsert.assert_not_awaited()
