"""Unit tests для `_go2rtc_upsert_stream` (camera.py).

Закрывают G-9: PATCH-first / PUT-fallback контракт (commit 93a47a8,
A-71 v3.2) и S-A71-01 token-leak guard (commit 90cdbbc) до сих пор
тестировались только через camera-level integration. Direct unit-тесты
фиксируют контракт против go2rtc API.

Контракт:
- PATCH идёт ПЕРВЫМ (idempotent на existing stream, не убивает producer).
- PUT идёт fallback'ом только если PATCH вернул 4xx/5xx или ClientError.
- При PUT failure — `RuntimeError` БЕЗ исходного exception body
  (через `from None`) — guard против leak оператор-токена в traceback.
- ClientTimeout 10s применяется к обоим запросам.

NB: используем прямой mock session.* (не aioresponses) — см. соседний
test_go2rtc_validate.py:module-docstring.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientConnectionError

from custom_components.elektronny_gorod.camera import _go2rtc_upsert_stream


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


# ─── PUT fallback ───────────────────────────────────────────────────────


async def test_upsert_patch_4xx_falls_back_to_put() -> None:
    """PATCH 405/404 (старая go2rtc без PATCH-support) → PUT."""
    session = _make_session(
        patch_resp=_make_resp(405), put_resp=_make_resp(200)
    )
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y",
    )
    assert session.patch.called
    assert session.put.called


async def test_upsert_patch_client_error_falls_back_to_put() -> None:
    session = _make_session(
        patch_resp=ClientConnectionError("boom"),
        put_resp=_make_resp(200),
    )
    await _go2rtc_upsert_stream(
        session=session,
        base_url="http://127.0.0.1:1984",
        stream_name="eg_42",
        src="ffmpeg:rtsp://x/y",
    )
    assert session.put.called


# ─── PUT failure: token-leak guard (S-A71-01) ───────────────────────────


async def test_upsert_put_4xx_raises_without_body_in_message() -> None:
    """RuntimeError НЕ должен содержать response body (может echo'нуть src=<token>)."""
    session = _make_session(
        patch_resp=_make_resp(500), put_resp=_make_resp(403, text="forbidden_token_42")
    )
    with pytest.raises(RuntimeError) as exc:
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y?token=SECRET",
        )
    msg = str(exc.value)
    assert "HTTP 403" in msg
    assert "forbidden_token_42" not in msg
    assert "SECRET" not in msg


async def test_upsert_put_client_error_raises_without_exc_details() -> None:
    """ClientError из PUT → RuntimeError с type name только, exception chain оборван.

    S-A71-01: исходный `InvalidURL` etc. может содержать полный URL с токеном —
    `from None` рвёт chain, чтобы traceback оператора не вытащил.
    """
    session = _make_session(
        patch_resp=_make_resp(500),
        put_resp=ClientConnectionError("rtsp://x/y?token=SECRET timeout"),
    )
    with pytest.raises(RuntimeError) as exc:
        await _go2rtc_upsert_stream(
            session=session,
            base_url="http://127.0.0.1:1984",
            stream_name="eg_42",
            src="ffmpeg:rtsp://x/y?token=SECRET",
        )
    msg = str(exc.value)
    assert "ClientConnectionError" in msg
    assert "SECRET" not in msg
    # exception chain должен быть оборван
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__ is True
