"""HTTP interface."""

import inspect
import re
from typing import Any, Literal, assert_never

from aiohttp import ClientError, ClientResponse, ClientTimeout, StreamReader

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._logging import REDACTED, redact, is_auth_path, redact_path
from .const import (
    BASE_API_URL,
    LOGGER,
)
from .user_agent import UserAgent

# A-21: явные таймауты на operator API. Без них shared HA-сессия использует
# дефолт aiohttp (total≈5 мин), а refresh coordinator-а сериальный (~6 HTTP на
# place) — один зависший запрос надолго тормозит tick / первый setup.
# REST — короткий кап; binary (snapshot JPEG) — щедрее по total; connect-кап
# даёт быстрый fail на недоступный хост. Retry/backoff сознательно вне scope
# этого слайса (POST/login/open_lock не идемпотентны) — см. audit A-21.
_REST_TIMEOUT = ClientTimeout(total=30, connect=10)
_BINARY_TIMEOUT = ClientTimeout(total=60, connect=10)

# Endpoints that the stock 9.9.0 client calls before authentication. Keep this
# narrow: `/rest/v2/.../public/cameras` contains `public` but still requires a
# Bearer token.
_PREAUTH_PATH_PREFIXES = (
    "/auth/",
    "/api/mh-customer-device/mobile/public/",
)

_MAX_BLOCK_BODY_BYTES = 65536

# Сигнатуры HTML-заглушки ServicePipe / WAF (APK 9.9.0 ve/c.java, ve/d.java + issue #107/#102).
_SP_SHAPE1_RE = re.compile(r"""<p[^>]*\bid\s*=\s*["']REQUEST-ID["']""", re.IGNORECASE)
_SP_SHAPE1_ID_RE = re.compile(
    r"""<p[^>]*\bid\s*=\s*["']REQUEST-ID["'][^>]*>\s*(?:ID:\s*)?([^<\r\n]+)""",
    re.IGNORECASE,
)
_SP_SHAPE2_INFO_RE = re.compile(r"""\bid\s*=\s*["']info["']""", re.IGNORECASE)
_SP_SHAPE2_DATETIME_RE = re.compile(r"""\bdatetime\s*:""", re.IGNORECASE)
_SP_SHAPE2_IP_RE = re.compile(r"""\bip\s*:""", re.IGNORECASE)
_SP_SHAPE2_ID_RE = re.compile(
    r"""(?:<br\s*/?>\s*|\n\s*)id:\s*([^\s<]+)""",
    re.IGNORECASE,
)


def _log_request(url: str, method: str, headers: dict, body_size: int) -> None:
    """Log outgoing request. Headers redacted; body NEVER logged.

    Для auth-paths факт наличия body тоже не упоминаем (минимизируем сигнал).
    Для остальных — реальный размер body в байтах.
    """
    if is_auth_path(url):
        body_marker = "<auth-path-redacted>"
    elif body_size > 0:
        body_marker = f"<{body_size} bytes>"
    else:
        body_marker = "<none>"
    # URL — через ту же редакцию, что и лог отказа: телефон стоит прямо в
    # пути auth-запроса. Функция уже прятала заголовки и признак тела, но
    # оставляла его на виду, а именно debug-логи люди прикладывают к issue.
    LOGGER.debug(
        "Request %s %s headers=%s body=%s",
        method,
        redact_path(url),
        redact(headers),
        body_marker,
    )


async def _log_response(response: ClientResponse) -> None:
    """Log response status + length. Body НЕ логируется для auth-paths;
    для остальных — только размер, не содержимое.
    """
    url = str(response.url)
    if is_auth_path(url):
        # Полностью пропускаем — даже размер ответа может намекать на исход (success vs error).
        LOGGER.debug(
            "Response %s %s [%s]", response.method, redact_path(url), response.status
        )
        return
    # Не читаем body здесь — иначе streaming-ответы будут consumed.
    # Размер берём из Content-Length, если есть.
    content_length = response.headers.get("Content-Length", "?")
    LOGGER.debug(
        "Response %s %s [%s %s] content-length=%s",
        response.method,
        url,
        response.status,
        response.reason,
        content_length,
    )


def redact_request_id(raw: str | None) -> str | None:
    """Оставить безопасные символы correlation ID и замаскировать середину."""
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped == REDACTED:
        return REDACTED
    cleaned = "".join(
        ch for ch in stripped if ch.isascii() and (ch.isalnum() or ch in ":._-")
    )
    if not cleaned:
        return None
    if len(cleaned) > 8:
        return f"{cleaned[:4]}...{cleaned[-4:]}"
    return REDACTED


class ServicePipeBlockError(ClientError):
    """Запрос заблокирован антибот-защитой ServicePipe / WAF."""

    def __init__(
        self,
        status: int | None = None,
        *,
        request_id: str | None = None,
    ) -> None:
        self.status: int | None = status
        self.request_id: str | None = redact_request_id(request_id)
        super().__init__(str(self))

    def __str__(self) -> str:
        """Безопасное текстовое представление без URL, заголовков и HTML."""
        if self.request_id:
            return (
                f"ServicePipe WAF block (status={self.status}, "
                f"request_id={self.request_id})"
            )
        return f"ServicePipe WAF block (status={self.status})"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status={self.status!r}, "
            f"request_id={self.request_id!r})"
        )


def is_service_pipe_block(err: BaseException) -> bool:
    """True, если исключение вызвано блокировкой ServicePipe / WAF."""
    return isinstance(err, ServicePipeBlockError)


def error_status(err: BaseException) -> int | None:
    """Статус ответа оператора, если исключение его несёт.

    Ответ лежит в аргументе исключения — так его кладёт `ClientError(response)`
    здесь же. Прямая распаковка `err.args[0]` роняла `IndexError` на
    исключениях без аргументов: таймаут или сетевая ошибка при входе
    превращались не в понятное сообщение формы, а в «неизвестную ошибку» с
    трассировкой, потому что config flow ловит только `ValueError`.
    """
    if isinstance(err, ServicePipeBlockError):
        return err.status
    args = getattr(err, "args", ())
    response = args[0] if args else None
    return response.status if isinstance(response, ClientResponse) else None


def is_unauthorized(err: BaseException) -> bool:
    """Оператор отверг токен: нужна новая авторизация, а не повтор запроса."""
    return error_status(err) == 401


def _find_header_ci(headers: Any, name: str) -> str | None:
    """Case-insensitive чтение заголовка из dict или CIMultiDictProxy."""
    if not headers or not hasattr(headers, "items"):
        return None
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return None


async def _read_bounded_body(response: ClientResponse) -> tuple[str, bytes]:
    """Безопасно прочитать до 64 KiB тела ответа для проверки ServicePipe.

    Возвращает `(decoded_text, uncached_prefix)`. `uncached_prefix` непустой,
    только если байты читались напрямую из `response.content` (что сдвигает
    `StreamReader` без записи в `response._body`) и их нужно склеить с
    остатком на не-ServicePipe `binary=True` ответах.
    """
    try:
        content = getattr(response, "content", None)
        content_read = getattr(content, "read", None)
        if inspect.iscoroutinefunction(content_read):
            if isinstance(content, StreamReader):
                chunks: list[bytes] = []
                total = 0
                while total < _MAX_BLOCK_BODY_BYTES:
                    chunk = await content_read(_MAX_BLOCK_BODY_BYTES - total)
                    if not isinstance(chunk, (bytes, bytearray)) or not chunk:
                        break
                    chunks.append(bytes(chunk))
                    total += len(chunk)
                prefix = b"".join(chunks)[:_MAX_BLOCK_BODY_BYTES]
                return prefix.decode("utf-8", errors="replace"), prefix
            raw = await content_read(_MAX_BLOCK_BODY_BYTES)
            if isinstance(raw, (bytes, bytearray)):
                prefix = bytes(raw[:_MAX_BLOCK_BODY_BYTES])
                return prefix.decode("utf-8", errors="replace"), prefix

        read_fn = getattr(response, "read", None)
        if inspect.iscoroutinefunction(read_fn):
            raw = await read_fn()
            if isinstance(raw, (bytes, bytearray)):
                return (
                    bytes(raw[:_MAX_BLOCK_BODY_BYTES]).decode(
                        "utf-8", errors="replace"
                    ),
                    b"",
                )

        text_fn = getattr(response, "text", None)
        if inspect.iscoroutinefunction(text_fn):
            text = await text_fn()
            if isinstance(text, str):
                return text[:_MAX_BLOCK_BODY_BYTES], b""
    except (ClientError, TimeoutError, UnicodeDecodeError, OSError):
        return "", b""
    return "", b""


def _detect_service_pipe(
    status: int | None,
    sp_crid: str | None,
    body: str,
) -> tuple[bool, str | None]:
    """Распознать HTML-страницу блокировки ServicePipe по содержимому тела."""
    if body and _SP_SHAPE1_RE.search(body):
        match = _SP_SHAPE1_ID_RE.search(body)
        raw_id = match.group(1).strip() if match else None
        return True, raw_id or sp_crid or None

    if (
        body
        and _SP_SHAPE2_INFO_RE.search(body)
        and _SP_SHAPE2_DATETIME_RE.search(body)
        and _SP_SHAPE2_IP_RE.search(body)
    ):
        match = _SP_SHAPE2_ID_RE.search(body)
        raw_id = match.group(1).strip() if match else None
        return True, raw_id or sp_crid or None

    if status == 403 and body and "if you are not a bot" in body.lower():
        return True, sp_crid or None

    return False, None


async def _raise_if_service_pipe_block(
    response: ClientResponse, endpoint: str
) -> bytes:
    """Проверить ответ на ServicePipe WAF и поднять ServicePipeBlockError.

    Если блок не подтвердился, возвращает uncached prefix байтов (если чтение
    шло напрямую из `response.content`), чтобы caller не потерял начало потока.
    """
    headers = getattr(response, "headers", None)
    content_type = _find_header_ci(headers, "Content-Type") or ""
    mime_type = content_type.split(";", 1)[0].strip().lower()
    sp_crid = _find_header_ci(headers, "X-SP-CRID")

    inspect_body = (
        mime_type == "text/html"
        if response.ok
        else ("html" in mime_type or (not mime_type and sp_crid is not None))
    )
    if not inspect_body:
        return b""

    body, uncached_prefix = await _read_bounded_body(response)
    status = getattr(response, "status", None)
    matched, raw_id = _detect_service_pipe(status, sp_crid, body)
    if not matched:
        return uncached_prefix

    close_fn = getattr(response, "close", None)
    if callable(close_fn):
        close_fn()

    redacted_id = redact_request_id(raw_id)
    LOGGER.debug(
        "API request blocked by ServicePipe WAF: %s [%s] request_id=%s",
        redact_path(endpoint),
        status,
        redacted_id,
    )
    raise ServicePipeBlockError(status, request_id=raw_id)


class HTTP:
    def __init__(
        self,
        hass: HomeAssistant,
        user_agent: UserAgent,
        access_token: str | None,
        refresh_token: str | None,
        operator: str | None,
    ) -> None:
        self._hass = hass
        self._base_url: str = f"https://{BASE_API_URL}"
        self.user_agent: UserAgent = user_agent
        self._headers: dict = {
            "accept-encoding": "gzip",
        }
        if operator is not None:
            self._headers["operator"] = operator
        self.access_token: str | None = access_token
        self._refresh_token: str | None = refresh_token

    async def __request(
        self,
        endpoint: str,
        method: Literal["GET", "POST", "DELETE"],
        data: object | None,
        binary: bool,
    ) -> ClientResponse | bytes:
        """Make a HTTP request through shared HA aiohttp session.

        См. ADR-0008. Не создаём свою ClientSession — это нарушение HA convention
        (audit A-05, security S-05).
        """
        session = async_get_clientsession(self._hass)
        url = f"{self._base_url}{endpoint}"

        # Per-request headers (не накапливаем в self._headers, чтобы Authorization
        # из прошлых запросов не утекал в pre-auth endpoints).
        headers: dict[str, str] = dict(self._headers)
        headers["user-agent"] = str(self.user_agent)
        # content-type — только когда есть тело (POST; DELETE с телом —
        # мирроринг subscriberNotifications-отписки, см.
        # api.unregister_push_device). POST без тела приложение шлёт без
        # типа: Retrofit без `@Body` его не объявляет, HAR `guests/link`.
        if method in ("POST", "DELETE") and data is not None:
            headers["content-type"] = "application/json; charset=UTF-8"
        # Bearer НЕ шлём на pre-auth endpoints — иначе backend может увидеть
        # expired Bearer и отклонить reauth/bootstrap. HAR 9.9.0 подтверждает,
        # что public device-installations также вызывается без Authorization.
        is_preauth = any(
            endpoint.startswith(prefix) for prefix in _PREAUTH_PATH_PREFIXES
        )
        if self.access_token is not None and not is_preauth:
            headers["authorization"] = f"Bearer {self.access_token}"
        # data может быть str/bytes/None. Размер считаем безопасно.
        if data is None:
            body_size = 0
        elif isinstance(data, (bytes, bytearray)):
            body_size = len(data)
        else:
            body_size = len(str(data).encode("utf-8"))
        _log_request(url, method, headers, body_size)
        timeout = _BINARY_TIMEOUT if binary else _REST_TIMEOUT
        # Явный `raise` в конце, а не `else` у DELETE: аннотация `Literal`
        # проверяется статически, но если её когда-нибудь расширят, метод не
        # должен молча подмениться на удаление.
        if method == "GET":
            response = await session.get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            response = await session.post(url, data=data, headers=headers, timeout=timeout)
        elif method == "DELETE":
            response = await session.delete(url, data=data, headers=headers, timeout=timeout)
        else:
            # Ветка недостижима, пока `Literal` исчерпан ветками выше, — и
            # `assert_never` именно это и фиксирует: добавят метод в `Literal`,
            # забыв ветку, — анализ упадёт здесь. В рантайме остаётся отказ, а
            # не молчаливая подмена метода. Подавление ниже адресное: это
            # единственное место, где недостижимость намеренная.
            assert_never(method)  # pyright: ignore[reportUnreachable]

        if binary:
            uncached_prefix = await _raise_if_service_pipe_block(response, endpoint)
            # Статус проверяем и здесь: иначе тело ошибки оператора уходит
            # вызывающему как «данные». Для снимка это означало картинку из
            # JSON-текста ошибки, которую потребитель принимал за кадр.
            if not response.ok:
                # Уровень debug: статус уходит вызывающему исключением, а он
                # уже решает, что это — отказ оператора на снимке (штатное
                # дело, A-105) или настоящая поломка.
                LOGGER.debug(
                    "API binary request failed: %s [%s]",
                    redact_path(endpoint),
                    response.status,
                )
                raise ClientError(response)
            tail = await response.read()
            return uncached_prefix + tail if uncached_prefix else tail

        await _log_response(response)
        await _raise_if_service_pipe_block(response, endpoint)
        if response.ok:
            return response
        else:
            # `debug`, как и у бинарной ветки выше, и по той же причине:
            # транспорт не знает, значим ли отказ. Решает вызывающий —
            # координатор ограничивает жалобу по фронту с гранулярностью
            # «вид данных + место», а config flow показывает причину в форме.
            #
            # Пробовал и промежуточное — жалобу по фронту прямо здесь. Не
            # работает: ключ по пути схлопывает места, различающиеся
            # query-строкой (`finance?placeId=`), и наоборот размножается на
            # endpoint-ах с идентификатором в пути (архивная запись), где
            # «отказ» — это штатное «клип старше срока хранения».
            LOGGER.debug(
                "API request failed: %s [%s]", redact_path(endpoint), response.status
            )
            raise ClientError(response)

    async def get(self, endpoint: str, binary: bool = False) -> ClientResponse | bytes:
        """Handle GET requests."""
        return await self.__request(endpoint, method="GET", data=None, binary=binary)

    async def post(
        self, endpoint: str, data: object, binary: bool = False
    ) -> ClientResponse | bytes:
        """Handle POST requests."""
        return await self.__request(endpoint, method="POST", data=data, binary=binary)

    async def delete(
        self, endpoint: str, data: object | None = None
    ) -> ClientResponse | bytes:
        """Handle DELETE requests (опц. тело — мирроринг отписки)."""
        return await self.__request(endpoint, method="DELETE", data=data, binary=False)
