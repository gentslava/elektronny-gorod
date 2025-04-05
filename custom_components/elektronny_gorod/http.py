"""HTTP interface."""
from aiohttp import ClientSession, ClientError, ClientResponse
from .const import (
    BASE_API_URL,
    LOGGER,
)

async def _log_request(url, headers, data) -> None:
    """Log the request."""
    LOGGER.info(f"Sending API request to {url} with headers={headers} and data={data}")

async def _log_response(response: ClientResponse) -> None:
    """Log the request."""
    if body := await response.text():
        LOGGER.debug(f"Response is {response.url} ({response.method}) [{response.status} {response.reason}] data: {body}")
    else:
        LOGGER.debug(f"Response is {response.url} ({response.method}) [{response.status} {response.reason}]")

class HTTP:
    def __init__(
        self,
        user_agent: str,
        access_token: str | None,
        refresh_token: str | None,
        headers: dict,
    ) -> None:
        self.base_url: str = f"https://{BASE_API_URL}"
        self.user_agent: str = user_agent
        self.headers: dict = {
            **{
                "Host": BASE_API_URL,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
            },
            **headers
        }
        self.access_token: str | None = access_token
        self.refresh_token: str | None = refresh_token

    async def __request(self, endpoint: str, method: str, data: object | None, binary: bool):
        """Make a HTTP request."""
        if self.access_token is not None: self.headers["Authorization"] = f"Bearer {self.access_token}"
        self.headers["User-Agent"] = self.user_agent
        if method == "POST":
            self.headers["Content-Type"] = "application/json; charset=UTF-8"

        async with ClientSession() as session:
            url = f"{self.base_url}{endpoint}"
            await _log_request(url, self.headers, data)
            if method == "GET":
                response = await session.get(url, headers = self.headers)
            elif method == "POST":
                response = await session.post(url, data = data, headers = self.headers)

            if binary: return await response.read()

            await _log_response(response)
            if response.ok:
                try: return await response.json()
                except: return await response.text()
            else:
                LOGGER.error(f"Could not get data from API")
                raise ClientError(response)

    async def get(self, endpoint: str, binary: bool = False):
        """Handle GET requests."""
        return await self.__request(endpoint, method = "GET", data = None, binary = binary)

    async def post(self, endpoint: str, data: object, binary: bool = False):
        """Handle POST requests."""
        return await self.__request(endpoint, method = "POST", data = data, binary = binary)

    def update_access_token(self, access_token) -> None:
        self.access_token = access_token
