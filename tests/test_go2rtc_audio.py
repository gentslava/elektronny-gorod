"""Unit-тесты upsert/remove аудио-стрима вызова (go2rtc.py).

Аудио-мост two-way (audio-bridge-design.md): per-call go2rtc-стрим
`ffmpeg:http://<bridge>` через REST. PATCH-first / PUT-fallback (как камеры).
NB: консолидация go2rtc-клиента (R1-R6) отложена — это свежие методы.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.go2rtc import (
    go2rtc_auth_headers,
    upsert_audio_stream,
)


class _Ctx:
    def __init__(self, resp):
        self._r = resp

    async def __aenter__(self):
        return self._r

    async def __aexit__(self, *a):
        return False


def _resp(status: int):
    r = AsyncMock()
    r.status = status
    r.text = AsyncMock(return_value="")
    return r


def _session(patch_status: int):
    s = MagicMock()
    s.patch = MagicMock(return_value=_Ctx(_resp(patch_status)))
    s.put = MagicMock(return_value=_Ctx(_resp(200)))
    return s


async def test_upsert_audio_stream_patch_first():
    s = _session(200)
    await upsert_audio_stream(
        "http://go2rtc:1984", "eg_intercom_call", ["ffmpeg:http://h:1/x#audio=opus"], s, {}
    )
    s.patch.assert_called_once()
    s.put.assert_not_called()
    url = s.patch.call_args.args[0]
    assert "name=eg_intercom_call" in url and "/api/streams" in url


async def test_upsert_audio_stream_put_fallback_on_patch_4xx():
    s = _session(404)
    await upsert_audio_stream("http://go2rtc:1984", "eg_intercom_call", ["ffmpeg:x"], s, {})
    s.put.assert_called_once()


async def test_upsert_audio_stream_multi_src_video_plus_audio():
    # B: видео камеры (RTSP) + аудио моста → два src= в query (go2rtc склеивает).
    s = _session(200)
    await upsert_audio_stream(
        "http://go2rtc:1984", "eg_intercom_call",
        ["rtsp://127.0.0.1:8554/eg_5#video=copy", "ffmpeg:http://b:40020#audio=opus"], s, {},
    )
    url = s.patch.call_args.args[0]
    assert url.count("src=") == 2
    assert "rtsp" in url and "ffmpeg" in url


def test_go2rtc_auth_headers():
    assert go2rtc_auth_headers(None, None) == {}
    assert go2rtc_auth_headers("u", "") == {}
    h = go2rtc_auth_headers("user", "pass")
    assert h["Authorization"].startswith("Basic ")


# ─── Проба RTSP-порта ───────────────────────────────────────────────────────


async def test_open_rtsp_port_is_detected() -> None:
    """Открытый порт распознаётся — иначе настройку отвергнут зря."""
    from custom_components.elektronny_gorod.go2rtc import _probe_rtsp_port

    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    with patch(
        "custom_components.elektronny_gorod.go2rtc.asyncio.open_connection",
        new=AsyncMock(return_value=(MagicMock(), writer)),
    ):
        assert await _probe_rtsp_port("127.0.0.1", 8554, 1.0) is True
    writer.close.assert_called_once()


@pytest.mark.parametrize("failure", [OSError("отказано"), TimeoutError()])
async def test_closed_rtsp_port_is_reported(failure) -> None:
    """Закрытый порт находят при настройке, а не когда видео не пошло.

    HTTP-интерфейс go2rtc может отвечать, а RTSP быть закрыт брандмауэром
    или собран без модуля — без этой пробы человек узнаёт об этом только
    когда камера не воспроизводится.
    """
    from custom_components.elektronny_gorod.go2rtc import _probe_rtsp_port

    with patch(
        "custom_components.elektronny_gorod.go2rtc.asyncio.open_connection",
        new=AsyncMock(side_effect=failure),
    ):
        assert await _probe_rtsp_port("127.0.0.1", 8554, 1.0) is False


async def test_reset_while_closing_still_counts_as_open() -> None:
    """Обрыв при закрытии пробы не означает, что порт закрыт."""
    from custom_components.elektronny_gorod.go2rtc import _probe_rtsp_port

    writer = MagicMock()
    writer.wait_closed = AsyncMock(side_effect=OSError("connection reset"))
    with patch(
        "custom_components.elektronny_gorod.go2rtc.asyncio.open_connection",
        new=AsyncMock(return_value=(MagicMock(), writer)),
    ):
        assert await _probe_rtsp_port("127.0.0.1", 8554, 1.0) is True
