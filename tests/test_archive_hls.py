"""Tests for same-origin EVENT HLS archive remuxer and views (A-124)."""

from __future__ import annotations

import asyncio
import concurrent.futures
from fractions import Fraction
import io
import logging
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
    async_ensure_archive_pyav,
    async_register_archive_view,
    async_stop_all_archive_sessions,
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
    assert "#EXT-X-TARGETDURATION:6" in first
    assert "0.ts?t=TOK" in first
    assert "#EXT-X-ENDLIST" not in first

    # Growing playlist with irregular segment durations MUST keep TARGETDURATION fixed.
    segs.extend([(3.2, b"seg1"), (1.9, b"seg2")])
    grown = render_event_playlist(segs, "TOK", ended=False)
    assert "#EXT-X-MEDIA-SEQUENCE:0" in grown
    assert "#EXT-X-TARGETDURATION:6" in grown
    assert ["0.ts?t=TOK", "1.ts?t=TOK", "2.ts?t=TOK"] == [
        line for line in grown.splitlines() if line.endswith(".ts?t=TOK")
    ]
    assert "#EXT-X-ENDLIST" not in grown

    finished = render_event_playlist(segs, "TOK", ended=True)
    assert "#EXT-X-TARGETDURATION:6" in finished
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
    trailer: bytes = b"",
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
            if trailer:
                self._bio.write(trailer)

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
    vs = SimpleNamespace(
        index=0,
        type="video",
        name="h264",
        codec_context=SimpleNamespace(codec=SimpleNamespace(canonical_name="h264")),
        time_base=tb,
    )
    as_aac = SimpleNamespace(
        index=1,
        type="audio",
        name="aac",
        profile="LC",
        codec_context=SimpleNamespace(
            codec=SimpleNamespace(canonical_name="aac"),
            sample_rate=44100,
            extradata=b"\x12\x10",
        ),
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
    vs = SimpleNamespace(
        index=0,
        type="video",
        name="h264",
        codec_context=SimpleNamespace(codec=SimpleNamespace(canonical_name="h264")),
        time_base=tb,
    )
    # PyAV 17.0.1 exposes MP3 as `name='mp3float'` without `codec_descriptor`;
    # canonical name lives at `codec_context.codec.canonical_name == 'mp3'`.
    as_mp3 = SimpleNamespace(
        index=1,
        type="audio",
        name="mp3float",
        profile=None,
        codec_context=SimpleNamespace(
            name="mp3float",
            codec=SimpleNamespace(name="mp3float", canonical_name="mp3"),
            sample_rate=44100,
            extradata=None,
        ),
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
            codec_context=SimpleNamespace(
                codec=SimpleNamespace(canonical_name="pcm_alaw"),
                sample_rate=8000,
                extradata=None,
            ),
            time_base=tb,
        ),
        SimpleNamespace(
            index=1,
            type="audio",
            name="aac",
            profile="LC",
            codec_context=SimpleNamespace(
                codec=SimpleNamespace(canonical_name="aac"),
                sample_rate=0,
                extradata=b"\x12",
            ),
            time_base=tb,
        ),
        SimpleNamespace(
            index=1,
            type="audio",
            name="aac",
            profile=None,
            codec_context=SimpleNamespace(
                codec=SimpleNamespace(canonical_name="aac"),
                sample_rate=44100,
                extradata=None,
            ),
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


@pytest.mark.parametrize("rotate", [True, False], ids=["rotation", "tail"])
def test_remux_closes_buffer_when_trailer_exceeds_byte_budget(
    hass, monkeypatch, rotate
) -> None:
    from custom_components.elektronny_gorod import archive_hls

    buffers: list[io.BytesIO] = []

    def track_buffer() -> io.BytesIO:
        buffer = io.BytesIO()
        buffers.append(buffer)
        return buffer

    monkeypatch.setattr(archive_hls, "io", SimpleNamespace(BytesIO=track_buffer))
    video = SimpleNamespace(
        index=0, type="video", name="h264", time_base=Fraction(1, 1000)
    )
    packets = [_pkt(video, 0, keyframe=True)]
    if rotate:
        packets.append(_pkt(video, 2000, keyframe=True))
    trailer = b"trailer"
    fake_av, fake_in, outs = _fake_av_module(
        video_streams=[video], audio_streams=[], packets=packets, trailer=trailer
    )
    monkeypatch.setattr(archive_hls, "_import_av", lambda: fake_av)
    on_segment = MagicMock(return_value=True)
    pipe = _BytePipe(hass.loop)
    max_bytes = len(b"video:0:0;") + len(trailer) - 1

    if rotate:
        assert _remux_flv_to_mpegts(pipe, on_segment, max_bytes=max_bytes) == 0
    else:
        with pytest.raises(BufferError, match="Archive segment byte budget exceeded"):
            _remux_flv_to_mpegts(pipe, on_segment, max_bytes=max_bytes)

    on_segment.assert_not_called()
    assert fake_in.closed
    assert len(outs) == len(buffers) == 1
    assert outs[0].closed
    assert buffers[0].closed


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


def _build_synthetic_flv(
    av: Any,
    *,
    frame_times_ms: list[int],
    keyframe_ms: set[int],
    with_audio: bool = False,
    audio_codec: str | None = None,
    width: int = 64,
    height: int = 64,
) -> bytes:
    """Build a small reproducible FLV fixture in memory (H.264 + optional AAC/MP3)."""
    selected_audio = audio_codec if audio_codec is not None else ("aac" if with_audio else None)
    bio = io.BytesIO()
    out = av.open(bio, mode="w", format="flv")
    vs = out.add_stream("libx264", rate=10)
    vs.width = width
    vs.height = height
    vs.pix_fmt = "yuv420p"
    vs.time_base = Fraction(1, 1000)
    vs.options = {"g": "1000", "keyint_min": "1000", "tune": "zerolatency"}

    as_ = out.add_stream(selected_audio, rate=44100) if selected_audio else None

    total_samples = 0
    for idx, ts_ms in enumerate(frame_times_ms):
        frame = av.VideoFrame(width, height, "yuv420p")
        # Vary luma slightly so compressed size is deterministic and non-trivial.
        for plane in frame.planes:
            plane.update(bytes([((idx * 17) & 0xFF)]) * plane.buffer_size)
        frame.pts = ts_ms
        frame.pict_type = (
            av.video.frame.PictureType.I
            if ts_ms in keyframe_ms
            else av.video.frame.PictureType.P
        )
        for pkt in vs.encode(frame):
            pkt.time_base = Fraction(1, 1000)
            pkt.pts = ts_ms
            pkt.dts = ts_ms
            if ts_ms in keyframe_ms:
                pkt.is_keyframe = True
            out.mux(pkt)
        if as_ is not None:
            frame_samples = as_.codec_context.frame_size or (
                1152 if selected_audio == "mp3" else 1024
            )
            while total_samples * 1000 // 44100 <= ts_ms:
                af = av.AudioFrame(
                    format=as_.format.name,
                    layout=as_.layout.name,
                    samples=frame_samples,
                )
                af.sample_rate = as_.sample_rate
                af.pts = total_samples
                for plane in af.planes:
                    plane.update(b"\x00" * plane.buffer_size)
                total_samples += frame_samples
                for pkt in as_.encode(af):
                    out.mux(pkt)

    for pkt in vs.encode():
        out.mux(pkt)
    if as_ is not None:
        for pkt in as_.encode():
            out.mux(pkt)

    out.close()
    return bio.getvalue()


async def test_remux_enforces_byte_and_duration_budgets_independently(
    hass, monkeypatch
) -> None:
    """Byte cap stops mid-segment before overshoot; duration cap stops long GOPs independently."""
    from custom_components.elektronny_gorod import archive_hls as h

    tb = Fraction(1, 1000)
    vs = SimpleNamespace(index=0, type="video", name="h264", time_base=tb)

    # 1) Byte cap: TrackedBytesIO must never exceed remaining budget on segment 1.
    max_written = 0

    class _TrackedBytesIO(io.BytesIO):
        def write(self, data):
            nonlocal max_written
            n = super().write(data)
            max_written = max(max_written, self.tell())
            return n

    monkeypatch.setattr(h, "io", SimpleNamespace(BytesIO=_TrackedBytesIO))
    # Each packet writes ~26 bytes; seg0 fits (<50 bytes), seg1 exceeds remaining budget (60-len(seg0)).
    packets_bytes = [
        _pkt(vs, 0, keyframe=True),
        _pkt(vs, 1000),
        _pkt(vs, 2000, keyframe=True),
        _pkt(vs, 3000),
        _pkt(vs, 3500),
    ]
    fake_av, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=packets_bytes
    )
    emitted: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_av,
    ):
        count = _remux_flv_to_mpegts(
            _BytePipe(hass.loop),
            lambda d, b: emitted.append((d, b)) or True,
            max_bytes=55,
            max_segment_duration=6.0,
        )
    assert count == 1
    assert len(emitted[0][1]) <= 55
    assert max_written <= 55

    # Tight byte cap on segment 0 fails before publishing anything.
    emitted0: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_av,
    ):
        count0 = _remux_flv_to_mpegts(
            _BytePipe(hass.loop),
            lambda d, b: emitted0.append((d, b)) or True,
            max_bytes=10,
            max_segment_duration=6.0,
        )
    assert count0 == 0
    assert emitted0 == []

    # 2) Duration cap with huge byte cap: 0 -> 2s -> 6.5s (no keyframe) aborts mid-segment.
    packets_dur = [
        _pkt(vs, 0, keyframe=True),
        _pkt(vs, 2000, keyframe=True),  # emits seg 0 (2.0s)
        _pkt(vs, 5000),
        _pkt(vs, 8500),  # elapsed = 6.5s > 6.0s -> aborted before keyframe
    ]
    fake_dur, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=packets_dur
    )
    emitted_dur: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_dur,
    ):
        count_dur = _remux_flv_to_mpegts(
            _BytePipe(hass.loop),
            lambda d, b: emitted_dur.append((d, b)) or True,
            max_bytes=64 * 1024 * 1024,
            max_segment_duration=6.0,
        )
    assert count_dur == 1

    # Tail exceeding max_segment_duration is not emitted.
    packets_tail = [
        _pkt(vs, 0, keyframe=True),
        _pkt(vs, 2000, keyframe=True),
        _pkt(vs, 7500, duration=1000),  # tail = 6.5s > 6.0s
    ]
    fake_tail, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=packets_tail
    )
    emitted_tail: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_tail,
    ):
        count_tail = _remux_flv_to_mpegts(
            _BytePipe(hass.loop),
            lambda d, b: emitted_tail.append((d, b)) or True,
            max_segment_duration=6.0,
        )
    assert count_tail == 1

    # Direct `_LimitedBytesWriter` methods & exact byte-cap exhaustion on next segment.
    from custom_components.elektronny_gorod.archive_hls import _LimitedBytesWriter

    raw_buf = io.BytesIO()
    lim_writer = _LimitedBytesWriter(raw_buf, 10)
    assert lim_writer.writable() is True
    assert lim_writer.seekable() is True
    assert lim_writer.write(b"12345") == 5
    assert lim_writer.tell() == 5
    assert lim_writer.seek(0) == 0

    def _mk_exact_pkts():
        return [
            _pkt(vs, 0, keyframe=True),
            _pkt(vs, 2000, keyframe=True),
        ]

    fake_exact1, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=_mk_exact_pkts()
    )
    probe_exact: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_exact1,
    ):
        _remux_flv_to_mpegts(
            _BytePipe(hass.loop),
            lambda d, b: probe_exact.append((d, b)) or True,
        )
    exact_bytes = len(probe_exact[0][1])
    fake_exact2, _, _ = _fake_av_module(
        video_streams=[vs], audio_streams=[], packets=_mk_exact_pkts()
    )
    emitted_exact: list[tuple[float, bytes]] = []
    with patch(
        "custom_components.elektronny_gorod.archive_hls._import_av",
        return_value=fake_exact2,
    ):
        assert (
            _remux_flv_to_mpegts(
                _BytePipe(hass.loop),
                lambda d, b: emitted_exact.append((d, b)) or True,
                max_bytes=exact_bytes,
            )
            == 1
        )

    # Direct add_segment duration cap also protects session invariants.
    entry = _loaded_entry(hass)
    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="dur-cap",
        coordinator=entry.runtime_data,
        target_duration=4,
    )
    assert sess.add_segment(5.0, b"TOO_LONG") is False
    assert sess.failed is True
    await sess.stop()


async def test_worker_clogged_pipe_timeout_and_cancel_cleanup(hass) -> None:
    """Post-ready mux failure, fut.result timeout, and cancel all close pipe & upstream."""
    entry = _loaded_entry(hass)

    # 1) Clogged 2 MiB pipe + remux exception after seg0 preserves seg0 and drains upstream.
    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="clogged",
        coordinator=entry.runtime_data,
    )

    async def _clogged_upstream() -> None:
        while await sess._pipe.put(b"x" * 32768):
            pass

    def _emit_then_fail(_pipe, emit):
        assert emit(2.0, b"SEG0") is True
        raise RuntimeError("mux failure after seg0")

    sess._upstream_task = asyncio.create_task(_clogged_upstream())
    with patch(
        "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
        side_effect=_emit_then_fail,
    ):
        await asyncio.wait_for(sess._run_worker(), timeout=2.0)
    await asyncio.sleep(0)
    assert sess.ended is True
    assert sess.ready is True
    assert sess.get_segment(0) == b"SEG0"
    assert sess._pipe._closed is True
    assert sess._pipe._buffered == 0
    assert sess._upstream_task.done() is True
    await sess.stop()

    # 2) Simulated fut.result TimeoutError prevents late _async_emit publication.
    sess_to = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="emit-timeout",
        coordinator=entry.runtime_data,
    )
    captured_coros: list[Any] = []

    class _TimeoutFut:
        def result(self, timeout=None):
            raise TimeoutError

        def cancel(self):
            return True

    def _fake_rcts(coro, _loop):
        captured_coros.append(coro)
        return _TimeoutFut()

    def _emit_on_timeout(_pipe, emit):
        assert emit(2.0, b"LATE") is False
        return 0

    with (
        patch(
            "custom_components.elektronny_gorod.archive_hls.asyncio.run_coroutine_threadsafe",
            side_effect=_fake_rcts,
        ),
        patch(
            "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
            side_effect=_emit_on_timeout,
        ),
    ):
        await sess_to._run_worker()
    assert len(captured_coros) == 1
    assert await captured_coros[0] is False
    assert sess_to.segment_count == 0
    await sess_to.stop()

    # 3) Worker CancelledError closes pipe and cancels upstream cleanly.
    sess_cancel = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="worker-cancel",
        coordinator=entry.runtime_data,
    )
    worker_started = asyncio.Event()

    def _blocking_remux(pipe, _emit):
        hass.loop.call_soon_threadsafe(worker_started.set)
        pipe.read(16)
        return 0

    sess_cancel._upstream_task = asyncio.create_task(_clogged_upstream())
    with patch(
        "custom_components.elektronny_gorod.archive_hls._remux_flv_to_mpegts",
        side_effect=_blocking_remux,
    ):
        wt = asyncio.create_task(sess_cancel._run_worker())
        await worker_started.wait()
        wt.cancel()
        with pytest.raises(asyncio.CancelledError):
            await wt
    assert sess_cancel._pipe._closed is True
    await sess_cancel.stop()


async def test_hass_stop_cleans_stalled_session_without_entry_unload(
    hass, caplog
) -> None:
    """Real HA async_stop() shuts down active sessions & idle timers without lingering-task warnings."""
    caplog.set_level(logging.WARNING)
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

    fake_av, _, _ = _fake_av_module(video_streams=[], audio_streams=[], packets=[])

    def _blocking_open(pipe: _BytePipe, *_args: Any, **_kwargs: Any):
        pipe.read(16)
        raise EOFError("pipe closed")

    fake_av.open = _blocking_open

    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="ha-stop",
        coordinator=entry.runtime_data,
    )
    archive_sessions_by_id(hass)[sess.session_id] = sess
    archive_streams(hass)[sess.key] = sess
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
        # Note: NO async_unload_entry called — simulate HA core shutdown directly.
        await hass.async_stop()

    release.set()
    assert sess.alive is False
    assert sess._idle_unsub is None
    assert not archive_sessions_by_id(hass)
    assert not archive_streams(hass)
    assert "was still running after final writes" not in caplog.text
    # Idempotent second call is a safe no-op.
    await async_stop_all_archive_sessions(hass)


async def test_async_ensure_archive_pyav_paths(hass) -> None:
    """PyAV requirement resolution uses HA requirements off the loop and degrades safely."""
    # 1) Already in sys.modules -> no HA requirements call.
    with (
        patch.dict(sys.modules, {"av": SimpleNamespace()}),
        patch(
            "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements"
        ) as req_mock,
    ):
        assert await async_ensure_archive_pyav(hass) is True
        req_mock.assert_not_awaited()

    saved_av = sys.modules.pop("av", None)
    try:
        # 2) Not in sys.modules yet, but importable in executor -> no requirements call.
        with (
            patch(
                "custom_components.elektronny_gorod.archive_hls._import_av",
                return_value=SimpleNamespace(),
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements"
            ) as req_mock,
        ):
            assert await async_ensure_archive_pyav(hass) is True
            req_mock.assert_not_awaited()

        # 3) Missing initially -> calls async_get_integration_with_requirements(hass, 'stream') without setting up stream.
        import_attempts = 0

        def _fake_import_av():
            nonlocal import_attempts
            import_attempts += 1
            if import_attempts == 1:
                raise ModuleNotFoundError("no av yet")
            return SimpleNamespace()

        with (
            patch(
                "custom_components.elektronny_gorod.archive_hls._import_av",
                side_effect=_fake_import_av,
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements",
                AsyncMock(return_value=MagicMock()),
            ) as req_mock,
        ):
            assert await async_ensure_archive_pyav(hass) is True
            req_mock.assert_awaited_once_with(hass, "stream")
            assert "stream" not in hass.config.components

        # 3) Requirement installation failure -> returns False safely and clears key.
        with (
            patch(
                "custom_components.elektronny_gorod.archive_hls._import_av",
                side_effect=ModuleNotFoundError("no av"),
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements",
                AsyncMock(side_effect=RuntimeError("pip offline")),
            ),
        ):
            assert await async_ensure_archive_pyav(hass) is False
        await asyncio.sleep(0)

        # 4) Concurrent consumers + real HA RequirementsManager shared Future: canceling
        # consumer 1 must NOT cancel bootstraps or HA's shared `stream` Future.
        from homeassistant import requirements as ha_reqs
        from custom_components.elektronny_gorod.archive_hls import (
            _ARCHIVE_PYAV_BOOTSTRAP_KEY,
        )

        manager = ha_reqs._async_get_manager(hass)
        ha_future = hass.loop.create_future()
        manager.integrations_with_reqs["stream"] = ha_future
        install_calls = 0
        real_get_reqs = ha_reqs.async_get_integration_with_requirements

        async def _spy_ha_get(target_hass, domain: str):
            nonlocal install_calls
            install_calls += 1
            return await real_get_reqs(target_hass, domain)

        av_ready = False

        def _fake_import_when_ready():
            if not av_ready:
                raise ModuleNotFoundError("still installing")
            return SimpleNamespace()

        try:
            with (
                patch(
                    "custom_components.elektronny_gorod.archive_hls._import_av",
                    side_effect=_fake_import_when_ready,
                ),
                patch(
                    "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements",
                    side_effect=_spy_ha_get,
                ),
            ):
                consumer_1 = asyncio.create_task(async_ensure_archive_pyav(hass))
                consumer_2 = asyncio.create_task(async_ensure_archive_pyav(hass))
                await asyncio.sleep(0)
                bootstrap_task = hass.data.get(_ARCHIVE_PYAV_BOOTSTRAP_KEY)
                assert bootstrap_task is not None and not bootstrap_task.done()
                assert install_calls == 1

                # Timeout/abort cancels consumer_1 only, not bootstrap or HA shared Future.
                consumer_1.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await consumer_1
                await asyncio.sleep(0)
                assert not bootstrap_task.cancelled() and not bootstrap_task.done()
                assert not ha_future.cancelled()

                # Native stream / HA finishes installing requirements without InvalidStateError.
                av_ready = True
                ha_future.set_result(MagicMock())
                assert await consumer_2 is True
                await asyncio.sleep(0)
                assert _ARCHIVE_PYAV_BOOTSTRAP_KEY not in hass.data
        finally:
            manager.integrations_with_reqs.pop("stream", None)

        # 5) Integration-initiated stalled cold install: timeout of consumer_1 does NOT cancel
        # pip install / bootstrap task; consumer_2 finishes cleanly when install resolves.
        pip_started = asyncio.Event()
        pip_release = asyncio.Event()

        async def _slow_cold_install(_target_hass, _domain: str):
            pip_started.set()
            await pip_release.wait()
            return MagicMock()

        av_ready = False
        with (
            patch(
                "custom_components.elektronny_gorod.archive_hls._import_av",
                side_effect=_fake_import_when_ready,
            ),
            patch(
                "custom_components.elektronny_gorod.archive_hls.async_get_integration_with_requirements",
                side_effect=_slow_cold_install,
            ) as slow_req_mock,
        ):
            first = asyncio.create_task(async_ensure_archive_pyav(hass))
            await pip_started.wait()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(first, timeout=0.02)
            bootstrap_task = hass.data.get(_ARCHIVE_PYAV_BOOTSTRAP_KEY)
            assert bootstrap_task is not None and not bootstrap_task.done()
            second = asyncio.create_task(async_ensure_archive_pyav(hass))
            await asyncio.sleep(0)
            assert slow_req_mock.await_count == 1
            av_ready = True
            pip_release.set()
            assert await second is True
            await asyncio.sleep(0)
            assert _ARCHIVE_PYAV_BOOTSTRAP_KEY not in hass.data
    finally:
        if saved_av is not None:
            sys.modules["av"] = saved_av


async def test_stop_releases_published_segments_before_joining_stalled_worker(
    hass,
) -> None:
    """`stop()` frees published segment bytes immediately before awaiting task join."""
    entry = _loaded_entry(hass)
    release_worker = asyncio.Event()
    sess = ArchiveHlsSession(
        hass,
        entry_id=entry.entry_id,
        camera_id=_CAMERA_ID,
        event_id="early-free",
        coordinator=entry.runtime_data,
    )

    async def _stalled_worker() -> None:
        await release_worker.wait()

    sess._worker_task = asyncio.create_task(_stalled_worker())
    assert sess.add_segment(2.0, b"X" * 4096) is True
    assert sess._total_bytes == 4096

    stop_task = asyncio.create_task(sess.stop())
    await asyncio.sleep(0)
    assert not stop_task.done()
    assert sess._segments == []
    assert sess._total_bytes == 0

    release_worker.set()
    await stop_task


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.parametrize("audio_codec", [None, "aac", "mp3"])
async def test_real_pyav_hermetic_flv_decodes_frames_and_pts(
    hass, archive_client, audio_codec: str | None
) -> None:
    """Hermetic real-PyAV remuxing decodes actual video + AAC/MP3 audio frames and PTS."""
    av = pytest.importorskip("av")

    frame_times = [t * 200 for t in range(30)]  # 0..5.8s at 5fps
    flv_bytes = _build_synthetic_flv(
        av,
        frame_times_ms=frame_times,
        keyframe_ms={0, 2000, 4000},
        audio_codec=audio_codec,
    )
    if audio_codec == "mp3":
        # Verify the fixture hits PyAV 17's `mp3float` / `canonical_name == 'mp3'` shape.
        probe = av.open(io.BytesIO(flv_bytes), mode="r", format="flv")
        try:
            in_audio = probe.streams.audio[0]
            assert in_audio.codec_context.codec.canonical_name == "mp3"
            assert not hasattr(in_audio, "codec_descriptor")
        finally:
            probe.close()

    async def _fake_stream(request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(headers={"Content-Type": "video/x-flv"})
        await resp.prepare(request)
        for off in range(0, len(flv_bytes), 4096):
            await resp.write(flv_bytes[off : off + 4096])
            await asyncio.sleep(0)
        return resp

    app = web.Application()
    app.router.add_get("/archive.flv", _fake_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    entry = _loaded_entry(hass)
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

        for _ in range(100):
            if sess.ended:
                break
            await asyncio.sleep(0.02)
        assert sess.ended is True
        assert sess.segment_count == 3

        pl_text = await (await archive_client.get(pl_url)).text()
        assert "#EXT-X-PLAYLIST-TYPE:EVENT" in pl_text
        assert "#EXT-X-MEDIA-SEQUENCE:0" in pl_text
        assert "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES" in pl_text
        assert "#EXT-X-TARGETDURATION:6" in pl_text
        assert "#EXT-X-ENDLIST" in pl_text

        total_video_frames = 0
        total_audio_frames = 0
        prev_v_pts: int | None = None
        for idx in range(sess.segment_count):
            seg_bytes = await (
                await archive_client.get(
                    f"/api/elektronny_gorod/archive/{sess.session_id}/{idx}.ts?t={tok}"
                )
            ).read()
            c = av.open(io.BytesIO(seg_bytes), format="mpegts")
            streams = (
                (c.streams.video[0], c.streams.audio[0])
                if audio_codec is not None
                else (c.streams.video[0],)
            )
            seg_v = 0
            seg_a = 0
            for decoded in c.decode(*streams):
                if isinstance(decoded, av.VideoFrame):
                    assert decoded.width == 64 and decoded.height == 64
                    assert decoded.pts is not None
                    if prev_v_pts is not None:
                        assert decoded.pts > prev_v_pts
                    prev_v_pts = decoded.pts
                    seg_v += 1
                else:
                    assert decoded.samples > 0 and decoded.pts is not None
                    seg_a += 1
            assert seg_v > 0
            if audio_codec is not None:
                assert seg_a > 0
            else:
                assert not c.streams.audio
            total_video_frames += seg_v
            total_audio_frames += seg_a
            c.close()

        assert total_video_frames == len(frame_times)
        if audio_codec is not None:
            assert total_audio_frames > 0
    finally:
        await sess.stop()
        await runner.cleanup()


async def test_real_pyav_irregular_gop_and_independent_limits(hass, monkeypatch) -> None:
    """Real PyAV: irregular 0/2/5.2/7.2s keeps TARGETDURATION fixed; >6s and >max_bytes stop cleanly."""
    av = pytest.importorskip("av")
    from custom_components.elektronny_gorod import archive_hls as h

    # 1) Irregular GOP: 0, 2.0, 5.2, 7.2 -> durations 2.0, 3.2, 2.0, 0.8 (all <= 6.0).
    times_irr = [t * 200 for t in range(40)]  # 0..7.8s
    flv_irr = _build_synthetic_flv(
        av, frame_times_ms=times_irr, keyframe_ms={0, 2000, 5200, 7200}
    )
    pipe_irr = _BytePipe(hass.loop)
    await pipe_irr.put(flv_irr)
    pipe_irr.finish()
    segs_irr: list[tuple[float, bytes]] = []
    targets: list[str] = []

    def _on_irr(dur: float, data: bytes) -> bool:
        segs_irr.append((dur, data))
        pl = render_event_playlist(segs_irr, "TOK", ended=False)
        targets.append(
            next(l for l in pl.splitlines() if l.startswith("#EXT-X-TARGETDURATION:"))
        )
        return True

    assert _remux_flv_to_mpegts(pipe_irr, _on_irr) == 4
    assert targets == ["#EXT-X-TARGETDURATION:6"] * 4

    # 2) Duration overflow: keys at 0, 2.0, 9.0 -> seg 1 exceeds 6.0s -> only seg 0 published.
    times_long = [t * 500 for t in range(20)]  # 0..9.5s
    flv_long = _build_synthetic_flv(
        av, frame_times_ms=times_long, keyframe_ms={0, 2000, 9000}
    )
    pipe_long = _BytePipe(hass.loop)
    await pipe_long.put(flv_long)
    pipe_long.finish()
    segs_long: list[tuple[float, bytes]] = []
    assert (
        _remux_flv_to_mpegts(
            pipe_long,
            lambda d, b: segs_long.append((d, b)) or True,
            max_bytes=64 * 1024 * 1024,
            max_segment_duration=6.0,
        )
        == 1
    )
    assert len(segs_long) == 1

    # 3) Byte overflow on short 2s GOPs: cap stops mid-write before exceeding remaining budget.
    peak_written = 0

    class _TrackedBytesIO(io.BytesIO):
        def write(self, data):
            nonlocal peak_written
            n = super().write(data)
            peak_written = max(peak_written, self.tell())
            return n

    monkeypatch.setattr(h, "io", SimpleNamespace(BytesIO=_TrackedBytesIO))
    flv_short = _build_synthetic_flv(
        av,
        frame_times_ms=[t * 200 for t in range(30)],
        keyframe_ms={0, 2000, 4000},
    )
    pipe_short = _BytePipe(hass.loop)
    await pipe_short.put(flv_short)
    pipe_short.finish()
    segs_short: list[tuple[float, bytes]] = []
    # Measure seg 0 size first, then allow seg 0 + half of seg 1.
    probe_segs: list[tuple[float, bytes]] = []
    probe_pipe = _BytePipe(hass.loop)
    await probe_pipe.put(flv_short)
    probe_pipe.finish()
    _remux_flv_to_mpegts(probe_pipe, lambda d, b: probe_segs.append((d, b)) or True)
    budget = len(probe_segs[0][1]) + len(probe_segs[1][1]) // 2
    peak_written = 0
    assert (
        _remux_flv_to_mpegts(
            pipe_short,
            lambda d, b: segs_short.append((d, b)) or True,
            max_bytes=budget,
            max_segment_duration=6.0,
        )
        == 1
    )
    assert peak_written <= max(len(segs_short[0][1]), budget - len(segs_short[0][1]))


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
    av = pytest.importorskip("av")

    from homeassistant.components.media_source.models import MediaSourceItem

    from custom_components.elektronny_gorod.api import CameraHistoryEvent
    from custom_components.elektronny_gorod.media_source import (
        ElektronnyGorodMediaSource,
        async_stop_archive_streams,
    )

    frame_times = [t * 200 for t in range(70)]  # 0..13.8s -> 7 segments
    flv_bytes = _build_synthetic_flv(
        av,
        frame_times_ms=frame_times,
        keyframe_ms={0, 2000, 4000, 6000, 8000, 10000, 12000},
        with_audio=True,
    )
    split_point = (len(flv_bytes) * 2) // 3
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
        assert "#EXT-X-TARGETDURATION:6" in pl_early
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
        assert "#EXT-X-TARGETDURATION:6" in pl_late
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
