"""Tests for same-origin EVENT HLS archive remuxer and views (A-124)."""

from __future__ import annotations

import asyncio
from fractions import Fraction
import io
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError, web
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.elektronny_gorod.archive_hls import (
    ArchiveHlsSession,
    _BytePipe,
    _remux_flv_to_mpegts,
    archive_sessions_by_id,
    archive_streams,
    async_register_archive_view,
    enforce_active_session_limit,
    pop_entry_sessions_by_id,
    pop_entry_stop_tasks,
    render_event_playlist,
    sign_archive_token,
    stop_archive_session_in_background,
    verify_archive_token,
)
from custom_components.elektronny_gorod.clip_proxy import (
    async_register_clip_view,
    sign_clip_token,
    verify_clip_token,
)
from custom_components.elektronny_gorod.const import DOMAIN

_ENTRY_ID = "entry-1"
_CAMERA_ID = "111"
_EVENT_ID = "3001"
_OPERATOR_URL = "https://forpost-1.example:18081/rtsp/STREAM-ID/SECRET-TOKEN/d=1"

_BENCH_DIR = Path("/tmp/eg-a92-merge.rVuFfZAG")
_BENCH_LIBS = _BENCH_DIR / "stream-test-libs"
_FLV_VIDEO_ONLY = _BENCH_DIR / "a124-test-pattern.flv"
_FLV_AV = _BENCH_DIR / "a124-timecoded-av.flv"


def _load_real_av():
    """Import real PyAV if available (installed or in local bench libs)."""
    try:
        return __import__("av")
    except ModuleNotFoundError:
        if _BENCH_LIBS.is_dir():
            if str(_BENCH_LIBS) not in sys.path:
                sys.path.insert(0, str(_BENCH_LIBS))
            try:
                return __import__("av")
            except ModuleNotFoundError:
                return None
        return None


def _coordinator() -> SimpleNamespace:
    return SimpleNamespace(api=SimpleNamespace())


def _loaded_entry(hass, entry_id: str | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Test", entry_id=entry_id)
    entry.add_to_hass(hass)
    entry.runtime_data = _coordinator()
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


@pytest.fixture
async def archive_client(hass, hass_client):
    """HTTP test client with both archive and clip views registered."""
    assert await async_setup_component(hass, "http", {})
    async_register_clip_view(hass)
    async_register_archive_view(hass)
    return await hass_client()


def test_render_event_playlist_anchors_sequence_zero_and_preserves_first_segment() -> None:
    segs: list[tuple[float, bytes]] = [(2.0, b"seg0")]
    first = render_event_playlist(segs, "TOK", ended=False)
    assert "#EXTM3U" in first
    assert "#EXT-X-VERSION:3" in first
    assert "#EXT-X-PLAYLIST-TYPE:EVENT" in first
    assert "#EXT-X-MEDIA-SEQUENCE:0" in first
    assert "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES" in first
    assert "#EXT-X-TARGETDURATION:2" in first
    assert "0.ts?t=TOK" in first
    assert "#EXT-X-ENDLIST" not in first

    segs.extend([(2.1, b"seg1"), (1.9, b"seg2")])
    grown = render_event_playlist(segs, "TOK", ended=False)
    assert "#EXT-X-MEDIA-SEQUENCE:0" in grown
    assert "#EXT-X-TARGETDURATION:3" in grown
    assert ["0.ts?t=TOK", "1.ts?t=TOK", "2.ts?t=TOK"] == [
        line for line in grown.splitlines() if line.endswith(".ts?t=TOK")
    ]
    assert "#EXT-X-ENDLIST" not in grown

    finished = render_event_playlist(segs, "TOK", ended=True)
    assert finished.splitlines()[-1] == "#EXT-X-ENDLIST"


def test_archive_token_binding_expiry_and_clip_scope_isolation(hass) -> None:
    tok = sign_archive_token(
        hass, "sess-1", _ENTRY_ID, _CAMERA_ID, _EVENT_ID, now=1000.0
    )
    assert verify_archive_token(
        hass, tok, "sess-1", _ENTRY_ID, _CAMERA_ID, _EVENT_ID, now=1001.0
    )
    assert not verify_archive_token(
        hass, tok, "sess-2", _ENTRY_ID, _CAMERA_ID, _EVENT_ID, now=1001.0
    )
    assert not verify_archive_token(
        hass, tok, "sess-1", "entry-2", _CAMERA_ID, _EVENT_ID, now=1001.0
    )
    assert not verify_archive_token(
        hass, tok, "sess-1", _ENTRY_ID, "222", _EVENT_ID, now=1001.0
    )
    assert not verify_archive_token(
        hass, tok, "sess-1", _ENTRY_ID, _CAMERA_ID, "3002", now=1001.0
    )
    assert not verify_archive_token(
        hass, tok, "sess-1", _ENTRY_ID, _CAMERA_ID, _EVENT_ID, now=1601.0
    )
    assert not verify_archive_token(
        hass, "1000000.non-ascii-дайджест", "sess-1", _ENTRY_ID, _CAMERA_ID, _EVENT_ID
    )

    clip_tok = sign_clip_token(hass, _ENTRY_ID, _EVENT_ID, now=1000.0)
    assert not verify_archive_token(
        hass, clip_tok, "sess-1", _ENTRY_ID, _CAMERA_ID, _EVENT_ID, now=1001.0
    )
    assert not verify_clip_token(hass, tok, _ENTRY_ID, _EVENT_ID, now=1001.0)


async def test_byte_pipe_backpressure_and_close_independence(hass) -> None:
    pipe = _BytePipe(hass.loop, max_bytes=8)
    assert pipe.readable() is True
    assert pipe.seekable() is False
    assert await pipe.put(b"") is True
    assert await pipe.put(b"12345678") is True

    blocked_put = asyncio.create_task(pipe.put(b"90"))
    await asyncio.sleep(0.01)
    assert not blocked_put.done()

    assert pipe.read(0) == b""
    assert pipe.read(4) == b"1234"
    assert await asyncio.wait_for(blocked_put, timeout=0.5) is True
    assert pipe.read(4) == b"5678"
    assert pipe.read(4) == b"90"

    # Blocked read wakes immediately on close(), and subsequent put fails.
    read_fut = hass.loop.run_in_executor(None, pipe.read, 16)
    await asyncio.sleep(0.01)
    assert not read_fut.done()
    pipe.close()
    assert await asyncio.wait_for(read_fut, timeout=0.5) == b""
    assert await pipe.put(b"x") is False

    # Normal finish() drains remaining chunks before EOF.
    pipe2 = _BytePipe(hass.loop, max_bytes=64)
    assert await pipe2.put(b"abc") is True
    pipe2.finish()
    assert pipe2.read(16) == b"abc"
    assert pipe2.read(16) == b""


def _fake_av_module(
    *,
    video_streams: list[Any],
    audio_streams: list[Any],
    packets: list[Any],
    mux_side_effect: Exception | None = None,
):
    """Build a lightweight fake `av` module for PyAV-free CI runs."""

    class _FakeOut:
        def __init__(self, bio: io.BytesIO) -> None:
            self._bio = bio
            self._muxed: list[Any] = []
            self.closed = False

        def add_stream_from_template(self, tmpl: Any) -> SimpleNamespace:
            return SimpleNamespace(template=tmpl)

        def mux(self, pkt: Any) -> None:
            if mux_side_effect is not None:
                raise mux_side_effect
            self._muxed.append(pkt)
            self._bio.write(f"{pkt.stream.template.type}:{pkt.dts}:{pkt.pts};".encode())

        def close(self) -> None:
            self.closed = True

    class _FakeIn:
        def __init__(self) -> None:
            self.streams = SimpleNamespace(video=video_streams, audio=audio_streams)
            self.closed = False

        def demux(self, *_streams: Any):
            return iter(packets)

        def close(self) -> None:
            self.closed = True

    fake_in = _FakeIn()
    opened_outs: list[_FakeOut] = []

    def _open(target: Any, mode: str = "r", **_kwargs: Any) -> Any:
        if mode == "r":
            return fake_in
        out = _FakeOut(target)
        opened_outs.append(out)
        return out

    return SimpleNamespace(open=_open), fake_in, opened_outs


def _pkt(
    stream: Any,
    dts: int | None,
    *,
    pts: int | None = None,
    keyframe: bool = False,
    duration: int = 1000,
) -> SimpleNamespace:
    return SimpleNamespace(
        stream=stream,
        dts=dts,
        pts=dts if pts is None else pts,
        is_keyframe=keyframe,
        duration=duration,
        time_base=stream.time_base,
    )


def test_remux_fake_av_rebases_grows_and_handles_audio_variants(hass) -> None:
    tb = Fraction(1, 1000)
    vs = SimpleNamespace(index=0, type="video", name="h264", time_base=tb)
    as_aac = SimpleNamespace(
        index=1,
        type="audio",
        name="aac",
        profile="LC",
        codec_descriptor=SimpleNamespace(name="aac"),
        codec_context=SimpleNamespace(sample_rate=44100, extradata=b"\x12\x10"),
        time_base=tb,
    )
    packets = [
        _pkt(vs, None, keyframe=True),  # ignored: dts None
        _pkt(as_aac, 900),  # ignored: before first keyframe
        _pkt(vs, 950, keyframe=False),  # ignored: non-keyframe before start
        _pkt(vs, 1000, pts=1040, keyframe=True),  # base_sec = 1.0
        _pkt(as_aac, 990),  # ignored: dts < base_sec
        _pkt(as_aac, 1000),
        _pkt(as_aac, 1000),  # ignored: non-monotonic dts
        _pkt(vs, 2000),
        _pkt(vs, 3000, keyframe=True),  # emits seg 0 (2.0s)
        _pkt(vs, 4000),  # tail seg 1
    ]
    fake_av, fake_in, _outs = _fake_av_module(
        video_streams=[vs], audio_streams=[as_aac], packets=packets
    )
    pipe = _BytePipe(hass.loop)
    emitted: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_av,
    ):
        count = _remux_flv_to_mpegts(
            pipe, lambda d, b: emitted.append((d, b)) or True
        )

    assert count == 2
    assert fake_in.closed is True
    assert emitted[0][0] == pytest.approx(2.0)
    assert emitted[0][1].startswith(b"video:0:40;audio:0:0;video:1000:1000;")
    assert emitted[1][1].startswith(b"video:2000:2000;video:3000:3000;")


def test_remux_fake_av_mp3_and_unsupported_codecs(hass) -> None:
    tb = Fraction(1, 1000)
    vs = SimpleNamespace(index=0, type="video", name="h264", time_base=tb)
    as_mp3 = SimpleNamespace(
        index=1,
        type="audio",
        name="mp3float",
        profile=None,
        codec_descriptor=SimpleNamespace(name="mp3"),
        codec_context=SimpleNamespace(sample_rate=44100, extradata=None),
        time_base=tb,
    )
    fake_av, _, _ = _fake_av_module(
        video_streams=[vs],
        audio_streams=[as_mp3],
        packets=[_pkt(vs, 0, keyframe=True), _pkt(as_mp3, 0)],
    )
    emitted: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_av,
    ):
        count = _remux_flv_to_mpegts(
            _BytePipe(hass.loop), lambda d, b: emitted.append((d, b)) or True
        )
    assert count == 1
    assert b"audio:0:0;" in emitted[0][1]

    # Unsupported audio (pcm_alaw) and uninitialized AAC (no extradata/profile) are dropped.
    for bad_audio in (
        SimpleNamespace(
            index=1,
            type="audio",
            name="pcm_alaw",
            profile=None,
            codec_descriptor=SimpleNamespace(name="pcm_alaw"),
            codec_context=SimpleNamespace(sample_rate=8000, extradata=None),
            time_base=tb,
        ),
        SimpleNamespace(
            index=1,
            type="audio",
            name="aac",
            profile="LC",
            codec_descriptor=SimpleNamespace(name="aac"),
            codec_context=SimpleNamespace(sample_rate=0, extradata=b"\x12"),
            time_base=tb,
        ),
        SimpleNamespace(
            index=1,
            type="audio",
            name="aac",
            profile=None,
            codec_descriptor=SimpleNamespace(name="aac"),
            codec_context=SimpleNamespace(sample_rate=44100, extradata=None),
            time_base=tb,
        ),
    ):
        fake_av2, _, _ = _fake_av_module(
            video_streams=[vs],
            audio_streams=[bad_audio],
            packets=[_pkt(vs, 0, keyframe=True), _pkt(bad_audio, 0)],
        )
        emitted2: list[tuple[float, bytes]] = []
        with patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_av2,
        ):
            _remux_flv_to_mpegts(
                _BytePipe(hass.loop), lambda d, b: emitted2.append((d, b)) or True
            )
        assert b"audio:" not in emitted2[0][1]


def test_remux_fake_av_rejects_missing_or_non_h264_video_and_handles_abort(hass) -> None:
    tb = Fraction(1, 1000)
    fake_no_video, _, _ = _fake_av_module(video_streams=[], audio_streams=[], packets=[])
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_no_video,
        ),
        pytest.raises(ValueError, match="no video"),
    ):
        _remux_flv_to_mpegts(_BytePipe(hass.loop), lambda _d, _b: True)

    vs_flv1 = SimpleNamespace(index=0, type="video", name="flv", time_base=tb)
    fake_flv1, _, _ = _fake_av_module(
        video_streams=[vs_flv1], audio_streams=[], packets=[]
    )
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_flv1,
        ),
        pytest.raises(ValueError, match="Unsupported archive video codec"),
    ):
        _remux_flv_to_mpegts(_BytePipe(hass.loop), lambda _d, _b: True)

    # Abort callback stops remux immediately without emitting tail.
    vs = SimpleNamespace(index=0, type="video", name="h264", time_base=tb)
    fake_abort, _, _ = _fake_av_module(
        video_streams=[vs],
        audio_streams=[],
        packets=[
            _pkt(vs, 0, keyframe=True),
            _pkt(vs, 2000, keyframe=True),
            _pkt(vs, 3000),
        ],
    )
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_abort,
    ):
        assert _remux_flv_to_mpegts(_BytePipe(hass.loop), lambda _d, _b: False) == 0

    # Inner mux error closes cur_out without masking original error.
    fake_err, fake_in, outs = _fake_av_module(
        video_streams=[vs],
        audio_streams=[],
        packets=[_pkt(vs, 0, keyframe=True)],
        mux_side_effect=RuntimeError("mux boom"),
    )
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_err,
        ),
        pytest.raises(RuntimeError, match="mux boom"),
    ):
        _remux_flv_to_mpegts(_BytePipe(hass.loop), lambda _d, _b: True)
    assert fake_in.closed is True
    assert outs[0].closed is True


async def test_archive_views_security_headers_and_client_disconnect(
    hass, archive_client, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    entry = _loaded_entry(hass)
    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id=_EVENT_ID,
        coordinator=entry.runtime_data,
    )
    archive_sessions_by_id(hass)[sess.session_id] = sess

    # Not ready yet (0 segments) -> 404.
    url = sess.playlist_url(hass)
    tok = url.split("?t=", 1)[1]
    assert (await archive_client.get(url)).status == 404

    sess.add_segment(2.0, b"SEG0DATA")
    sess.add_segment(2.0, b"SEG1DATA")

    # Valid playlist + segments.
    pl_resp = await archive_client.get(url)
    assert pl_resp.status == 200
    assert pl_resp.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert pl_resp.headers["Cache-Control"] == "private, no-store"
    pl_text = await pl_resp.text()
    assert "#EXT-X-PLAYLIST-TYPE:EVENT" in pl_text
    assert "#EXT-X-MEDIA-SEQUENCE:0" in pl_text
    assert "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES" in pl_text
    assert f"0.ts?t={tok}" in pl_text
    assert f"1.ts?t={tok}" in pl_text

    seg0_resp = await archive_client.get(
        f"/api/elektronny_gorod/archive/{sess.session_id}/0.ts?t={tok}"
    )
    assert seg0_resp.status == 200
    assert seg0_resp.headers["Content-Type"] == "video/mp2t"
    assert seg0_resp.headers["Cache-Control"] == "private, no-store"
    assert await seg0_resp.read() == b"SEG0DATA"

    # Missing segment -> 404.
    assert (
        await archive_client.get(
            f"/api/elektronny_gorod/archive/{sess.session_id}/99.ts?t={tok}"
        )
    ).status == 404

    # Foreign / tampered / missing / clip-scoped / expired tokens -> 403.
    clip_tok = sign_clip_token(hass, entry.entry_id, _EVENT_ID)
    expired_tok = sign_archive_token(
        hass, sess.session_id, entry.entry_id, _CAMERA_ID, _EVENT_ID, now=1.0
    )
    for bad_url in (
        f"/api/elektronny_gorod/archive/{sess.session_id}/playlist.m3u8",
        f"/api/elektronny_gorod/archive/{sess.session_id}/playlist.m3u8?t=tampered",
        f"/api/elektronny_gorod/archive/{sess.session_id}/playlist.m3u8?t={clip_tok}",
        f"/api/elektronny_gorod/archive/{sess.session_id}/playlist.m3u8?t={expired_tok}",
        f"/api/elektronny_gorod/archive/{sess.session_id}/0.ts?t={clip_tok}",
        f"/api/elektronny_gorod/archive/{sess.session_id}/0.ts?t={expired_tok}",
    ):
        assert (await archive_client.get(bad_url)).status == 403

    # Clip view also rejects archive tokens (403).
    assert (
        await archive_client.get(
            f"/api/elektronny_gorod/clips/{entry.entry_id}/{_EVENT_ID}?t={tok}"
        )
    ).status == 403

    # Unknown session -> 404.
    assert (
        await archive_client.get(
            f"/api/elektronny_gorod/archive/no-such-session/playlist.m3u8?t={tok}"
        )
    ).status == 404

    # Client disconnect during segment write does not raise or kill session.
    with patch.object(
        web.StreamResponse, "write", AsyncMock(side_effect=ConnectionResetError)
    ):
        disc_resp = await archive_client.get(
            f"/api/elektronny_gorod/archive/{sess.session_id}/0.ts?t={tok}"
        )
        assert disc_resp.status == 200
    assert sess.alive is True

    # Reloaded/unloaded coordinator invalidates session (404) and stops it.
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)
    assert (await archive_client.get(url)).status == 404
    await hass.async_block_till_done()
    assert sess.alive is False
    assert _OPERATOR_URL not in caplog.text


async def test_session_caps_eviction_idle_and_upstream_errors(
    hass, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    entry = _loaded_entry(hass)

    # Cap on max_bytes stops upstream and sets ended=True preserving segment 0.
    sess_cap = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="1",
        coordinator=entry.runtime_data,
        max_bytes=10,
        max_segments=5,
    )
    assert sess_cap.add_segment(2.0, b"123456") is True
    assert sess_cap.add_segment(2.0, b"123456") is False
    assert sess_cap.ended is True
    assert sess_cap.get_segment(0) == b"123456"
    assert sess_cap.get_segment(1) is None

    # Cap exceeded on very first segment marks failed.
    sess_first_cap = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="2",
        coordinator=entry.runtime_data,
        max_bytes=4,
    )
    assert sess_first_cap.add_segment(2.0, b"123456") is False
    assert sess_first_cap.failed is True
    await sess_first_cap.stop()

    # Active session limit evicts LRU session.
    sessions = []
    for idx in range(4):
        s = ArchiveHlsSession(
            hass,
            entry_id=entry.entry_id,
            camera_id=_CAMERA_ID,
            event_id=str(10 + idx),
            coordinator=entry.runtime_data,
        )
        s.last_access = 100.0 + idx
        archive_sessions_by_id(hass)[s.session_id] = s
        archive_streams(hass)[s.key] = s
        sessions.append(s)
    sessions[0].last_access = 500.0  # touched -> sessions[1] is now oldest
    enforce_active_session_limit(hass)
    await hass.async_block_till_done()
    assert sessions[1].session_id not in archive_sessions_by_id(hass)
    assert sessions[1].alive is False
    assert sessions[0].session_id in archive_sessions_by_id(hass)

    # Clean remaining sessions.
    for s in sessions:
        await s.stop()
    archive_sessions_by_id(hass).clear()
    archive_streams(hass).clear()

    # Idle timeout callback stops inactive session.
    sess_idle = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="idle",
        coordinator=entry.runtime_data,
        idle_timeout=0.02,
    )
    archive_sessions_by_id(hass)[sess_idle.session_id] = sess_idle
    archive_streams(hass)[sess_idle.key] = sess_idle
    sess_idle.touch()
    await asyncio.sleep(0.06)
    await hass.async_block_till_done()
    assert sess_idle.alive is False
    assert sess_idle.session_id not in archive_sessions_by_id(hass)

    # Upstream HTTP 404 -> mark_failed without leaking operator URL.
    resp_404 = MagicMock(status=404)
    cm_404 = MagicMock()
    cm_404.__aenter__ = AsyncMock(return_value=resp_404)
    cm_404.__aexit__ = AsyncMock(return_value=False)
    http_session = MagicMock()
    http_session.get = MagicMock(return_value=cm_404)
    sess_404 = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="404",
        coordinator=entry.runtime_data,
    )
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
            return_value=http_session,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
            side_effect=lambda pipe, _emit: (pipe.read(16), 0)[1],
        ),
    ):
        sess_404.start(_OPERATOR_URL)
        await asyncio.wait_for(sess_404.fail_event.wait(), timeout=1.0)
        await sess_404.stop()
    assert "SECRET-TOKEN" not in caplog.text
    assert "forpost-1.example" not in caplog.text

    # Upstream ClientError after 1 segment -> preserves segment and marks ended.
    cm_err = MagicMock()
    cm_err.__aenter__ = AsyncMock(side_effect=ClientError("boom"))
    cm_err.__aexit__ = AsyncMock(return_value=False)
    http_session.get = MagicMock(return_value=cm_err)
    sess_partial = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="partial",
        coordinator=entry.runtime_data,
    )
    sess_partial.add_segment(2.0, b"SEG0")
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
            return_value=http_session,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
            side_effect=lambda pipe, _emit: (pipe.read(16), 0)[1],
        ),
    ):
        sess_partial.start(_OPERATOR_URL)
        await hass.async_block_till_done()
    assert sess_partial.ended is True
    assert sess_partial.alive is True
    assert sess_partial.ready is True
    assert pop_entry_sessions_by_id(hass, entry.entry_id) == []
    archive_sessions_by_id(hass)[sess_partial.session_id] = sess_partial
    assert pop_entry_sessions_by_id(hass, entry.entry_id) == [sess_partial]
    await sess_partial.stop()
    assert not pop_entry_stop_tasks(hass, entry.entry_id)

    # `_import_av` uses importlib.import_module("av")
    with patch("importlib.import_module", return_value="fake-av") as imp:
        from custom_components.elektronny_gorod.archive_hls import _import_av

        assert _import_av() == "fake-av"
        imp.assert_called_once_with("av")

    # Background stop task tracking when `stop()` yields.
    sess_bg = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="bg-stop",
        coordinator=entry.runtime_data,
    )
    bg_release = asyncio.Event()

    async def _slow_bg_stop() -> None:
        await bg_release.wait()

    sess_bg.stop = _slow_bg_stop  # type: ignore[method-assign]
    bg_task = stop_archive_session_in_background(hass, sess_bg)
    assert bg_task in pop_entry_stop_tasks(hass, entry.entry_id)
    bg_release.set()
    await bg_task


async def test_hung_upstream_stops_immediately_without_waiting_for_network(
    hass,
) -> None:
    entry = _loaded_entry(hass)
    started = asyncio.Event()
    release = asyncio.Event()

    async def _hung_aenter():
        started.set()
        await release.wait()

    cm_hung = MagicMock()
    cm_hung.__aenter__ = AsyncMock(side_effect=_hung_aenter)
    cm_hung.__aexit__ = AsyncMock(return_value=False)
    http_session = MagicMock()
    http_session.get = MagicMock(return_value=cm_hung)

    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="hung",
        coordinator=entry.runtime_data,
    )
    fake_av, _, _ = _fake_av_module(video_streams=[], audio_streams=[], packets=[])

    def _blocking_open(pipe: _BytePipe, *_args: Any, **_kwargs: Any):
        pipe.read(16)
        raise EOFError("pipe closed")

    fake_av.open = _blocking_open

    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
            return_value=http_session,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_av,
        ),
    ):
        sess.start(_OPERATOR_URL)
        await asyncio.wait_for(started.wait(), timeout=1.0)
        await asyncio.wait_for(sess.stop(), timeout=1.0)
        assert not release.is_set()
    release.set()


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.parametrize(
    ("flv_path", "expect_audio"),
    [
        (_FLV_VIDEO_ONLY, False),
        (_FLV_AV, True),
    ],
)
async def test_real_pyav_synthetic_flv_end_to_end_event_playlist(
    hass, archive_client, flv_path: Path, expect_audio: bool
) -> None:
    """Real PyAV remuxing of synthetic FLV fixtures into growing EVENT HLS."""
    av = _load_real_av()
    if av is None or not flv_path.is_file():
        pytest.skip("Real PyAV or synthetic FLV bench fixture not present")

    entry = _loaded_entry(hass)
    flv_bytes = flv_path.read_bytes()

    async def _fake_stream(request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(headers={"Content-Type": "video/x-flv"})
        await resp.prepare(request)
        for off in range(0, len(flv_bytes), 16384):
            await resp.write(flv_bytes[off : off + 16384])
            await asyncio.sleep(0)
        return resp

    app = web.Application()
    app.router.add_get("/archive.flv", _fake_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id=_EVENT_ID,
        coordinator=entry.runtime_data,
    )
    archive_sessions_by_id(hass)[sess.session_id] = sess
    try:
        sess.start(f"http://127.0.0.1:{port}/archive.flv")
        await asyncio.wait_for(sess.ready_event.wait(), timeout=5.0)
        pl_url = sess.playlist_url(hass)
        tok = pl_url.split("?t=", 1)[1]

        # Poll until worker finishes remuxing the synthetic FLV.
        for _ in range(100):
            if sess.ended:
                break
            await asyncio.sleep(0.02)
        assert sess.ended is True
        assert sess.segment_count >= 6

        pl_resp = await archive_client.get(pl_url)
        assert pl_resp.status == 200
        pl_text = await pl_resp.text()
        assert "#EXT-X-PLAYLIST-TYPE:EVENT" in pl_text
        assert "#EXT-X-MEDIA-SEQUENCE:0" in pl_text
        assert "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES" in pl_text
        assert f"0.ts?t={tok}" in pl_text
        assert f"{sess.segment_count - 1}.ts?t={tok}" in pl_text
        assert "#EXT-X-ENDLIST" in pl_text

        # Segment 0 and last segment decode cleanly as MPEG-TS with expected streams.
        for idx in (0, sess.segment_count - 1):
            seg_resp = await archive_client.get(
                f"/api/elektronny_gorod/archive/{sess.session_id}/{idx}.ts?t={tok}"
            )
            assert seg_resp.status == 200
            seg_bytes = await seg_resp.read()
            c = av.open(io.BytesIO(seg_bytes), format="mpegts")
            types = {s.type for s in c.streams}
            assert "video" in types
            assert ("audio" in types) is expect_audio
            c.close()
    finally:
        await sess.stop()
        await runner.cleanup()


async def test_session_worker_with_fake_av_runs_upstream_and_remux(hass) -> None:
    """Full `ArchiveHlsSession.start()` with mocked HTTP + fake PyAV (PyAV-free CI)."""
    entry = _loaded_entry(hass)
    tb = Fraction(1, 1000)
    vs = SimpleNamespace(index=0, type="video", name="h264", time_base=tb)
    packets = [
        _pkt(vs, 0, keyframe=True),
        _pkt(vs, 2000, keyframe=True),
        _pkt(vs, 3000),
    ]
    fake_av, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=packets
    )

    async def _iter_chunks(_size: int):
        yield b"FLV..."

    resp = MagicMock(status=200)
    resp.content = MagicMock()
    resp.content.iter_chunked = _iter_chunks
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    http_session = MagicMock()
    http_session.get = MagicMock(return_value=cm)

    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="worker-ok",
        coordinator=entry.runtime_data,
    )
    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
            return_value=http_session,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._import_av",
            return_value=fake_av,
        ),
    ):
        sess.start(_OPERATOR_URL)
        await asyncio.wait_for(sess.ready_event.wait(), timeout=2.0)
        for _ in range(50):
            if sess.ended:
                break
            await asyncio.sleep(0.01)
    assert sess.ended is True
    assert sess.segment_count == 2
    await sess.stop()

    # Worker exception after 1 segment preserves segment 0 and marks ended.
    sess_partial = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="worker-partial",
        coordinator=entry.runtime_data,
    )

    def _emit_one_then_boom(_pipe, on_seg):
        on_seg(2.0, b"SEG0")
        raise RuntimeError("corrupt tail")

    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_clientsession",
            return_value=http_session,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
            side_effect=_emit_one_then_boom,
        ),
    ):
        sess_partial.start(_OPERATOR_URL)
        await asyncio.wait_for(sess_partial.ready_event.wait(), timeout=2.0)
        for _ in range(50):
            if sess_partial.ended:
                break
            await asyncio.sleep(0.01)
    assert sess_partial.ended is True
    assert sess_partial.get_segment(0) == b"SEG0"
    await sess_partial.stop()


@pytest.mark.usefixtures("socket_enabled")
async def test_media_source_progressive_event_hls_keeps_segment_zero(
    hass, archive_client
) -> None:
    """End-to-end MediaSource + real PyAV progressive FLV keeps segment 0 in EVENT playlist."""
    av = _load_real_av()
    if av is None or not _FLV_AV.is_file():
        pytest.skip("Real PyAV or synthetic FLV bench fixture not present")

    from homeassistant.components.media_source.models import MediaSourceItem

    from custom_components.elektronny_gorod.api import CameraHistoryEvent
    from custom_components.elektronny_gorod.media_source import (
        ElektronnyGorodMediaSource,
        async_stop_archive_streams,
    )

    flv_bytes = _FLV_AV.read_bytes()
    split_point = len(flv_bytes) // 3
    allow_rest = asyncio.Event()

    async def _progressive_stream(request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(headers={"Content-Type": "video/x-flv"})
        await resp.prepare(request)
        await resp.write(flv_bytes[:split_point])
        await allow_rest.wait()
        await resp.write(flv_bytes[split_point:])
        return resp

    app = web.Application()
    app.router.add_get("/progressive.flv", _progressive_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    now_ts = int(dt_util.utcnow().timestamp())
    event = CameraHistoryEvent(
        id=_EVENT_ID,
        camera_id=_CAMERA_ID,
        backend_camera_id="4001",
        timestamp=now_ts - 10,
        duration=60,
        event_subject_id=126,
        available=True,
        goto_enabled=True,
    )
    day_str = dt_util.as_local(dt_util.utc_from_timestamp(event.timestamp)).strftime(
        "%Y%m%d"
    )
    entry = _loaded_entry(hass)
    entry.runtime_data = SimpleNamespace(
        api=SimpleNamespace(
            query_camera_events=AsyncMock(return_value=(event,)),
            query_camera_archive_stream=AsyncMock(
                return_value=f"http://127.0.0.1:{port}/progressive.flv"
            ),
        ),
        data={
            "places": [{"place": {"id": "1001", "address": "ул. Тестовая 1"}}],
            "cameras": [
                {
                    "id": _CAMERA_ID,
                    "name": "Подъезд",
                    "place_id": "1001",
                    "source": "intercom",
                }
            ],
        },
    )

    source = ElektronnyGorodMediaSource(hass)
    try:
        play = await source.async_resolve_media(
            MediaSourceItem(
                hass=hass,
                domain=DOMAIN,
                identifier=f"{entry.entry_id}/1001/{_CAMERA_ID}/{day_str}/{_EVENT_ID}",
                target_media_player=None,
            )
        )
        assert play.mime_type == "application/x-mpegURL"
        assert play.url.startswith("/api/elektronny_gorod/archive/")

        pl_early = await (await archive_client.get(play.url)).text()
        assert "#EXT-X-MEDIA-SEQUENCE:0" in pl_early
        assert "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES" in pl_early
        assert "#EXT-X-ENDLIST" not in pl_early
        early_segs = [l for l in pl_early.splitlines() if ".ts?t=" in l]
        assert early_segs[0].startswith("0.ts?t=")
        seg0_early = await (
            await archive_client.get(
                play.url.replace("playlist.m3u8", "0.ts")
            )
        ).read()

        # Release remainder of FLV and wait for playlist growth + ENDLIST.
        allow_rest.set()
        for _ in range(100):
            pl_late = await (await archive_client.get(play.url)).text()
            if "#EXT-X-ENDLIST" in pl_late:
                break
            await asyncio.sleep(0.02)
        assert "#EXT-X-ENDLIST" in pl_late
        assert "#EXT-X-MEDIA-SEQUENCE:0" in pl_late
        late_segs = [l for l in pl_late.splitlines() if ".ts?t=" in l]
        assert len(late_segs) > len(early_segs)
        assert late_segs[0] == early_segs[0]
        seg0_late = await (
            await archive_client.get(
                play.url.replace("playlist.m3u8", "0.ts")
            )
        ).read()
        assert seg0_late == seg0_early
    finally:
        allow_rest.set()
        await async_stop_archive_streams(hass, entry.entry_id)
        await runner.cleanup()
