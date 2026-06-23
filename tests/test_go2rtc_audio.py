"""Unit-тесты upsert/remove аудио-стрима вызова (go2rtc.py).

Аудио-мост two-way (audio-bridge-design.md): per-call go2rtc-стрим
`ffmpeg:http://<bridge>` через REST. PATCH-first / PUT-fallback (как камеры).
NB: консолидация go2rtc-клиента (R1-R6) отложена — это свежие методы.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
        "http://go2rtc:1984", "eg_intercom_talk", "ffmpeg:http://h:1/x#audio=opus", s, {}
    )
    s.patch.assert_called_once()
    s.put.assert_not_called()
    url = s.patch.call_args.args[0]
    assert "name=eg_intercom_talk" in url and "/api/streams" in url


async def test_upsert_audio_stream_put_fallback_on_patch_4xx():
    s = _session(404)
    await upsert_audio_stream("http://go2rtc:1984", "eg_intercom_talk", "ffmpeg:x", s, {})
    s.put.assert_called_once()


def test_go2rtc_auth_headers():
    assert go2rtc_auth_headers(None, None) == {}
    assert go2rtc_auth_headers("u", "") == {}
    h = go2rtc_auth_headers("user", "pass")
    assert h["Authorization"].startswith("Basic ")
