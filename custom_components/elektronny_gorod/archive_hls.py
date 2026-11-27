"""Same-origin EVENT HLS proxy for in-progress archive playback (A-124).

HA native Stream HLS uses a rolling window (`MAX_SEGMENTS=5`) and hardcodes
`#EXT-X-START:TIME-OFFSET=-2.000`, so in-progress archive playback jumps near
the live edge instead of starting from segment 0. This module remuxes the
operator's `video/x-flv` stream (H.264 + optional AAC/MP3) into MPEG-TS
segments via PyAV and serves a growing `#EXT-X-PLAYLIST-TYPE:EVENT` playlist
anchored at sequence 0 (`#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES`).

The operator's signed URL stays strictly server-side inside `aiohttp` (`av`
reads from an in-memory `_BytePipe`, so even `libav.*` logs never see the
operator URL). Client requests use opaque session IDs and HMAC-signed tokens
scoped to `"archive"` and bound to `(session_id, entry_id, camera_id, event_id)`.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Iterator
import concurrent.futures
import contextlib
from dataclasses import dataclass
import importlib
import io
import secrets
import sys
import threading
import time
from typing import Any

from aiohttp import ClientError, ClientTimeout, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.requirements import async_get_integration_with_requirements

from .clip_proxy import sign_scoped_token, verify_scoped_token
from .const import DOMAIN, LOGGER
from .coordinator import async_get_coordinator

_ARCHIVE_VIEW_REGISTERED = f"{DOMAIN}_archive_view_registered"
_ARCHIVE_STOP_LISTENER_KEY = f"{DOMAIN}_archive_stop_listener"
_ARCHIVE_PYAV_BOOTSTRAP_KEY = f"{DOMAIN}_archive_pyav_bootstrap"
ARCHIVE_STREAMS_KEY = f"{DOMAIN}_archive_streams"
_ARCHIVE_BY_ID_KEY = f"{DOMAIN}_archive_sessions_by_id"
ARCHIVE_IN_FLIGHT_KEY = f"{DOMAIN}_archive_in_flight"
_ARCHIVE_STOP_TASKS_KEY = f"{DOMAIN}_archive_stop_tasks"

_ARCHIVE_TOKEN_SCOPE = "archive"
_ARCHIVE_TOKEN_TTL = 600.0

_SEGMENT_DURATION_SEC = 2.0
_TARGET_DURATION_SEC = 6
_CHUNK_SIZE = 32 * 1024
_PIPE_MAX_BYTES = 2 * 1024 * 1024
_MAX_SESSION_BYTES = 64 * 1024 * 1024
_MAX_SESSION_SEGMENTS = 600
_MAX_ACTIVE_SESSIONS = 4
_SESSION_IDLE_TIMEOUT_SEC = 60.0

_UPSTREAM_TIMEOUT = ClientTimeout(total=None, sock_connect=10.0, sock_read=30.0)
_AUDIO_CODECS = frozenset({"aac", "mp3"})


def _import_av() -> Any:
    """Lazy import of PyAV so environments without `av` can still import."""
    return importlib.import_module("av")


def _try_import_av() -> bool:
    """Return True if PyAV can be imported (runs off the event loop)."""
    try:
        _import_av()
    except ImportError:
        return False
    return True


async def _bootstrap_archive_pyav(hass: HomeAssistant) -> bool:
    """Resolve `stream` requirements through HA and import PyAV off the loop."""
    try:
        await async_get_integration_with_requirements(hass, "stream")
    except Exception as ex:  # noqa: BLE001 - optional dependency boundary
        LOGGER.debug(
            "Archive HLS PyAV requirements unavailable (%s)",
            type(ex).__name__,
        )
        return False
    return await hass.async_add_executor_job(_try_import_av)


async def async_ensure_archive_pyav(hass: HomeAssistant) -> bool:
    """Ensure PyAV is available via a single shielded HA bootstrap task."""
    if "av" in sys.modules:
        return True
    if await hass.async_add_executor_job(_try_import_av):
        return True
    task: asyncio.Task[bool] | None = hass.data.get(_ARCHIVE_PYAV_BOOTSTRAP_KEY)
    if task is None or task.done():
        task = hass.async_create_task(
            _bootstrap_archive_pyav(hass),
            name=f"{DOMAIN}_archive_pyav_bootstrap",
        )
        if not task.done():
            hass.data[_ARCHIVE_PYAV_BOOTSTRAP_KEY] = task

            def _clear_bootstrap(finished: asyncio.Task[bool]) -> None:
                if hass.data.get(_ARCHIVE_PYAV_BOOTSTRAP_KEY) is finished:
                    hass.data.pop(_ARCHIVE_PYAV_BOOTSTRAP_KEY, None)

            task.add_done_callback(_clear_bootstrap)
    return await asyncio.shield(task)


def sign_archive_token(
    hass: HomeAssistant,
    session_id: str,
    entry_id: str,
    camera_id: str,
    event_id: str,
    *,
    now: float | None = None,
) -> str:
    """Sign one archive HLS token bound to session, entry, camera and event."""
    return sign_scoped_token(
        hass,
        _ARCHIVE_TOKEN_SCOPE,
        f"{session_id}:{entry_id}:{camera_id}:{event_id}",
        _ARCHIVE_TOKEN_TTL,
        now=now,
    )


def verify_archive_token(
    hass: HomeAssistant,
    token: str,
    session_id: str,
    entry_id: str,
    camera_id: str,
    event_id: str,
    *,
    now: float | None = None,
) -> bool:
    """Verify an archive HLS token in constant time."""
    return verify_scoped_token(
        hass,
        token,
        _ARCHIVE_TOKEN_SCOPE,
        f"{session_id}:{entry_id}:{camera_id}:{event_id}",
        now=now,
    )


class _BytePipe:
    """Thread-safe bounded pipe fed by asyncio upstream and read by PyAV.

    `close()` wakes both blocked `read()` in the PyAV executor and any awaiting
    `put()` on the event loop immediately, independent of upstream progress.
    """

    def __init__(
        self, loop: asyncio.AbstractEventLoop, max_bytes: int = _PIPE_MAX_BYTES
    ) -> None:
        self._loop = loop
        self._max_bytes = max_bytes
        self._chunks: deque[bytes] = deque()
        self._buffered = 0
        self._eof = False
        self._closed = False
        self._cond = threading.Condition()
        self._space_event = asyncio.Event()
        self._space_event.set()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    async def put(self, chunk: bytes) -> bool:
        """Append bytes to the pipe, applying backpressure at `max_bytes`."""
        if not chunk:
            return not self._closed
        while True:
            with self._cond:
                if self._closed:
                    return False
                if self._buffered < self._max_bytes:
                    self._chunks.append(chunk)
                    self._buffered += len(chunk)
                    if self._buffered >= self._max_bytes:
                        self._space_event.clear()
                    self._cond.notify_all()
                    return True
                self._space_event.clear()
            await self._space_event.wait()

    def finish(self) -> None:
        """Signal normal upstream EOF so PyAV drains buffered bytes and ends."""
        with self._cond:
            self._eof = True
            self._cond.notify_all()

    def close(self) -> None:
        """Abort the pipe immediately, dropping buffered bytes and waking waiters."""
        with self._cond:
            self._closed = True
            self._eof = True
            self._chunks.clear()
            self._buffered = 0
            self._cond.notify_all()
        self._space_event.set()

    def read(self, size: int = _CHUNK_SIZE) -> bytes:
        """Blocking read for PyAV executor; returns `b""` on EOF or `close()`."""
        if size == 0:
            return b""
        with self._cond:
            while not self._chunks and not self._eof and not self._closed:
                self._cond.wait()
            if self._closed or (not self._chunks and self._eof):
                return b""
            head = self._chunks.popleft()
            if size > 0 and len(head) > size:
                out, rest = head[:size], head[size:]
                self._chunks.appendleft(rest)
            else:
                out = head
            self._buffered -= len(out)
            if self._buffered < self._max_bytes:
                with contextlib.suppress(RuntimeError):
                    self._loop.call_soon_threadsafe(self._space_event.set)
            return out


def _stream_codec_name(stream: Any) -> str | None:
    """Return canonical codec name via PyAV's `codec_context.codec.canonical_name`."""
    codec_ctx = getattr(stream, "codec_context", None)
    codec = getattr(codec_ctx, "codec", None) if codec_ctx is not None else None
    canonical = getattr(codec, "canonical_name", None) if codec is not None else None
    if canonical:
        return str(canonical)
    name = getattr(codec_ctx, "name", None) if codec_ctx is not None else None
    return str(name) if name else getattr(stream, "name", None)


def _is_supported_audio(stream: Any) -> bool:
    """Return True if the FLV audio stream can be remuxed into browser MPEG-TS."""
    codec_name = _stream_codec_name(stream)
    if codec_name not in _AUDIO_CODECS:
        return False
    codec_ctx = getattr(stream, "codec_context", None)
    if codec_ctx is not None and getattr(codec_ctx, "sample_rate", 1) <= 0:
        return False
    if codec_name == "aac":
        extradata = (
            getattr(codec_ctx, "extradata", None) if codec_ctx is not None else None
        )
        if getattr(stream, "profile", None) is None and not extradata:
            return False
    return True


class _SegmentBudgetExceeded(BufferError):
    """Raised when an in-progress MPEG-TS segment exceeds the byte budget."""


class _LimitedBytesWriter:
    """Writable wrapper around `io.BytesIO` enforcing a hard byte cap."""

    def __init__(self, inner: Any, limit: int) -> None:
        self._inner = inner
        self._limit = limit

    def write(self, data: bytes | bytearray | memoryview) -> int:
        if self._inner.tell() + len(data) > self._limit:
            raise _SegmentBudgetExceeded("Archive segment byte budget exceeded")
        return self._inner.write(data)

    def tell(self) -> int:
        return self._inner.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._inner.seek(offset, whence)

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True


def _select_flv_streams(inp: Any) -> tuple[Any, Any | None, tuple[Any, ...]]:
    """Validate H.264 video and select demux streams from an open FLV container."""
    video_streams = inp.streams.video
    if not video_streams:
        raise ValueError("Archive stream has no video")
    vs = video_streams[0]
    video_codec = _stream_codec_name(vs)
    if video_codec != "h264":
        raise ValueError(f"Unsupported archive video codec: {video_codec}")
    audio_streams = inp.streams.audio
    as_ = audio_streams[0] if audio_streams else None
    if as_ is not None and not _is_supported_audio(as_):
        as_ = None
    streams_to_demux = (vs, as_) if as_ is not None else (vs,)
    return vs, as_, streams_to_demux


def _rebase_packet(pkt: Any, offset_sec: float, prev_dts: dict[int, int]) -> bool:
    """Rebase packet timestamps from `offset_sec` and drop non-monotonic DTS."""
    shift = int(round(offset_sec / float(pkt.time_base)))
    dts = pkt.dts - shift
    if dts < 0:
        return False
    stream_idx = pkt.stream.index
    prev = prev_dts.get(stream_idx)
    if prev is not None and dts <= prev:
        return False
    prev_dts[stream_idx] = dts
    pkt.dts = dts
    if pkt.pts is not None:
        pkt.pts = max(dts, pkt.pts - shift)
    return True


@dataclass
class _TsSegment:
    """Open single-segment MPEG-TS muxer bound to a remaining byte budget."""

    bio: io.BytesIO
    out: Any
    vs: Any
    as_: Any | None

    @classmethod
    def open(cls, av: Any, vs: Any, as_: Any | None, remaining: int) -> _TsSegment:
        """Open a fresh MPEG-TS muxer enforcing `remaining` bytes."""
        if remaining <= 0:
            raise _SegmentBudgetExceeded("Archive session byte budget exhausted")
        bio = io.BytesIO()
        writer = _LimitedBytesWriter(bio, remaining)
        out = av.open(
            writer,
            mode="w",
            format="mpegts",
            container_options={"mpegts_copyts": "1"},
        )
        ovs = out.add_stream_from_template(vs)
        oas = out.add_stream_from_template(as_) if as_ is not None else None
        return cls(bio=bio, out=out, vs=ovs, as_=oas)

    def close_and_take_bytes(self) -> bytes:
        """Finalize muxer headers/trailers, extract bytes, and close buffer."""
        self.out.close()
        seg_bytes = self.bio.getvalue()
        self.bio.close()
        return seg_bytes

    def discard(self) -> None:
        """Close muxer and buffer while suppressing partial write errors."""
        with contextlib.suppress(Exception):
            self.out.close()
        self.bio.close()


class _FlvTsMuxer:
    """Stateful FLV-to-MPEG-TS keyframe segmenter honoring byte and duration limits."""

    def __init__(
        self,
        *,
        av: Any,
        vs: Any,
        as_: Any | None,
        on_segment: Callable[[float, bytes], bool],
        segment_duration: float,
        max_segment_duration: float,
        max_bytes: int,
    ) -> None:
        self._av = av
        self._vs = vs
        self._as = as_
        self._on_segment = on_segment
        self._segment_duration = segment_duration
        self._max_segment_duration = max_segment_duration
        self._max_bytes = max_bytes
        self._seg: _TsSegment | None = None
        self._published_bytes = 0
        self.emitted = 0
        self._base_sec: float | None = None
        self._seg_start_dts: int | None = None
        self._last_v_dts: int | None = None
        self._last_v_dur = 0
        self._prev_dts: dict[int, int] = {}
        self._aborted = False

    def open_next_segment(self) -> None:
        """Open the next bounded MPEG-TS output segment."""
        self._seg = _TsSegment.open(
            self._av,
            self._vs,
            self._as,
            self._max_bytes - self._published_bytes,
        )

    def discard_current(self) -> None:
        """Discard any open segment after an unhandled exception or budget overrun."""
        if self._seg is not None:
            self._seg.discard()
            self._seg = None

    def abort(self) -> None:
        """Mark the muxer aborted and drop the active segment."""
        self._aborted = True
        self.discard_current()

    def feed(self, pkt: Any) -> bool:
        """Feed one demuxed packet; return True when muxing should stop."""
        if pkt.dts is None:
            return False
        if self._base_sec is None:
            if pkt.stream != self._vs or not pkt.is_keyframe:
                return False
            self._base_sec = float(pkt.dts * self._vs.time_base)
        if pkt.stream == self._vs:
            return self._feed_video(pkt)
        if self._seg is not None and self._seg.as_ is not None:
            self._mux_rebased(pkt, self._seg.as_)
        return False

    def _mux_rebased(self, pkt: Any, target_stream: Any) -> None:
        assert self._base_sec is not None
        assert self._seg is not None
        if not _rebase_packet(pkt, self._base_sec, self._prev_dts):
            return
        pkt.stream = target_stream
        self._seg.out.mux(pkt)

    def _rotate_segment(self, elapsed: float) -> bool:
        assert self._seg is not None
        seg = self._seg
        self._seg = None
        seg_bytes = seg.close_and_take_bytes()
        if seg_bytes:
            if not self._on_segment(elapsed, seg_bytes):
                return False
            self._published_bytes += len(seg_bytes)
            self.emitted += 1
        self.open_next_segment()
        return True

    def _feed_video(self, pkt: Any) -> bool:
        if self._seg_start_dts is None:
            self._seg_start_dts = pkt.dts
        elapsed = float((pkt.dts - self._seg_start_dts) * self._vs.time_base)
        if elapsed > self._max_segment_duration:
            self._aborted = True
            return True
        if pkt.is_keyframe and elapsed >= self._segment_duration:
            if not self._rotate_segment(elapsed):
                self._aborted = True
                return True
            self._seg_start_dts = pkt.dts
        self._last_v_dts = pkt.dts
        if pkt.duration:
            self._last_v_dur = pkt.duration
        assert self._seg is not None
        self._mux_rebased(pkt, self._seg.vs)
        return False

    def finish(self) -> int:
        """Flush and optionally emit the trailing segment, returning emitted count."""
        seg = self._seg
        self._seg = None
        if seg is None:
            return self.emitted
        if self._aborted:
            seg.discard()
            return self.emitted
        seg.out.close()
        try:
            if self._seg_start_dts is not None and self._last_v_dts is not None:
                tail = max(
                    float(
                        ((self._last_v_dts - self._seg_start_dts) + self._last_v_dur)
                        * self._vs.time_base
                    ),
                    0.1,
                )
                if tail <= self._max_segment_duration:
                    tail_bytes = seg.bio.getvalue()
                    if tail_bytes and self._on_segment(tail, tail_bytes):
                        self._published_bytes += len(tail_bytes)
                        self.emitted += 1
        finally:
            seg.bio.close()
        return self.emitted


def _remux_flv_to_mpegts(
    pipe: _BytePipe,
    on_segment: Callable[[float, bytes], bool],
    *,
    segment_duration: float = _SEGMENT_DURATION_SEC,
    max_segment_duration: float = float(_TARGET_DURATION_SEC),
    max_bytes: int = _MAX_SESSION_BYTES,
) -> int:
    """Remux FLV stream from `pipe` into continuous MPEG-TS segments via PyAV.

    Returns total emitted segments; raises if video stream is missing or invalid.
    """
    av = _import_av()
    inp = av.open(pipe, mode="r", format="flv")
    try:
        vs, as_, streams_to_demux = _select_flv_streams(inp)
        muxer = _FlvTsMuxer(
            av=av,
            vs=vs,
            as_=as_,
            on_segment=on_segment,
            segment_duration=segment_duration,
            max_segment_duration=max_segment_duration,
            max_bytes=max_bytes,
        )
        muxer.open_next_segment()
        try:
            for pkt in inp.demux(*streams_to_demux):
                if muxer.feed(pkt):
                    break
        except _SegmentBudgetExceeded:
            muxer.abort()
        except BaseException:
            muxer.discard_current()
            raise
        return muxer.finish()
    finally:
        inp.close()


def render_event_playlist(
    segments: list[tuple[float, bytes]],
    token: str,
    *,
    ended: bool,
    target_duration: int = _TARGET_DURATION_SEC,
) -> str:
    """Render an HLS MPEG-TS EVENT playlist anchored at sequence 0, offset 0."""
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-PLAYLIST-TYPE:EVENT",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-START:TIME-OFFSET=0.000,PRECISE=YES",
        f"#EXT-X-TARGETDURATION:{max(target_duration, 1)}",
    ]
    for idx, (dur, _) in enumerate(segments):
        lines.append(f"#EXTINF:{dur:.3f},")
        lines.append(f"{idx}.ts?t={token}")
    if ended:
        lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


def archive_sessions_by_id(hass: HomeAssistant) -> dict[str, ArchiveHlsSession]:
    return hass.data.setdefault(_ARCHIVE_BY_ID_KEY, {})


def archive_streams(hass: HomeAssistant) -> dict[tuple[str, str, str], Any]:
    return hass.data.setdefault(ARCHIVE_STREAMS_KEY, {})


def _stop_tasks_map(hass: HomeAssistant) -> dict[str, set[asyncio.Task[None]]]:
    return hass.data.setdefault(_ARCHIVE_STOP_TASKS_KEY, {})


def pop_entry_stop_tasks(
    hass: HomeAssistant, entry_id: str
) -> list[asyncio.Task[None]]:
    """Pop and return pending background stop tasks for `entry_id`."""
    stop_tasks: dict[str, set[asyncio.Task[None]]] = (
        hass.data.get(_ARCHIVE_STOP_TASKS_KEY) or {}
    )
    return list(stop_tasks.pop(entry_id, ()))


def pop_entry_sessions_by_id(
    hass: HomeAssistant, entry_id: str
) -> list[ArchiveHlsSession]:
    """Pop and return active archive sessions by ID for `entry_id`."""
    by_id: dict[str, ArchiveHlsSession] = (
        hass.data.get(_ARCHIVE_BY_ID_KEY) or {}
    )
    popped: list[ArchiveHlsSession] = []
    for sid in [sid for sid, sess in by_id.items() if sess.entry_id == entry_id]:
        sess = by_id.pop(sid, None)
        if sess is not None:
            popped.append(sess)
    return popped


class ArchiveHlsSession:
    """One in-progress archive EVENT HLS remux session."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        camera_id: str,
        event_id: str,
        coordinator: Any,
        max_bytes: int = _MAX_SESSION_BYTES,
        max_segments: int = _MAX_SESSION_SEGMENTS,
        target_duration: int = _TARGET_DURATION_SEC,
        idle_timeout: float = _SESSION_IDLE_TIMEOUT_SEC,
    ) -> None:
        self.hass = hass
        self.session_id = secrets.token_urlsafe(16)
        self.entry_id = entry_id
        self.camera_id = camera_id
        self.event_id = event_id
        self.coordinator = coordinator
        self.key = (entry_id, camera_id, event_id)
        self._max_bytes = max_bytes
        self._max_segments = max_segments
        self._target_duration = max(target_duration, 1)
        self._max_segment_duration = float(self._target_duration)
        self._idle_timeout = idle_timeout
        self._segments: list[tuple[float, bytes]] = []
        self._total_bytes = 0
        self.ended = False
        self.failed = False
        self._closed = False
        self.ready_event = asyncio.Event()
        self.fail_event = asyncio.Event()
        self.last_access = time.monotonic()
        self._idle_unsub: CALLBACK_TYPE | None = None
        self._pipe = _BytePipe(hass.loop)
        self._upstream_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._stop_task: asyncio.Task[None] | None = None

    @property
    def alive(self) -> bool:
        return not self._closed and not self.failed

    @property
    def ready(self) -> bool:
        return bool(self._segments) and self.alive

    @property
    def segment_count(self) -> int:
        return len(self._segments)

    def get_segment(self, index: int) -> bytes | None:
        if 0 <= index < len(self._segments):
            return self._segments[index][1]
        return None

    def playlist_url(self, hass: HomeAssistant) -> str:
        token = sign_archive_token(
            hass, self.session_id, self.entry_id, self.camera_id, self.event_id
        )
        return f"/api/elektronny_gorod/archive/{self.session_id}/playlist.m3u8?t={token}"

    def render_playlist(self, token: str) -> str:
        return render_event_playlist(
            self._segments,
            token,
            ended=self.ended,
            target_duration=self._target_duration,
        )

    def touch(self) -> None:
        """Reset inactivity timer on client playback or reuse."""
        if self._closed:
            return
        self.last_access = time.monotonic()
        self._cancel_idle_timer()
        self._idle_unsub = async_call_later(
            self.hass, self._idle_timeout, self._on_idle_timeout
        )

    def _cancel_idle_timer(self) -> None:
        if self._idle_unsub is not None:
            self._idle_unsub()
            self._idle_unsub = None

    @callback
    def _on_idle_timeout(self, _now: Any) -> None:
        self._idle_unsub = None
        if not self._closed:
            stop_archive_session_in_background(self.hass, self)

    def add_segment(self, duration: float, data: bytes) -> bool:
        """Append one MPEG-TS segment without ever removing published ones."""
        if self._closed or self.failed or self.ended:
            return False
        if (
            duration > self._max_segment_duration
            or self._total_bytes + len(data) > self._max_bytes
            or len(self._segments) >= self._max_segments
        ):
            # Cap reached: preserve already-published segments and finalize EVENT.
            if not self._segments:
                self.mark_failed()
            else:
                self.mark_ended()
            return False
        self._segments.append((duration, data))
        self._total_bytes += len(data)
        self.ready_event.set()
        return True

    def mark_ended(self) -> None:
        if self._closed:
            return
        if not self._segments:
            self.mark_failed()
            return
        self.ended = True
        self._stop_upstream_only()

    def mark_failed(self) -> None:
        if not self.failed:
            self.failed = True
            self.fail_event.set()
        self._stop_upstream_only()

    def _stop_upstream_only(self) -> None:
        self._pipe.close()
        current = asyncio.current_task()
        if (
            self._upstream_task is not None
            and not self._upstream_task.done()
            and self._upstream_task is not current
        ):
            self._upstream_task.cancel()

    def start(self, source_url: str) -> None:
        """Start asynchronous HTTP upstream reader and PyAV remux worker."""
        if getattr(self.hass, "is_stopping", False):
            self.mark_failed()
            return
        ensure_archive_stop_listener(self.hass)
        self.touch()
        self._upstream_task = self.hass.async_create_task(
            self._read_upstream(source_url),
            name=f"{DOMAIN}_archive_upstream_{self.camera_id}",
        )
        self._worker_task = self.hass.async_create_task(
            self._run_worker(),
            name=f"{DOMAIN}_archive_worker_{self.camera_id}",
        )

    async def _read_upstream(self, source_url: str) -> None:
        http_session = async_get_clientsession(self.hass)
        try:
            async with http_session.get(
                source_url, timeout=_UPSTREAM_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    LOGGER.debug(
                        "Archive HLS upstream rejected camera_id=%s event_id=%s status=%s",
                        self.camera_id,
                        self.event_id,
                        resp.status,
                    )
                    if not self._segments:
                        self.mark_failed()
                    else:
                        self._pipe.finish()
                    return
                async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                    if not await self._pipe.put(chunk):
                        return
                self._pipe.finish()
        except asyncio.CancelledError:
            self._pipe.close()
            raise
        except (ClientError, ConnectionResetError, TimeoutError, ValueError) as ex:
            LOGGER.debug(
                "Archive HLS upstream error camera_id=%s event_id=%s (%s)",
                self.camera_id,
                self.event_id,
                type(ex).__name__,
            )
            if not self._segments:
                self.mark_failed()
            else:
                self._pipe.finish()

    def _emit_segment_from_worker(self, duration: float, data: bytes) -> bool:
        """Bridge one remuxed MPEG-TS segment onto the HA event loop."""
        if self._closed or self.ended or self.failed:
            return False
        aborted = threading.Event()
        fut = None
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._async_emit(duration, data, aborted),
                self.hass.loop,
            )
            return fut.result(timeout=5.0)
        except (
            RuntimeError,
            TimeoutError,
            concurrent.futures.CancelledError,
        ):
            aborted.set()
            if fut is not None:
                fut.cancel()
            return False

    async def _run_worker(self) -> None:
        def _thread_main() -> int:
            remux_kwargs: dict[str, Any] = {}
            if self._max_bytes != _MAX_SESSION_BYTES:
                remux_kwargs["max_bytes"] = self._max_bytes
            if self._max_segment_duration != float(_TARGET_DURATION_SEC):
                remux_kwargs["max_segment_duration"] = self._max_segment_duration
            return _remux_flv_to_mpegts(
                self._pipe, self._emit_segment_from_worker, **remux_kwargs
            )

        try:
            emitted = await self.hass.async_add_executor_job(_thread_main)
            if self._closed:
                return
            if emitted <= 0 and not self._segments:
                self.mark_failed()
            else:
                self.mark_ended()
        except asyncio.CancelledError:
            self._stop_upstream_only()
            raise
        except Exception as ex:  # noqa: BLE001 - worker boundary
            LOGGER.debug(
                "Archive HLS remux failed camera_id=%s event_id=%s (%s)",
                self.camera_id,
                self.event_id,
                type(ex).__name__,
            )
            if not self._segments:
                self.mark_failed()
            else:
                self.mark_ended()
        finally:
            self._stop_upstream_only()

    async def _async_emit(
        self,
        duration: float,
        data: bytes,
        aborted: threading.Event | None = None,
    ) -> bool:
        if aborted is not None and aborted.is_set():
            return False
        return self.add_segment(duration, data)

    async def _join_tasks(self) -> None:
        tasks = [
            task
            for task in (self._upstream_task, self._worker_task)
            if task is not None and not task.done()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop session idempotently, releasing segments and closing upstream first."""
        if self._stop_task is None:
            self._closed = True
            self._cancel_idle_timer()
            self.fail_event.set()
            self._stop_upstream_only()
            # Releasing published segment bytes before joining tasks avoids
            # retaining multi-megabyte buffers while background tasks unwind;
            # any active ArchiveSegmentView already holds its own chunk ref.
            self._segments.clear()
            self._total_bytes = 0
            if not any(
                task is not None and not task.done()
                for task in (self._upstream_task, self._worker_task)
            ):
                return
            self._stop_task = asyncio.create_task(
                self._join_tasks(),
                name=f"{DOMAIN}_archive_session_stop_{self.camera_id}",
            )
        await asyncio.shield(self._stop_task)


def detach_archive_session(hass: HomeAssistant, session: ArchiveHlsSession) -> None:
    """Remove `session` from lookup maps atomically on the event loop."""
    streams = archive_streams(hass)
    if streams.get(session.key) is session:
        streams.pop(session.key, None)
    by_id = archive_sessions_by_id(hass)
    if by_id.get(session.session_id) is session:
        by_id.pop(session.session_id, None)


def stop_archive_session_in_background(
    hass: HomeAssistant, session: ArchiveHlsSession
) -> asyncio.Task[None]:
    """Detach session and stop it in a tracked per-entry background task."""
    detach_archive_session(hass, session)
    stop_tasks = _stop_tasks_map(hass)
    entry_tasks = stop_tasks.setdefault(session.entry_id, set())

    async def _run_stop() -> None:
        try:
            await session.stop()
        except Exception as ex:  # noqa: BLE001 - background cleanup
            LOGGER.debug(
                "Archive HLS stop failed for entry_id=%s (%s)",
                session.entry_id,
                type(ex).__name__,
            )

    task = hass.async_create_task(
        _run_stop(), name=f"{DOMAIN}_archive_stream_stop"
    )
    if not task.done():
        entry_tasks.add(task)
        task.add_done_callback(entry_tasks.discard)
    return task


def enforce_active_session_limit(hass: HomeAssistant) -> None:
    """Evict least-recently-used sessions if active count hits `_MAX_ACTIVE_SESSIONS`."""
    by_id = archive_sessions_by_id(hass)
    for sid in [sid for sid, sess in by_id.items() if not sess.alive]:
        stop_archive_session_in_background(hass, by_id[sid])
    while len(by_id) >= _MAX_ACTIVE_SESSIONS:
        oldest = min(by_id.values(), key=lambda sess: sess.last_access)
        stop_archive_session_in_background(hass, oldest)


@callback
def ensure_archive_stop_listener(hass: HomeAssistant) -> None:
    """Register one-shot HA shutdown cleanup for all active archive sessions."""
    if hass.data.get(_ARCHIVE_STOP_LISTENER_KEY) is not None:
        return
    bus = getattr(hass, "bus", None)
    if bus is None:
        return

    async def _on_hass_stop(_event: Any) -> None:
        hass.data.pop(_ARCHIVE_STOP_LISTENER_KEY, None)
        await async_stop_all_archive_sessions(hass)

    hass.data[_ARCHIVE_STOP_LISTENER_KEY] = bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _on_hass_stop
    )


@contextlib.contextmanager
def register_archive_in_flight(
    hass: HomeAssistant, entry_id: str, event: asyncio.Event
) -> Iterator[None]:
    """Track an in-flight archive wait event per entry for unload cancellation."""
    in_flight_map: dict[str, set[asyncio.Event]] = hass.data.setdefault(
        ARCHIVE_IN_FLIGHT_KEY, {}
    )
    entry_in_flight = in_flight_map.setdefault(entry_id, set())
    entry_in_flight.add(event)
    try:
        yield
    finally:
        entry_in_flight.discard(event)
        if not entry_in_flight:
            in_flight_map.pop(entry_id, None)


def signal_archive_in_flight(
    hass: HomeAssistant, entry_id: str | None = None
) -> None:
    """Wake in-flight archive resolvers for `entry_id` or across all entries."""
    in_flight: dict[str, set[asyncio.Event]] = (
        hass.data.get(ARCHIVE_IN_FLIGHT_KEY) or {}
    )
    event_sets = (
        (in_flight.get(entry_id, ()),)
        if entry_id is not None
        else in_flight.values()
    )
    for events in event_sets:
        for fail_event in events:
            fail_event.set()


def pop_all_sessions_to_stop(hass: HomeAssistant) -> list[Any]:
    """Detach and collect every registered archive session for HA shutdown."""
    to_stop: list[Any] = []
    streams: dict[tuple[str, str, str], Any] = (
        hass.data.get(ARCHIVE_STREAMS_KEY) or {}
    )
    for key in list(streams):
        session = streams.pop(key, None)
        if session is not None and session not in to_stop:
            to_stop.append(session)
    by_id: dict[str, ArchiveHlsSession] = (
        hass.data.get(_ARCHIVE_BY_ID_KEY) or {}
    )
    for sid in list(by_id):
        session = by_id.pop(sid, None)
        if session is not None and session not in to_stop:
            to_stop.append(session)
    return to_stop


def _pop_all_stop_tasks(hass: HomeAssistant) -> list[asyncio.Task[None]]:
    """Pop all pending background session-stop tasks across entries."""
    stop_tasks: dict[str, set[asyncio.Task[None]]] = (
        hass.data.get(_ARCHIVE_STOP_TASKS_KEY) or {}
    )
    pending: list[asyncio.Task[None]] = []
    for entry_id in list(stop_tasks):
        pending.extend(stop_tasks.pop(entry_id, ()))
    return pending


async def async_stop_all_archive_sessions(hass: HomeAssistant) -> None:
    """Idempotently stop all archive sessions and pending stop tasks on HA shutdown."""
    signal_archive_in_flight(hass)
    to_stop = pop_all_sessions_to_stop(hass)
    for session in to_stop:
        if hasattr(session, "_stop_upstream_only"):
            session._stop_upstream_only()
    if to_stop:
        await asyncio.gather(
            *(session.stop() for session in to_stop),
            return_exceptions=True,
        )

    pending = _pop_all_stop_tasks(hass)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@callback
def async_register_archive_view(hass: HomeAssistant) -> None:
    """Register the archive EVENT HLS views once per HA instance."""
    ensure_archive_stop_listener(hass)
    if hass.data.get(_ARCHIVE_VIEW_REGISTERED) or hass.http is None:
        return
    hass.http.register_view(ArchivePlaylistView())
    hass.http.register_view(ArchiveSegmentView())
    hass.data[_ARCHIVE_VIEW_REGISTERED] = True


class _BaseArchiveView(HomeAssistantView):
    """Shared authorization and idle-refresh logic for archive HLS views."""

    requires_auth = False

    def _authorize(
        self, request: web.Request, session_id: str
    ) -> tuple[ArchiveHlsSession, str] | web.Response:
        hass: HomeAssistant = request.app["hass"]
        session = archive_sessions_by_id(hass).get(session_id)
        if session is None or not session.alive:
            return self.json_message("Unknown media item", 404)
        token = request.query.get("t", "")
        if not verify_archive_token(
            hass,
            token,
            session_id,
            session.entry_id,
            session.camera_id,
            session.event_id,
        ):
            return self.json_message("Invalid or expired archive link", 403)
        if async_get_coordinator(hass, session.entry_id) is not session.coordinator:
            stop_archive_session_in_background(hass, session)
            return self.json_message("Unknown media item", 404)
        session.touch()
        return session, token


class ArchivePlaylistView(_BaseArchiveView):
    """Serve the growing `#EXT-X-PLAYLIST-TYPE:EVENT` playlist."""

    url = "/api/elektronny_gorod/archive/{session_id}/playlist.m3u8"
    name = "api:elektronny_gorod:archive_playlist"

    async def get(
        self, request: web.Request, session_id: str
    ) -> web.StreamResponse:
        auth = self._authorize(request, session_id)
        if isinstance(auth, web.Response):
            return auth
        session, token = auth
        if not session.segment_count:
            return self.json_message("Archive stream is not ready", 404)
        return web.Response(
            text=session.render_playlist(token),
            content_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "private, no-store"},
        )


class ArchiveSegmentView(_BaseArchiveView):
    """Serve one MPEG-TS segment of an active EVENT playlist."""

    url = r"/api/elektronny_gorod/archive/{session_id}/{segment:\d+}.ts"
    name = "api:elektronny_gorod:archive_segment"

    async def get(
        self, request: web.Request, session_id: str, segment: str
    ) -> web.StreamResponse:
        auth = self._authorize(request, session_id)
        if isinstance(auth, web.Response):
            return auth
        session, _token = auth
        if not (segment.isascii() and segment.isdigit()):
            return self.json_message("Unknown media segment", 404)
        data = session.get_segment(int(segment))
        if data is None:
            return self.json_message("Unknown media segment", 404)
        resp = web.StreamResponse(status=200)
        resp.headers["Content-Type"] = "video/mp2t"
        resp.headers["Content-Length"] = str(len(data))
        resp.headers["Cache-Control"] = "private, no-store"
        try:
            await resp.prepare(request)
            await resp.write(data)
        except (ClientError, ConnectionResetError):
            return resp
        return resp
