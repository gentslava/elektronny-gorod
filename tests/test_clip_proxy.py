"""Tests for the same-origin clip proxy view and its signed tokens."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.setup import async_setup_component


@pytest.fixture
async def clip_client(hass, hass_client):
    """HTTP test client with the http component set up."""
    assert await async_setup_component(hass, "http", {})
    async_register_clip_view(hass)
    return await hass_client()

from custom_components.elektronny_gorod.api import ForpostDownloadError
from custom_components.elektronny_gorod.clip_proxy import (
    ClipProxyView,
    async_register_clip_view,
    clip_proxy_url,
    sign_clip_token,
    verify_clip_token,
)
from custom_components.elektronny_gorod.const import DOMAIN

_ENTRY_ID = "test-entry"
_EVENT_ID = "3001"
_OPERATOR_URL = "https://savevideo.example/signed-clip.mp4"


def _coordinator(
    download_url: str = _OPERATOR_URL,
    download_error: Exception | None = None,
) -> SimpleNamespace:
    query_download = AsyncMock(return_value=download_url)
    if download_error is not None:
        query_download = AsyncMock(side_effect=download_error)
    return SimpleNamespace(api=SimpleNamespace(query_event_download=query_download))


def _fake_upstream(
    *,
    status: int = 200,
    chunks: tuple[bytes, ...] = (b"mp4", b"data"),
    headers: dict[str, str] | None = None,
) -> MagicMock:
    upstream = MagicMock()
    upstream.status = status
    upstream.headers = headers or {"Content-Length": "7"}

    async def _iter_chunked(_size: int):
        for chunk in chunks:
            yield chunk

    upstream.content.iter_chunked = _iter_chunked
    upstream.close = MagicMock()
    return upstream


def _fake_session(upstream: MagicMock) -> MagicMock:
    session = MagicMock()
    session.get = AsyncMock(return_value=upstream)
    return session


async def test_token_roundtrip_and_rejection(hass) -> None:
    token = sign_clip_token(hass, _ENTRY_ID, _EVENT_ID, now=1000.0)

    assert verify_clip_token(hass, token, _ENTRY_ID, _EVENT_ID, now=1001.0)
    assert not verify_clip_token(hass, token, _ENTRY_ID, "9999", now=1001.0)
    assert not verify_clip_token(hass, "tampered", _ENTRY_ID, _EVENT_ID)
    assert not verify_clip_token(hass, token, _ENTRY_ID, _EVENT_ID, now=1601.0)
    other = sign_clip_token(hass, _ENTRY_ID, _EVENT_ID, now=1000.0)
    assert verify_clip_token(hass, other, _ENTRY_ID, _EVENT_ID, now=1001.0)
    assert not verify_clip_token(hass, "1000000.non-ascii-dаgеst", _ENTRY_ID, _EVENT_ID)


def test_clip_proxy_url_shape(hass) -> None:
    url = clip_proxy_url(hass, _ENTRY_ID, _EVENT_ID)
    assert url.startswith(f"/api/elektronny_gorod/clips/{_ENTRY_ID}/{_EVENT_ID}?t=")
    assert _OPERATOR_URL not in url


async def test_view_streams_clip(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()
    upstream = _fake_upstream()
    session = _fake_session(upstream)

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        resp = await client.get(url)

    assert resp.status == 200
    assert resp.headers["Content-Type"] == "video/mp4"
    assert await resp.read() == b"mp4data"
    session.get.assert_awaited_once_with(_OPERATOR_URL, headers={})
    upstream.close.assert_called_once()


async def test_view_forwards_range(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()
    upstream = _fake_upstream(
        status=206, chunks=(b"mp4",), headers={"Content-Range": "bytes 0-2/7"}
    )
    session = _fake_session(upstream)

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        resp = await client.get(url, headers={"Range": "bytes=0-2"})

    assert resp.status == 206
    assert resp.headers["Content-Range"] == "bytes 0-2/7"
    session.get.assert_awaited_once_with(
        _OPERATOR_URL, headers={"Range": "bytes=0-2"}
    )


async def test_view_rejects_bad_token_and_unknown_entry(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    client = clip_client

    resp = await client.get(
        f"/api/elektronny_gorod/clips/{entry.entry_id}/{_EVENT_ID}?t=bad"
    )
    assert resp.status == 403

    valid_unknown = clip_proxy_url(hass, "no-such-entry", _EVENT_ID)
    resp = await client.get(valid_unknown)
    assert resp.status == 404


async def test_view_maps_download_errors(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    client_coordinator = _coordinator(
        download_error=ForpostDownloadError("102")
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client_coordinator

    client = clip_client

    resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))
    assert resp.status == 503

    client_coordinator.api.query_event_download = AsyncMock(
        side_effect=ForpostDownloadError(None)
    )
    resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))
    assert resp.status == 404

    client_coordinator.api.query_event_download = AsyncMock(
        side_effect=RuntimeError("operator down")
    )
    resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))
    assert resp.status == 502


async def test_view_upstream_failure_is_502(hass, clip_client) -> None:
    from aiohttp import ClientError

    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()
    session = MagicMock()
    session.get = AsyncMock(side_effect=ClientError("boom"))

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 502


async def test_view_rejects_non_ascii_token_without_500(
    hass, clip_client
) -> None:
    """Security I-1: non-ASCII digest must 403, not TypeError-500."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    client = clip_client
    resp = await client.get(
        f"/api/elektronny_gorod/clips/{entry.entry_id}/{_EVENT_ID}"
        "?t=9999999999.dаgеst"
    )
    assert resp.status == 403


async def test_view_clamps_bad_upstream_status(hass, clip_client) -> None:
    """M-5: non-2xx upstream (e.g. expired link) maps to 502, not passthrough."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    upstream = _fake_upstream(status=403, chunks=(b"",))
    session = _fake_session(upstream)
    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))
    assert resp.status == 502


async def test_register_is_idempotent(hass) -> None:
    hass.http = MagicMock()
    async_register_clip_view(hass)
    async_register_clip_view(hass)
    assert hass.http.register_view.call_count == 1


def _fake_locked_upstream():
    locked = _fake_upstream(status=423, chunks=(b"",))
    return locked


async def test_view_polls_storage_until_clip_ready(hass, clip_client) -> None:
    """Storage host also gates the file with 423 until rendering finishes.

    Contract mirrors the mobile app: mint ONCE, poll the SAME link with
    plain GETs (no Range) until the gate clears.
    """
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    coordinator = _coordinator()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    ready = _fake_upstream(chunks=(b"mp4", b"data"))
    session = MagicMock()
    session.get = AsyncMock(side_effect=[_fake_locked_upstream(), ready])

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_INTERVAL",
        0.01,
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 200
    assert await resp.read() == b"mp4data"
    assert coordinator.api.query_event_download.await_count == 1
    assert session.get.await_count == 2
    session.get.assert_any_await(_OPERATOR_URL, headers={})


async def test_view_range_rides_poll_single_fetch(hass, clip_client) -> None:
    """Signed link is single-use: Range rides the poll; first success streams.

    A second fetch after a successful GET would 404 (one-time token), so the
    poll must carry the client Range and stream the first 200/206 directly.
    """
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    coordinator = _coordinator()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    ranged = _fake_upstream(
        status=206, chunks=(b"mp4",), headers={"Content-Range": "bytes 0-2/7"}
    )
    session = MagicMock()
    session.get = AsyncMock(side_effect=[_fake_locked_upstream(), ranged])

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_INTERVAL",
        0.01,
    ):
        client = clip_client
        resp = await client.get(
            clip_proxy_url(hass, entry.entry_id, _EVENT_ID),
            headers={"Range": "bytes=0-2"},
        )

    assert resp.status == 206
    assert resp.headers["Content-Range"] == "bytes 0-2/7"
    assert session.get.await_count == 2
    for call in session.get.await_args_list:
        assert call.kwargs["headers"] == {"Range": "bytes=0-2"}


async def test_view_storage_prepare_timeout_is_503(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    session = MagicMock()
    session.get = AsyncMock(return_value=_fake_locked_upstream())

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_INTERVAL",
        0.01,
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BUDGET",
        0.05,
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 503
    assert session.get.await_count >= 2
