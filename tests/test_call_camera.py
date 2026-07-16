# tests/test_call_camera.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.elektronny_gorod.call_camera import ElektronnyGorodCallCamera
from custom_components.elektronny_gorod.const import (
    CALL_STATE_ENDED,
    CALL_STATE_ERROR,
    EVENT_CALL_STATE,
)
from homeassistant.core import Event

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
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell if cid == "1013" else None)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        url = await cam.stream_source()
    doorbell.stream_source.assert_awaited_once()  # bootstrap видео-источника (mock doorbell)
    # eg_intercom_call собран: свежее видео (copy) + аудио моста
    srcs = upsert.await_args.args[2]
    assert srcs == [
        "rtsp://127.0.0.1:8554/eg_1013#video=copy",
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
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
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


async def test_stream_source_none_when_upsert_fails():
    """upsert стрима упал (напр. раздутый go2rtc-конфиг) → None, а не мёртвый URL (404)."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac"
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    upsert = AsyncMock(side_effect=RuntimeError("go2rtc audio PUT failed: HTTP 400"))
    cam = _cam(c, lambda cid: doorbell)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        result = await cam.stream_source()
    assert result is None


async def test_available_only_during_active_call():
    """available=True только при активном вызове (иначе HA не стримит → нет вечных 404)."""
    c = MagicMock()
    c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    assert cam.available is False
    c.active_call_media.return_value = ("1013", MagicMock())
    assert cam.available is True


async def test_available_false_when_controller_none():
    cam = ElektronnyGorodCallCamera(
        controller_getter=lambda: None,
        go2rtc_base_url="http://g:1984",
        go2rtc_headers={}, rtsp_host="127.0.0.1",
        doorbell_lookup=lambda cid: None,
        entry_id="e1",
    )
    assert cam.available is False


async def test_camera_image_delegates_to_doorbell_snapshot():
    """async_camera_image → снапшот камеры домофона (не NotImplementedError)."""
    c = MagicMock()
    c.active_call_media.return_value = ("1013", MagicMock())
    doorbell = MagicMock()
    doorbell.async_camera_image = AsyncMock(return_value=b"jpeg-bytes")
    cam = _cam(c, lambda cid: doorbell if cid == "1013" else None)
    img = await cam.async_camera_image(300, 200)
    assert img == b"jpeg-bytes"
    doorbell.async_camera_image.assert_awaited_once_with(300, 200)


async def test_camera_image_none_without_active_call():
    """Вне вызова — None (нет кадра), без NotImplementedError."""
    c = MagicMock()
    c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    assert await cam.async_camera_image() is None


def test_on_call_state_writes_ha_state():
    """EVENT_CALL_STATE → запись состояния (чтобы фронт увидел смену available)."""
    c = MagicMock()
    c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    cam.async_write_ha_state = MagicMock()
    cam._on_call_state(MagicMock())
    cam.async_write_ha_state.assert_called_once()


async def test_stream_source_dedup_same_call_no_rebuild():
    """A-88: повторный stream_source в пределах одного звонка НЕ пересобирает стрим
    (второй клиент/WebRTC re-offer подключается к тому же продюсеру)."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus"
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        url1 = await cam.stream_source()
        url2 = await cam.stream_source()  # тот же звонок (тот же bridge)
    assert url1 == url2 == "rtsp://127.0.0.1:8554/eg_intercom_call"
    assert upsert.await_count == 1  # собрано ОДИН раз
    assert doorbell.stream_source.await_count == 1  # operator-URL не пере-фетчен


async def test_stream_source_concurrent_opens_deduped():
    """A-88: два ОДНОВРЕМЕННЫХ первых открытия (warm-up + фронтенд) собирают стрим
    один раз — второй ждёт in-flight future, а не пере-собирает (double upsert)."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:audio"
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    gate = asyncio.Event()

    async def slow_stream_source():
        await gate.wait()  # держим первую сборку, пока не войдёт вторая
        return "rtsp://127.0.0.1:8554/eg_1013"

    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(side_effect=slow_stream_source)
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        t1 = asyncio.create_task(cam.stream_source())
        t2 = asyncio.create_task(cam.stream_source())
        await asyncio.sleep(0.01)  # оба вошли: t1 занял future, t2 ждёт его
        gate.set()
        url1, url2 = await asyncio.gather(t1, t2)
    assert url1 == url2 == "rtsp://127.0.0.1:8554/eg_intercom_call"
    assert upsert.await_count == 1  # собрано ОДИН раз, второй ждал future
    assert doorbell.stream_source.await_count == 1  # operator-URL не пере-фетчен


async def test_stream_source_rebuilds_on_new_call():
    """Новый звонок (новый bridge) → пересборка; кэш сбрасывается между звонками."""
    b1 = MagicMock(); b1.go2rtc_src = "ffmpeg:a"
    b2 = MagicMock(); b2.go2rtc_src = "ffmpeg:b"
    c = MagicMock()
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        c.active_call_media.return_value = ("1013", b1)
        await cam.stream_source()
        c.active_call_media.return_value = None  # звонок кончился → сброс кэша
        await cam.stream_source()
        c.active_call_media.return_value = ("1013", b2)  # новый звонок
        await cam.stream_source()
    assert upsert.await_count == 2  # пересобрано на новый звонок, не на каждое открытие


async def test_teardown_on_ended_removes_stream_and_clears_cache():
    """A-88 A1: на `ended` снимаем go2rtc-стрим и сбрасываем кэш."""
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac"
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_1013")
    remove = AsyncMock()
    cam = _cam(c, lambda cid: doorbell)
    session = MagicMock()
    with patch(f"{_CC}.upsert_audio_stream", new=AsyncMock()), patch(
        f"{_CC}.remove_audio_stream", new=remove
    ), patch(f"{_CC}.async_get_clientsession", return_value=session):
        cam.hass = MagicMock()
        await cam.stream_source()
        assert cam._call_stream_cache is not None
        await cam._teardown_call_stream()
    assert cam._call_stream_cache is None
    remove.assert_awaited_once_with(
        "http://g:1984", "eg_intercom_call", session, {}
    )


async def test_teardown_idempotent_after_ended():
    """Повторный teardown идемпотентен (best-effort remove)."""
    cam = _cam(MagicMock(), lambda cid: None)
    remove = AsyncMock()
    with patch(f"{_CC}.remove_audio_stream", new=remove), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        await cam._teardown_call_stream()
        await cam._teardown_call_stream()
    assert remove.await_count == 2


async def test_stream_source_none_after_teardown():
    """После teardown и конца вызова stream_source → None."""
    c = MagicMock(); c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    cam._call_stream_cache = (1, "rtsp://127.0.0.1:8554/eg_intercom_call")
    assert await cam.stream_source() is None
    assert cam._call_stream_cache is None


async def test_on_call_state_schedules_teardown_on_ended():
    """EVENT_CALL_STATE `ended` → задача teardown."""
    cam = _cam(MagicMock(), lambda cid: None)
    cam.hass = MagicMock()
    cam.async_write_ha_state = MagicMock()
    created: list = []

    def _capture(coro):
        created.append(coro)
        return MagicMock()

    cam.hass.async_create_task.side_effect = _capture
    with patch(f"{_CC}.remove_audio_stream", new=AsyncMock()), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam._on_call_state(Event(EVENT_CALL_STATE, {"state": CALL_STATE_ENDED}))
        assert len(created) == 1
        await created[0]
    cam.async_write_ha_state.assert_called_once()


async def test_on_call_state_schedules_teardown_on_error():
    cam = _cam(MagicMock(), lambda cid: None)
    cam.hass = MagicMock()
    cam.async_write_ha_state = MagicMock()
    created: list = []

    def _capture(coro):
        created.append(coro)
        return MagicMock()

    cam.hass.async_create_task.side_effect = _capture
    with patch(f"{_CC}.remove_audio_stream", new=AsyncMock()), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam._on_call_state(Event(EVENT_CALL_STATE, {"state": CALL_STATE_ERROR}))
        assert len(created) == 1
        await created[0]


async def test_stream_source_uses_shared_go2rtc_rtsp_not_operator_pull():
    """A-88 A3: call stream берёт RTSP eg_<id> через async_go2rtc_video_rtsp."""
    from custom_components.elektronny_gorod.camera import ElektronnyGorodCamera

    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus"
    c = MagicMock(); c.active_call_media.return_value = ("1013", bridge)
    doorbell = ElektronnyGorodCamera.__new__(ElektronnyGorodCamera)
    doorbell.async_go2rtc_video_rtsp = AsyncMock(
        return_value="rtsp://127.0.0.1:8554/eg_1013"
    )
    doorbell.stream_source = AsyncMock()
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell if cid == "1013" else None)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        url = await cam.stream_source()
    doorbell.async_go2rtc_video_rtsp.assert_awaited_once()
    doorbell.stream_source.assert_not_awaited()
    srcs = upsert.await_args.args[2]
    assert srcs[0] == "rtsp://127.0.0.1:8554/eg_1013#video=copy"
    assert url == "rtsp://127.0.0.1:8554/eg_intercom_call"
