"""HTTP interface."""

from aiohttp import ClientError, ClientResponse, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._logging import redact, is_auth_path, redact_path
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
    LOGGER.debug(
        "Request %s %s headers=%s body=%s",
        method,
        url,
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
        LOGGER.debug("Response %s %s [%s]", response.method, url, response.status)
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
        self, endpoint: str, method: str, data: object | None, binary: bool
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
        # content-type для тела (POST всегда; DELETE с телом — мирроринг
        # subscriberNotifications-отписки, см. api.unregister_push_device).
        if method == "POST" or (method == "DELETE" and data is not None):
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
        if method == "GET":
            response = await session.get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            response = await session.post(url, data=data, headers=headers, timeout=timeout)
        elif method == "DELETE":
            response = await session.delete(url, data=data, headers=headers, timeout=timeout)

        if binary:
            return await response.read()

        await _log_response(response)
        if response.ok:
            return response
        else:
            LOGGER.error("API request failed: %s [%s]", redact_path(endpoint), response.status)
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
