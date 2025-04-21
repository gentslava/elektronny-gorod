"""HTTP interface."""

from aiohttp import ClientSession, ClientError, ClientResponse
from .const import (
    BASE_API_URL,
    LOGGER,
)
from .user_agent import UserAgent


async def _log_request(url, headers, data) -> None:
    """Log the request."""
    LOGGER.info(f"Sending API request to {url} with headers={headers} and data={data}")


async def _log_response(response: ClientResponse) -> None:
    """Log the request."""
    _url = response.url
    _method = response.method
    _status = response.status
    _reason = response.reason
    if body := await response.text():
        LOGGER.debug(f"Response {_url} ({_method}) [{_status} {_reason}] data: {body}")
    else:
        LOGGER.debug(f"Response {_url} ({_method}) [{_status} {_reason}]")


class HTTP:
    def __init__(
        self,
        user_agent: UserAgent,
        access_token: str | None,
        refresh_token: str | None,
        operator: str | None,
    ) -> None:
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
        """Make a HTTP request."""
        if self.access_token is not None:
            self._headers["authorization"] = f"Bearer {self.access_token}"
        self._headers["user-agent"] = str(self.user_agent)
        if method == "POST":
            self._headers["content-type"] = "application/json; charset=UTF-8"

        async with ClientSession() as session:
            url = f"{self._base_url}{endpoint}"
            await _log_request(url, self._headers, data)
            if method == "GET":
                response = await session.get(url, headers=self._headers)
            elif method == "POST":
                response = await session.post(url, data=data, headers=self._headers)

            if binary:
                return await response.read()

            await _log_response(response)
            if response.ok:
                return response
            else:
                LOGGER.error(f"Could not get data from API")
                raise ClientError(response)

    async def get(self, endpoint: str, binary: bool = False) -> ClientResponse | bytes:
        """Handle GET requests."""
        return await self.__request(endpoint, method="GET", data=None, binary=binary)

    async def post(
        self, endpoint: str, data: object, binary: bool = False
    ) -> ClientResponse | bytes:
        """Handle POST requests."""
        return await self.__request(endpoint, method="POST", data=data, binary=binary)
