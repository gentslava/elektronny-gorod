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
    upstream.read = AsyncMock(return_value=b"".join(chunks))
    upstream.close = MagicMock()
    upstream.release = MagicMock()
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
    # Без Accept-Ranges Chromium помечает источник потоковым и гасит seek.
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Length"] == "7"
    assert await resp.read() == b"mp4data"
    assert session.get.await_args.args == (_OPERATOR_URL,)
    assert session.get.await_count == 1
    upstream.close.assert_called_once()


async def test_view_serves_range_itself(hass, clip_client) -> None:
    """Диапазоны нарезаем сами: оператор Accept-Ranges не анонсирует.

    Приложение Range наверх не шлёт вовсе (снимок 2026-05-25), а storage в
    успешном ответе не отдаёт ни Accept-Ranges, ни ETag.
    """
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
        resp = await client.get(url, headers={"Range": "bytes=0-2"})

    assert resp.status == 206
    assert resp.headers["Content-Range"] == "bytes 0-2/7"
    assert resp.headers["Content-Length"] == "3"
    assert await resp.read() == b"mp4"
    # Range наверх не уходит — оператор его не поддерживает.
    assert session.get.await_args.args == (_OPERATOR_URL,)
    assert "headers" not in session.get.await_args.kwargs
    assert session.get.await_count == 1


async def test_view_range_suffix_and_unsatisfiable(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=_fake_session(_fake_upstream()),
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        suffix = await client.get(url, headers={"Range": "bytes=-4"})
        beyond = await client.get(url, headers={"Range": "bytes=99-"})

    assert suffix.status == 206
    assert suffix.headers["Content-Range"] == "bytes 3-6/7"
    assert await suffix.read() == b"data"
    assert beyond.status == 416
    assert beyond.headers["Content-Range"] == "bytes */7"


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

    # Бюджет ожидания сжимаем: иначе тест честно спит все 30 секунд реального
    # времени, ожидая, пока mint-гейт исчерпает поллинг.
    with patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BACKOFF",
        (0.01,),
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BUDGET",
        0.05,
    ):
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
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BACKOFF",
        (0.01,),
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 200
    assert await resp.read() == b"mp4data"
    assert coordinator.api.query_event_download.await_count == 1
    assert session.get.await_count == 2
    assert session.get.await_args.args == (_OPERATOR_URL,)


async def test_clip_is_fetched_once_and_reused(hass, clip_client) -> None:
    """Перемотка обслуживается из кеша, а не новым минтом.

    Каждый минт запускает подготовку mp4 заново, поэтому повторные запросы
    браузера (в том числе seek) не должны доходить до оператора.
    """
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    coordinator = _coordinator()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    session = _fake_session(_fake_upstream())

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        first = await client.get(url)
        seek = await client.get(url, headers={"Range": "bytes=3-6"})

    assert first.status == 200
    assert seek.status == 206
    assert await seek.read() == b"data"
    assert coordinator.api.query_event_download.await_count == 1
    assert session.get.await_count == 1


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
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BACKOFF",
        (0.01,),
    ), patch(
        "custom_components.elektronny_gorod.clip_proxy._DOWNLOAD_PREPARE_BUDGET",
        0.05,
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 503
    assert session.get.await_count >= 2


async def test_cache_is_scoped_per_entry(hass, clip_client) -> None:
    """Регрессия: кеш ключевался только по event_id.

    Один и тот же event_id у двух аккаунтов отдавал бы клип чужого entry.
    """
    from custom_components.elektronny_gorod.clip_proxy import _cache_get, _cache_put

    _cache_put(hass, "entry-a", _EVENT_ID, b"aaa")
    _cache_put(hass, "entry-b", _EVENT_ID, b"bbb")

    assert _cache_get(hass, "entry-a", _EVENT_ID).data == b"aaa"
    assert _cache_get(hass, "entry-b", _EVENT_ID).data == b"bbb"


async def test_cache_expiry_and_eviction(hass) -> None:
    from custom_components.elektronny_gorod import clip_proxy

    clip = clip_proxy._cache_put(hass, _ENTRY_ID, "1", b"x")
    clip.created -= clip_proxy._CACHE_TTL + 1
    assert clip_proxy._cache_get(hass, _ENTRY_ID, "1") is None

    with patch.object(clip_proxy, "_CACHE_MAX_BYTES", 4):
        clip_proxy._cache_put(hass, _ENTRY_ID, "2", b"aa")
        clip_proxy._cache_put(hass, _ENTRY_ID, "3", b"bb")
        clip_proxy._cache_put(hass, _ENTRY_ID, "4", b"cc")
        # Самый старый вытеснен, бюджет соблюдён.
        assert clip_proxy._cache_get(hass, _ENTRY_ID, "2") is None
        assert clip_proxy._cache_get(hass, _ENTRY_ID, "4") is not None

    # Клип крупнее всего бюджета не кешируется вовсе.
    with patch.object(clip_proxy, "_CACHE_MAX_BYTES", 2):
        clip_proxy._cache_put(hass, _ENTRY_ID, "5", b"toolong")
        assert clip_proxy._cache_get(hass, _ENTRY_ID, "5") is None


async def test_release_clip_cache_drops_only_its_entry(hass) -> None:
    from custom_components.elektronny_gorod.clip_proxy import (
        _cache_get,
        _cache_put,
        async_release_clip_cache,
    )

    _cache_put(hass, "entry-a", _EVENT_ID, b"aaa")
    _cache_put(hass, "entry-b", _EVENT_ID, b"bbb")

    async_release_clip_cache(hass, "entry-a")

    assert _cache_get(hass, "entry-a", _EVENT_ID) is None
    assert _cache_get(hass, "entry-b", _EVENT_ID) is not None


def test_parse_range_follows_rfc9110() -> None:
    from custom_components.elektronny_gorod.clip_proxy import (
        _RANGE_IGNORE,
        _RANGE_UNSATISFIABLE,
        _parse_range,
    )

    assert _parse_range("bytes=0-2", 7) == (0, 2)
    assert _parse_range("BYTES=0-2", 7) == (0, 2)  # единица регистронезависима
    assert _parse_range("bytes=-4", 7) == (3, 6)
    assert _parse_range("bytes=0-999", 7) == (0, 6)
    # Неразбираемое игнорируется (200), а не превращается в 416.
    assert _parse_range("bytes=abc", 7) == _RANGE_IGNORE
    assert _parse_range("items=0-1", 7) == _RANGE_IGNORE
    assert _parse_range("bytes=0-1,5-6", 7) == _RANGE_IGNORE
    # Синтаксис верен, диапазон недостижим.
    assert _parse_range("bytes=9-", 7) == _RANGE_UNSATISFIABLE
    assert _parse_range("bytes=5-2", 7) == _RANGE_UNSATISFIABLE


async def test_view_ignores_malformed_range(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=_fake_session(_fake_upstream()),
    ):
        client = clip_client
        resp = await client.get(
            clip_proxy_url(hass, entry.entry_id, _EVENT_ID),
            headers={"Range": "bytes=abc"},
        )

    assert resp.status == 200
    assert await resp.read() == b"mp4data"


async def test_view_refuses_empty_body(hass, clip_client) -> None:
    """Пустое тело нельзя закешировать: оно отравило бы клип на весь TTL."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=_fake_session(_fake_upstream(chunks=())),
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        first = await client.get(url)
        second = await client.get(url)

    assert first.status == 502
    assert second.status == 502


async def test_view_refuses_oversized_clip(hass, clip_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()
    upstream = _fake_upstream(headers={"Content-Length": "999999999"})

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=_fake_session(upstream),
    ):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 502


async def test_view_aborts_oversized_stream(hass, clip_client) -> None:
    """Лимит держится и когда upstream не объявил длину заранее."""
    from custom_components.elektronny_gorod import clip_proxy

    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _coordinator()
    upstream = _fake_upstream(chunks=(b"aaaa", b"bbbb"), headers={})

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=_fake_session(upstream),
    ), patch.object(clip_proxy, "_CLIP_MAX_BYTES", 5):
        client = clip_client
        resp = await client.get(clip_proxy_url(hass, entry.entry_id, _EVENT_ID))

    assert resp.status == 502
    # Ничего не закешировано — повтор снова пойдёт к оператору.
    assert clip_proxy._cache_get(hass, entry.entry_id, _EVENT_ID) is None


async def test_parallel_requests_mint_once(hass, clip_client) -> None:
    """Центральный инвариант: одновременные запросы дают один минт.

    Браузер на старте шлёт несколько range-запросов сразу; без лока каждый
    из них запускал бы у оператора отдельную подготовку файла.
    """
    import asyncio

    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    coordinator = _coordinator()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entered = asyncio.Event()
    gate = asyncio.Event()
    upstream = _fake_upstream()

    async def _slow_get(*args, **kwargs):
        entered.set()
        await gate.wait()
        return upstream

    session = MagicMock()
    session.get = AsyncMock(side_effect=_slow_get)

    with patch(
        "custom_components.elektronny_gorod.clip_proxy.async_get_clientsession",
        return_value=session,
    ):
        client = clip_client
        url = clip_proxy_url(hass, entry.entry_id, _EVENT_ID)
        first = asyncio.create_task(client.get(url))
        second = asyncio.create_task(client.get(url, headers={"Range": "bytes=0-2"}))
        # Дожидаемся, что первый действительно внутри загрузки, и только потом
        # даём второму дойти до лока — иначе он успел бы обслужиться кешем и
        # тест был бы зелёным даже без лока.
        await asyncio.wait_for(entered.wait(), 1)
        for _ in range(10):
            await asyncio.sleep(0)
        assert session.get.await_count == 1
        gate.set()
        responses = await asyncio.gather(first, second)

    assert {resp.status for resp in responses} == {200, 206}
    assert coordinator.api.query_event_download.await_count == 1
    assert session.get.await_count == 1
