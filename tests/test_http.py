"""Tests for HTTP client behavior — security-critical:
- Bearer не отправляется на pre-auth endpoints.
- Error log не утекает PII (phone/contract/account id в auth URL).
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.http import (
    HTTP,
    ServicePipeBlockError,
    error_status,
    is_service_pipe_block,
    redact_request_id,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _FakeResponse:
    """Минимальный stub aiohttp ClientResponse для тестов.

    `url` — зеркало запрошенного, а не константа: иначе ветка auth-пути в
    `_log_response` не исполняется ни разу, и редакция телефона в ней не
    держится ничем. Именно эта строка пишется на КАЖДОМ auth-запросе,
    включая успешный вход, — в отличие от строки отказа.
    """

    def __init__(self, status: int, url: str = "https://example/") -> None:
        self.status = status
        self.ok = 200 <= status < 300
        self.reason = "OK" if self.ok else "Error"
        self.headers: dict = {}
        self.method = "GET"
        self.url = url


def _responder(status: int):
    """Ответчик, чей `url` — зеркало запрошенного.

    Константный URL в дублёре прятал от тестов ветку auth-пути в
    `_log_response`: она не исполнялась ни разу, и редакция телефона в ней
    не держалась ничем.
    """

    async def _call(url, **_kwargs):
        return _FakeResponse(status, url)

    return _call


@pytest.fixture
def fake_session() -> MagicMock:
    """Подмена aiohttp session — захватывает headers для assert'ов."""
    session = MagicMock()
    session.get = AsyncMock(side_effect=_responder(200))
    session.post = AsyncMock(side_effect=_responder(200))
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


async def test_bearer_omitted_on_public_device_installation(http_client, fake_session):
    """Public bootstrap 9.9.0 вызывается до auth и не получает Bearer."""
    await http_client.post(
        "/api/mh-customer-device/mobile/public/v1/customers/device-installations",
        '{"appVersion": "9.9.0"}',
    )

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
    """Лог отказа не должен содержать PII из auth URL.

    Уровень — `debug`: транспорт не решает, значим ли отказ (см. тест про
    устойчивый отказ ниже). Редакция телефона от уровня не зависит и нужна
    тем более: именно debug-логи люди прикладывают к issue.
    """
    fake_session.get = AsyncMock(side_effect=_responder(401))

    with caplog.at_level(logging.DEBUG, logger="custom_components.elektronny_gorod.const"):
        with pytest.raises(Exception):
            await http_client.get("/auth/v2/login/1131686")

    assert "1131686" not in caplog.text
    assert "/auth/v2/login/***" in caplog.text


async def test_error_log_passes_through_non_auth_path(http_client, fake_session, caplog):
    """Для не-auth endpoint path логируется как есть (place_id и т.д. — не PII)."""
    fake_session.get = AsyncMock(side_effect=_responder(500))

    with caplog.at_level(logging.DEBUG, logger="custom_components.elektronny_gorod.const"):
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


async def test_post_without_body_sends_no_content_type(http_client, fake_session):
    """POST без тела уходит без `content-type`, как у приложения.

    Retrofit для POST без `@Body` шлёт пустое тело и тип не объявляет — в
    HAR у `guests/link` нет `Content-Type`, `Content-Length: 0`.
    Объявлять JSON при пустом теле — заголовок, которого приложение не
    шлёт (ADR-0006).
    """
    await http_client.post("/api/mh-auth/mobile/v1/guests/link?placeId=1&app=2", None)

    sent = fake_session.post.await_args.kwargs
    assert sent["data"] is None
    assert "content-type" not in {k.lower() for k in sent["headers"]}


async def test_post_with_body_declares_json(http_client, fake_session):
    """POST с телом по-прежнему объявляет JSON — граница предыдущего теста."""
    await http_client.post("/rest/v1/something", '{"x": 1}')

    sent_headers = fake_session.post.await_args.kwargs["headers"]
    assert sent_headers["content-type"] == "application/json; charset=UTF-8"


async def test_delete_with_body_declares_json(http_client, fake_session):
    """DELETE с телом объявляет JSON — мирроринг отписки push."""
    fake_session.delete = AsyncMock(return_value=_FakeResponse(200))
    await http_client.delete("/rest/v1/something", '{"x": 1}')

    sent_headers = fake_session.delete.await_args.kwargs["headers"]
    assert sent_headers["content-type"] == "application/json; charset=UTF-8"


async def test_delete_without_body_sends_no_content_type(http_client, fake_session):
    """DELETE без тела типа не объявляет — граница предыдущего теста."""
    fake_session.delete = AsyncMock(return_value=_FakeResponse(200))
    await http_client.delete("/rest/v1/something")

    sent_headers = fake_session.delete.await_args.kwargs["headers"]
    assert "content-type" not in {k.lower() for k in sent_headers}


async def test_delete_uses_rest_timeout(http_client, fake_session):
    """DELETE получает REST-таймаут."""
    from custom_components.elektronny_gorod.http import _REST_TIMEOUT

    fake_session.delete = AsyncMock(return_value=_FakeResponse(200))
    await http_client.delete("/rest/v1/something", '{"x": 1}')

    assert fake_session.delete.await_args.kwargs["timeout"] is _REST_TIMEOUT


async def test_binary_error_body_is_not_returned_as_data(http_client, fake_session):
    """Тело ошибки оператора не уходит вызывающему как «данные».

    Бинарный путь возвращал содержимое любого ответа. На `531`/`500` это были
    непустые байты JSON-ошибки, и потребитель снимка принимал их за кадр.
    """
    resp = _FakeResponse(531)
    resp.read = AsyncMock(return_value=b'{"error":"camera busy"}')
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ClientError):
        await http_client.get("/rest/v1/cameras/1/snapshot", binary=True)


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


async def test_non_auth_response_is_logged_with_its_status(
    http_client, fake_session, caplog
) -> None:
    """Обычный ответ логируется статусом, без тела и заголовков."""
    import logging

    fake_session.get = AsyncMock(return_value=_FakeResponse(200))

    with caplog.at_level(logging.DEBUG):
        await http_client.get("/rest/v1/places")

    assert any("Response" in r.msg for r in caplog.records)


async def test_post_body_size_is_logged_not_the_body(
    http_client, fake_session, caplog
) -> None:
    """В журнал уходит размер тела, а не само тело.

    В теле лежат пароль и код из SMS — писать его нельзя даже на отладке.
    """
    import logging

    fake_session.post = AsyncMock(return_value=_FakeResponse(200))

    with caplog.at_level(logging.DEBUG):
        await http_client.post("/auth/v2/auth/x/password", '{"hash1": "СЕКРЕТ"}')

    assert not any("СЕКРЕТ" in str(r.msg) % (r.args or ()) for r in caplog.records)


async def test_auth_response_is_logged_without_its_size(
    http_client, fake_session, caplog
) -> None:
    """У ответа на вход не логируется даже размер.

    По размеру видно, чем кончилась попытка входа: успех и отказ различаются
    длиной тела.
    """
    import logging

    fake_session.post = AsyncMock(return_value=_FakeResponse(200))

    with caplog.at_level(logging.DEBUG):
        await http_client.post("/auth/v2/auth/x/password", "{}")

    responses = [r for r in caplog.records if "Response" in str(r.msg)]
    assert responses, "ответ должен попасть в журнал"
    assert not any("Content-Length" in str(r.msg) for r in responses)


async def test_binary_body_size_is_measured_without_decoding(
    http_client, fake_session, caplog
) -> None:
    """Двоичное тело измеряется как есть, без попытки его прочитать текстом."""
    import logging

    fake_session.post = AsyncMock(return_value=_FakeResponse(200))

    with caplog.at_level(logging.DEBUG):
        await http_client.post("/rest/v1/upload", b"\xff\xd8\x00\x01")

    assert any("Request" in str(r.msg) for r in caplog.records)


async def test_persistent_rest_failure_is_not_shouted_on_every_response(
    http_client, fake_session, caplog
) -> None:
    """Устойчивый отказ REST не даёт по громкой строке на каждый ответ.

    Транспорт не знает, значим ли отказ: решает вызывающий — координатор
    ограничивает жалобу по фронту, config flow показывает причину в форме.
    На `error` эта строка сводила дедупликацию на нет: при отказе оператора
    набегало под три сотни одинаковых записей в сутки на каждый endpoint,
    против правила Silver `log-when-unavailable`.
    """
    import logging

    fake_session.get = AsyncMock(side_effect=_responder(503))

    with caplog.at_level(logging.DEBUG):
        for _ in range(12):
            with pytest.raises(ClientError):
                await http_client.get("/rest/v1/subscriber-places")

    ours = [
        r for r in caplog.records
        if r.name.startswith("custom_components.elektronny_gorod")
        and "API request failed" in r.msg
    ]
    assert [r for r in ours if r.levelno >= logging.WARNING] == [], (
        "об отказе решает вызывающий, а не транспорт"
    )
    assert len(ours) == 12, "на debug отказ виден — иначе диагностировать нечем"


# --- A-92: ServicePipe / WAF block detection ------------------------------- #


def _html_response(
    status: int,
    body: bytes | str,
    *,
    url: str = "https://example/rest/v3/subscriber-places",
    headers: dict[str, str] | None = None,
    use_text: bool = False,
) -> MagicMock:
    resp = MagicMock(spec=ClientResponse)
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.reason = "OK" if resp.ok else "Forbidden"
    resp.method = "GET"
    resp.url = url
    resp.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    if use_text:
        text_val = body.decode("utf-8") if isinstance(body, bytes) else body
        resp.text = AsyncMock(return_value=text_val)
    else:
        raw_val = body.encode("utf-8") if isinstance(body, str) else body
        resp.read = AsyncMock(return_value=raw_val)
    return resp


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("<!@#>", None),
        ("short", "***"),
        ("12345678", "***"),
        ("13005083566:3", "1300...66:3"),
        ("sp-req-1234567890ab", "sp-r...90ab"),
        ("***", "***"),
    ],
)
def test_redact_request_id(raw: str | None, expected: str | None) -> None:
    """Correlation ID редачится детерминированно без потери короткого суффикса."""
    assert redact_request_id(raw) == expected


@pytest.mark.parametrize(
    ("fixture_name", "status", "headers", "expected_id"),
    [
        (
            "servicepipe_shape1.html",
            403,
            {"Content-Type": "text/html; charset=utf-8"},
            "sp-r...90ab",
        ),
        (
            "servicepipe_shape1.html",
            200,
            {"content-type": "text/html"},
            "sp-r...90ab",
        ),
        (
            "servicepipe_shape2.html",
            403,
            {"Content-Type": "text/html; charset=utf-8"},
            "sp-i...3210",
        ),
        (
            "servicepipe_shape2.html",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
            "sp-i...3210",
        ),
        (
            "servicepipe_403_bot.html",
            403,
            {"Content-Type": "text/html", "X-SP-CRID": "13005083566:3"},
            "1300...66:3",
        ),
        (
            "servicepipe_403_bot.html",
            403,
            {"Content-Type": "text/html"},
            None,
        ),
    ],
)
async def test_servicepipe_block_detected_across_shapes_and_statuses(
    http_client,
    fake_session,
    fixture_name: str,
    status: int,
    headers: dict[str, str],
    expected_id: str | None,
) -> None:
    """Все три формы ServicePipe (на 403 и 200 text/html) дают ServicePipeBlockError."""
    html = (_FIXTURES / fixture_name).read_bytes()
    resp = _html_response(status, html, headers=headers)
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    err = exc_info.value
    assert isinstance(err, ClientError)
    assert is_service_pipe_block(err) is True
    assert err.status == status
    assert error_status(err) == status
    assert err.request_id == expected_id


async def test_servicepipe_detected_via_text_fallback(http_client, fake_session) -> None:
    """Если mock ответа реализует только `.text()`, чтение тоже работает."""
    html = (_FIXTURES / "servicepipe_shape1.html").read_text(encoding="utf-8")
    resp = _html_response(403, html, use_text=True)
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert exc_info.value.request_id == "sp-r...90ab"


async def test_servicepipe_detected_on_binary_error(http_client, fake_session) -> None:
    """На binary=True не-2xx ServicePipe HTML также поднимает ServicePipeBlockError."""
    html = (_FIXTURES / "servicepipe_shape1.html").read_bytes()
    resp = _html_response(403, html)
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v1/forpost/cameras/1/snapshots", binary=True)

    assert exc_info.value.status == 403
    assert exc_info.value.request_id == "sp-r...90ab"


@pytest.mark.parametrize("status", [400, 500])
async def test_normal_json_errors_remain_plain_client_error(
    http_client, fake_session, status: int
) -> None:
    """Обычные JSON-ошибки 400/500 не читаются как HTML и не превращаются в WAF."""
    resp = MagicMock(spec=ClientResponse)
    resp.status = status
    resp.ok = False
    resp.reason = "Error"
    resp.method = "GET"
    resp.url = "https://example/rest/v3/subscriber-places"
    resp.headers = {"Content-Type": "application/json"}
    resp.read = AsyncMock(side_effect=AssertionError("JSON body must not be read"))
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ClientError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert not is_service_pipe_block(exc_info.value)
    assert error_status(exc_info.value) == status


async def test_servicepipe_never_leaks_ip_datetime_html_or_auth_context(
    http_client, fake_session, caplog
) -> None:
    """Sentinel: IP, datetime, полный HTML, телефон и токен не попадают в логи и str/repr."""
    html = (_FIXTURES / "servicepipe_shape1.html").read_bytes()
    auth_endpoint = "/auth/v2/login/+79991112233"
    resp = _html_response(
        403,
        html,
        url=f"https://example{auth_endpoint}",
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "X-SP-CRID": "13005083566:3",
            "Set-Cookie": "secret-cookie=abc",
        },
    )
    fake_session.get = AsyncMock(return_value=resp)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ServicePipeBlockError) as exc_info:
            await http_client.get(auth_endpoint)

    err = exc_info.value
    rendered = f"{caplog.text}\n{err!s}\n{err!r}"
    for forbidden in (
        "198.51.100.42",
        "2026-11-26T12:00:00Z",
        "REQUEST-ID",
        "ServicePipe Protection",
        "sp-req-1234567890ab",
        "+79991112233",
        "EXPIRED_BEARER_TOKEN",
        "secret-cookie",
    ):
        assert forbidden not in rendered, f"Утечка {forbidden!r} в логи/исключение"

    ours = [
        r for r in caplog.records
        if r.name.startswith("custom_components.elektronny_gorod")
        and "ServicePipe WAF" in r.msg
    ]
    assert len(ours) == 1
    assert ours[0].levelno == logging.DEBUG
    assert "/auth/v2/login/***" in ours[0].getMessage()
    assert "sp-r...90ab" in ours[0].getMessage()


def test_servicepipe_error_str_without_request_id() -> None:
    """str(ServicePipeBlockError) без request_id безопасен и не требует args[0].__str__."""
    resp = _FakeResponse(403, url="https://example/auth/v2/login/+79991112233")
    err = ServicePipeBlockError(resp)
    assert str(err) == "ServicePipe WAF block (status=403)"
    assert "+79991112233" not in str(err)
    assert "+79991112233" not in repr(err)


async def test_non_servicepipe_html_error_raises_plain_client_error(
    http_client, fake_session
) -> None:
    """Обычная 502 Bad Gateway HTML (без маркеров ServicePipe) → обычный ClientError."""
    resp = _html_response(
        502,
        b"<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>",
    )
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ClientError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert not is_service_pipe_block(exc_info.value)
    assert error_status(exc_info.value) == 502


async def test_200_json_with_x_sp_crid_does_not_inspect_body(
    http_client, fake_session
) -> None:
    """200 OK JSON с заголовком X-SP-CRID не читает тело и возвращает response."""
    resp = MagicMock(spec=ClientResponse)
    resp.status = 200
    resp.ok = True
    resp.reason = "OK"
    resp.method = "GET"
    resp.url = "https://example/rest/v3/subscriber-places"
    resp.headers = {"Content-Type": "application/json", "X-SP-CRID": "13005083566:3"}
    resp.read = AsyncMock(side_effect=AssertionError("JSON body must not be read"))
    fake_session.get = AsyncMock(return_value=resp)

    result = await http_client.get("/rest/v3/subscriber-places")
    assert result is resp


async def test_servicepipe_detected_from_chunked_stream_reader(
    http_client, fake_session
) -> None:
    """Чтение чанков из реального aiohttp.StreamReader ограничено и собирает полный HTML."""
    import asyncio
    from aiohttp import StreamReader
    from aiohttp.base_protocol import BaseProtocol

    html = (_FIXTURES / "servicepipe_shape1.html").read_bytes()
    mid = len(html) // 2
    stream = StreamReader(
        MagicMock(spec=BaseProtocol),
        limit=2**16,
        loop=asyncio.get_running_loop(),
    )
    stream.feed_data(html[:mid])
    stream.feed_data(html[mid:])
    stream.feed_eof()

    resp = MagicMock(spec=ClientResponse)
    resp.status = 403
    resp.ok = False
    resp.reason = "Forbidden"
    resp.method = "GET"
    resp.url = "https://example/rest/v3/subscriber-places"
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp.content = stream
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert exc_info.value.request_id == "sp-r...90ab"


async def test_servicepipe_detected_from_content_read_mock(
    http_client, fake_session
) -> None:
    """response.content.read (AsyncMock) тоже поддерживается."""
    html = (_FIXTURES / "servicepipe_shape2.html").read_bytes()
    resp = MagicMock(spec=ClientResponse)
    resp.status = 403
    resp.ok = False
    resp.reason = "Forbidden"
    resp.method = "GET"
    resp.url = "https://example/rest/v3/subscriber-places"
    resp.headers = {"Content-Type": "text/html"}
    resp.content = MagicMock()
    resp.content.read = AsyncMock(return_value=html)
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert exc_info.value.request_id == "sp-i...3210"


async def test_servicepipe_body_read_error_falls_back_gracefully(
    http_client, fake_session
) -> None:
    """Сбой чтения HTML-тела (ClientError/TimeoutError) не роняет обработку ошибки."""
    resp = MagicMock(spec=ClientResponse)
    resp.status = 502
    resp.ok = False
    resp.reason = "Bad Gateway"
    resp.method = "GET"
    resp.url = "https://example/rest/v3/subscriber-places"
    resp.headers = {"Content-Type": "text/html"}
    resp.read = AsyncMock(side_effect=ClientError("stream broken"))
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ClientError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert not is_service_pipe_block(exc_info.value)
    assert error_status(exc_info.value) == 502


async def test_non_2xx_json_with_x_sp_crid_does_not_drain_stream(
    http_client, fake_session
) -> None:
    """F-01: 400 application/json с X-SP-CRID не читает StreamReader — тело остаётся целым."""
    import asyncio
    from aiohttp import StreamReader
    from aiohttp.base_protocol import BaseProtocol

    payload = b'{"errorCode": "11005"}'
    stream = StreamReader(
        MagicMock(spec=BaseProtocol),
        limit=2**16,
        loop=asyncio.get_running_loop(),
    )
    stream.feed_data(payload)
    stream.feed_eof()

    resp = MagicMock(spec=ClientResponse)
    resp.status = 400
    resp.ok = False
    resp.reason = "Bad Request"
    resp.method = "GET"
    resp.url = "https://example/rest/v1/forpost/events/3001/downloads?container=mp4"
    resp.headers = {"Content-Type": "application/json", "X-SP-CRID": "13005083566:3"}
    resp.content = stream
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ClientError) as exc_info:
        await http_client.get("/rest/v1/forpost/events/3001/downloads?container=mp4")

    assert not is_service_pipe_block(exc_info.value)
    assert error_status(exc_info.value) == 400
    assert await exc_info.value.args[0].content.read() == payload


async def test_servicepipe_bounded_read_stops_at_64kib(
    http_client, fake_session
) -> None:
    """F-02: _read_bounded_body читает максимум 65536 байт и не идёт дальше 64 KiB."""
    import asyncio
    from aiohttp import StreamReader
    from aiohttp.base_protocol import BaseProtocol
    from custom_components.elektronny_gorod.http import _MAX_BLOCK_BODY_BYTES

    assert _MAX_BLOCK_BODY_BYTES == 65536
    html = (_FIXTURES / "servicepipe_shape1.html").read_bytes()

    # 1) Маркер после 64 KiB не должен читаться и распознаваться.
    stream_late = StreamReader(
        MagicMock(spec=BaseProtocol),
        limit=2**17,
        loop=asyncio.get_running_loop(),
    )
    padding = b"x" * 70000
    stream_late.feed_data(padding[:32768])
    stream_late.feed_data(padding[32768:])
    stream_late.feed_data(html)
    stream_late.feed_eof()

    resp_late = MagicMock(spec=ClientResponse)
    resp_late.status = 403
    resp_late.ok = False
    resp_late.reason = "Forbidden"
    resp_late.method = "GET"
    resp_late.url = "https://example/rest/v3/subscriber-places"
    resp_late.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp_late.content = stream_late
    fake_session.get = AsyncMock(return_value=resp_late)

    with pytest.raises(ClientError) as exc_info:
        await http_client.get("/rest/v3/subscriber-places")

    assert not is_service_pipe_block(exc_info.value)
    remaining_late = await stream_late.read()
    assert len(remaining_late) == (len(padding) + len(html)) - _MAX_BLOCK_BODY_BYTES

    # 2) Маркер в первых 64 KiB + хвост > 64 KiB распознаётся, не читая хвост.
    stream_early = StreamReader(
        MagicMock(spec=BaseProtocol),
        limit=2**17,
        loop=asyncio.get_running_loop(),
    )
    tail = b"z" * 70000
    stream_early.feed_data(html)
    stream_early.feed_data(tail)
    stream_early.feed_eof()

    resp_early = MagicMock(spec=ClientResponse)
    resp_early.status = 403
    resp_early.ok = False
    resp_early.reason = "Forbidden"
    resp_early.method = "GET"
    resp_early.url = "https://example/rest/v3/subscriber-places"
    resp_early.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp_early.content = stream_early
    fake_session.get = AsyncMock(return_value=resp_early)

    with pytest.raises(ServicePipeBlockError) as waf_exc:
        await http_client.get("/rest/v3/subscriber-places")

    assert waf_exc.value.request_id == "sp-r...90ab"
    remaining_early = await stream_early.read()
    assert len(remaining_early) == (len(html) + len(tail)) - _MAX_BLOCK_BODY_BYTES


async def test_binary_200_text_html_servicepipe_raises(
    http_client, fake_session
) -> None:
    """F-03: 200 text/html ServicePipe на binary=True бросает ServicePipeBlockError, а не возвращает HTML."""
    html = (_FIXTURES / "servicepipe_shape1.html").read_bytes()
    resp = _html_response(200, html, headers={"Content-Type": "text/html; charset=utf-8"})
    fake_session.get = AsyncMock(return_value=resp)

    with pytest.raises(ServicePipeBlockError) as exc_info:
        await http_client.get("/rest/v1/forpost/cameras/1/snapshots", binary=True)

    assert exc_info.value.status == 200
    assert exc_info.value.request_id == "sp-r...90ab"
