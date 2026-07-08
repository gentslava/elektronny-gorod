"""Tests for HTTP client behavior — security-critical:
- Bearer не отправляется на pre-auth endpoints.
- Error log не утекает PII (phone/contract/account id в auth URL).
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.http import HTTP


class _FakeResponse:
    """Минимальный stub aiohttp ClientResponse для тестов."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.ok = 200 <= status < 300
        self.reason = "OK" if self.ok else "Error"
        self.headers: dict = {}
        self.method = "GET"
        self.url = "https://example/"


@pytest.fixture
def fake_session() -> MagicMock:
    """Подмена aiohttp session — захватывает headers для assert'ов."""
    session = MagicMock()
    session.get = AsyncMock(return_value=_FakeResponse(200))
    session.post = AsyncMock(return_value=_FakeResponse(200))
    return session


@pytest.fixture
def http_client(hass, fake_session, monkeypatch):
    """HTTP client с подменённой aiohttp-сессией HA."""
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.http.async_get_clientsession",
        lambda _hass: fake_session,
    )
    ua = MagicMock()
    ua.__str__ = lambda self: "test-ua"
    return HTTP(
        hass=hass,
        user_agent=ua,
        access_token="EXPIRED_BEARER_TOKEN",
        refresh_token=None,
        operator="1",
    )


async def test_bearer_omitted_on_preauth_login(http_client, fake_session):
    """Pre-auth /auth/v2/login/{phone} не должен получать Authorization header,
    даже если access_token присутствует. Иначе backend видит expired Bearer
    и отдаёт 401 — блокируя reauth flow."""
    await http_client.get("/auth/v2/login/1131686")

    fake_session.get.assert_awaited_once()
    sent_headers = fake_session.get.await_args.kwargs["headers"]
    assert "authorization" not in {k.lower() for k in sent_headers}


async def test_bearer_omitted_on_preauth_password(http_client, fake_session):
    """Pre-auth /auth/v2/auth/{phone}/password — то же, без Bearer."""
    await http_client.post("/auth/v2/auth/1131686/password", '{"login": "x"}')

    fake_session.post.assert_awaited_once()
    sent_headers = fake_session.post.await_args.kwargs["headers"]
    assert "authorization" not in {k.lower() for k in sent_headers}


async def test_bearer_sent_on_post_auth_endpoint(http_client, fake_session):
    """На post-auth endpoint Bearer должен быть отправлен."""
    await http_client.get("/rest/v1/places/12345/accesscontrols")

    sent_headers = fake_session.get.await_args.kwargs["headers"]
    assert sent_headers.get("authorization") == "Bearer EXPIRED_BEARER_TOKEN"


async def test_bearer_does_not_leak_across_requests(http_client, fake_session):
    """Регрессия: после post-auth запроса (где Authorization добавлен)
    следующий pre-auth запрос НЕ должен унаследовать Authorization.
    Корень bug'а — общий self._headers между запросами."""
    # Запрос #1 — post-auth, Bearer должен быть.
    await http_client.get("/rest/v1/places/12345/accesscontrols")
    first_headers = fake_session.get.await_args.kwargs["headers"]
    assert "authorization" in first_headers

    # Запрос #2 — pre-auth, Bearer НЕ должен утечь.
    await http_client.get("/auth/v2/login/1131686")
    second_headers = fake_session.get.await_args.kwargs["headers"]
    assert "authorization" not in {k.lower() for k in second_headers}


async def test_error_log_redacts_phone_in_auth_path(http_client, fake_session, caplog):
    """API request failed log не должен содержать PII из auth URL."""
    fake_session.get = AsyncMock(return_value=_FakeResponse(401))

    with caplog.at_level(logging.ERROR, logger="custom_components.elektronny_gorod.const"):
        with pytest.raises(Exception):
            await http_client.get("/auth/v2/login/1131686")

    assert "1131686" not in caplog.text
    assert "/auth/v2/login/***" in caplog.text


async def test_error_log_passes_through_non_auth_path(http_client, fake_session, caplog):
    """Для не-auth endpoint path логируется как есть (place_id и т.д. — не PII)."""
    fake_session.get = AsyncMock(return_value=_FakeResponse(500))

    with caplog.at_level(logging.ERROR, logger="custom_components.elektronny_gorod.const"):
        with pytest.raises(Exception):
            await http_client.get("/rest/v1/places/12345/accesscontrols")

    assert "/rest/v1/places/12345/accesscontrols" in caplog.text


# --- A-21: explicit ClientTimeout on operator API -------------------------- #


async def test_rest_get_uses_rest_timeout(http_client, fake_session):
    """GET (JSON) идёт с REST-таймаутом (total=30, connect=10), не с aiohttp-дефолтом."""
    from custom_components.elektronny_gorod.http import _REST_TIMEOUT

    await http_client.get("/rest/v1/places/12345/accesscontrols")

    timeout = fake_session.get.await_args.kwargs["timeout"]
    assert timeout is _REST_TIMEOUT
    assert timeout.total == 30
    assert timeout.connect == 10


async def test_post_uses_rest_timeout(http_client, fake_session):
    """POST также получает REST-таймаут."""
    from custom_components.elektronny_gorod.http import _REST_TIMEOUT

    await http_client.post("/rest/v1/something", '{"x": 1}')

    assert fake_session.post.await_args.kwargs["timeout"] is _REST_TIMEOUT


async def test_delete_uses_rest_timeout(http_client, fake_session):
    """DELETE получает REST-таймаут."""
    from custom_components.elektronny_gorod.http import _REST_TIMEOUT

    fake_session.delete = AsyncMock(return_value=_FakeResponse(200))
    await http_client.delete("/rest/v1/something", '{"x": 1}')

    assert fake_session.delete.await_args.kwargs["timeout"] is _REST_TIMEOUT


async def test_binary_get_uses_binary_timeout(http_client, fake_session):
    """Binary-чтение (snapshot JPEG) идёт с более щедрым binary-таймаутом (total=60)."""
    from custom_components.elektronny_gorod.http import _BINARY_TIMEOUT

    resp = MagicMock()
    resp.read = AsyncMock(return_value=b"jpeg-bytes")
    fake_session.get = AsyncMock(return_value=resp)

    result = await http_client.get("/rest/v1/cameras/1/snapshot", binary=True)

    assert result == b"jpeg-bytes"
    timeout = fake_session.get.await_args.kwargs["timeout"]
    assert timeout is _BINARY_TIMEOUT
    assert timeout.total == 60
