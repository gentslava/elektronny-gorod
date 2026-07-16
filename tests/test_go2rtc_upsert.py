"""Regression tests for PATCH-only operator-camera writes.

These tests retain the historical A-71/S-A71 security cases while moving the
write boundary from camera.py to `Go2RtcClient`.

Контракт:
- PATCH is the only write verb for `eg_<camera_id>` streams.
- HTTP/client failures never fall back to destructive PUT.
- Sanitized errors contain neither source/body nor underlying exception text.
- ClientTimeout 10s applies to PATCH.

NB: используем прямой mock session.* (не aioresponses) — см. соседний
test_go2rtc_validate.py:module-docstring.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientConnectionError

from custom_components.elektronny_gorod.go2rtc import (
    Go2RtcClient,
    Go2RtcRequestError,
)


# ─── Helpers ────────────────────────────────────────────────────────────


class _AsyncCtxMgr:
    def __init__(self, resp: Any) -> None:
        self._resp = resp

    async def __aenter__(self) -> Any:
        return self._resp

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _make_resp(status: int, text: str = "") -> AsyncMock:
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    return resp


def _make_session(
    *,
    patch_resp: AsyncMock | Exception,
    put_resp: AsyncMock | Exception | None = None,
) -> MagicMock:
    session = MagicMock()
    if isinstance(patch_resp, Exception):
        session.patch = MagicMock(side_effect=patch_resp)
    else:
        session.patch = MagicMock(return_value=_AsyncCtxMgr(patch_resp))

    if put_resp is None:
        session.put = MagicMock()
    elif isinstance(put_resp, Exception):
        session.put = MagicMock(side_effect=put_resp)
    else:
        session.put = MagicMock(return_value=_AsyncCtxMgr(put_resp))
    return session


async def _go2rtc_upsert_stream(
    *,
    session,
    base_url: str,
    stream_name: str,
    src: str,
    headers: dict | None = None,
) -> None:
    """Exercise the production client through the old test call shape."""
    client = Go2RtcClient(
        base_url=base_url,
        rtsp_host="127.0.0.1",
        session=session,
    )
    if headers is not None:
        client._headers = headers
    await client.async_patch_stream(stream_name, src)


# ─── PATCH-first behaviour ──────────────────────────────────────────────


@pytest.mark.parametrize("status", [200, 201, 204])
async def test_upsert_patch_success_skips_put(status: int) -> None:
    """PATCH 2xx → не идёт fallback в PUT (главное свойство A-71 v3.2)."""
    session = _make_session(patch_resp=_make_resp(status))
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y#video=copy",
    )
    assert session.patch.called
    assert not session.put.called


async def test_upsert_patch_sends_name_and_src_in_query() -> None:
    """qs включает `name` + `src`. URL-encoded ffmpeg-source."""
    session = _make_session(patch_resp=_make_resp(200))
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y",
    )
    (url,) = session.patch.call_args.args
    assert url.startswith("http://127.0.0.1:1984/api/streams?")
    assert "name=eg_42" in url
    # src URL-encoded
    assert "src=ffmpeg" in url


async def test_upsert_patch_sends_auth_header_when_provided() -> None:
    session = _make_session(patch_resp=_make_resp(200))
    headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y",
        headers=headers,
    )
    assert session.patch.call_args.kwargs["headers"] == headers


async def test_upsert_patch_sets_client_timeout() -> None:
    """ClientTimeout(total=10) — см. commit bafbbfc."""
    from aiohttp import ClientTimeout

    session = _make_session(patch_resp=_make_resp(200))
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y",
    )
    timeout = session.patch.call_args.kwargs["timeout"]
    assert isinstance(timeout, ClientTimeout)
    assert timeout.total == 10


# ─── No destructive PUT fallback ───────────────────────────────────────


async def test_upsert_patch_4xx_does_not_fall_back_to_put() -> None:
    """PATCH 405 fails safely instead of destroying an existing producer."""
    session = _make_session(
        patch_resp=_make_resp(405), put_resp=_make_resp(200)
    )
    with pytest.raises(Go2RtcRequestError) as caught:
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y",
        )
    assert session.patch.called
    assert not session.put.called
    assert caught.value.category == "http_405"


async def test_upsert_patch_client_error_does_not_fall_back_to_put() -> None:
    session = _make_session(
        patch_resp=ClientConnectionError("boom"),
        put_resp=_make_resp(200),
    )
    with pytest.raises(Go2RtcRequestError):
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y",
        )
    assert not session.put.called


# ─── PATCH failure: token-leak guard (S-A71-01) ────────────────────────


async def test_upsert_patch_4xx_raises_without_body_in_message() -> None:
    """Error must not contain response body or source query token."""
    session = _make_session(
        patch_resp=_make_resp(500), put_resp=_make_resp(403, text="forbidden_token_42")
    )
    with pytest.raises(Go2RtcRequestError) as exc:
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y?token=SECRET",
        )
    msg = str(exc.value)
    assert "http_500" in msg
    assert "forbidden_token_42" not in msg
    assert "SECRET" not in msg


async def test_upsert_patch_client_error_raises_without_exc_details() -> None:
    """ClientError becomes a sanitized category and suppresses its chain.

    S-A71-01: исходный `InvalidURL` etc. может содержать полный URL с токеном —
    `from None` рвёт chain, чтобы traceback оператора не вытащил.
    """
    session = _make_session(
        patch_resp=ClientConnectionError(
            "rtsp://x/y?token=SECRET timeout"
        ),
    )
    with pytest.raises(Go2RtcRequestError) as exc:
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y?token=SECRET",
        )
    msg = str(exc.value)
    assert "client_error" in msg
    assert "SECRET" not in msg
    # exception chain должен быть оборван
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__ is True
