from __future__ import annotations

import uuid
import base64
from dataclasses import dataclass
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .const import LOGGER


@dataclass(frozen=True)
class Go2RtcValidationResult:
    ok: bool
    error: str = ""
    rtsp_host: str | None = None


def build_go2rtc_src(source_url: str) -> str:
    """Build go2rtc source for an operator stream URL.

    Do not use `ffmpeg:` here: many go2rtc installations restrict external
    binaries with `allow_paths`, which breaks RTSP publishing for NVR clients.
    """
    return source_url


def build_basic_auth_headers(
    username: str | None,
    password: str | None,
) -> dict[str, str]:
    """Build go2rtc Basic auth headers if credentials are configured."""
    if not username or not password:
        return {}
    userpass = f"{username}:{password}"
    b64 = base64.b64encode(userpass.encode()).decode()
    return {"Authorization": f"Basic {b64}"}


async def upsert_go2rtc_stream(
    session: ClientSession,
    base_url: str,
    stream_name: str,
    src: str,
    headers: dict | None = None,
) -> None:
    """Create or update a go2rtc stream without leaking source URLs in errors."""
    qs = urlencode({"name": stream_name, "src": src})
    url = f"{base_url}/api/streams?{qs}"
    timeout = ClientTimeout(total=10)

    try:
        async with session.patch(
            url, headers=headers or {}, timeout=timeout
        ) as resp:
            if resp.status in (200, 201, 204):
                return
    except ClientError:
        pass

    try:
        async with session.put(url, headers=headers or {}, timeout=timeout) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"go2rtc PUT failed: HTTP {resp.status}")
    except ClientError as exc:
        raise RuntimeError(f"go2rtc PUT failed: {type(exc).__name__}") from None


def normalize_base_url(value: str | None) -> str:
    """Trim and remove trailing slash. Returns '' if empty."""
    return (value or "").strip().rstrip("/")


def derive_rtsp_host(base_url: str) -> str | None:
    """Extract host from http(s)://host:port URL."""
    try:
        host = URL(base_url).host
        return host or None
    except Exception:
        return None


async def validate_go2rtc(base_url: str, session: ClientSession, username: str | None = None, password: str | None = None) -> Go2RtcValidationResult:
    """
    Validate go2rtc HTTP API and that streams API is writable.

    Checks:
    1) GET  {base_url}/api -> 200
    2) PUT  {base_url}/api/streams?name=...&src=...
    3) DELETE cleanup {base_url}/api/streams?src=<name> (best-effort)

    Returns:
      Go2RtcValidationResult(ok, error, rtsp_host)
    """
    base_url = normalize_base_url(base_url)
    if not base_url:
        return Go2RtcValidationResult(False, "go2rtc_required_fields", None)

    rtsp_host = derive_rtsp_host(base_url)
    if not rtsp_host:
        return Go2RtcValidationResult(False, "go2rtc_invalid_url", None)

    headers = build_basic_auth_headers(username, password)

    # 1) ping /api
    try:
        async with session.get(f"{base_url}/api", headers=headers) as resp:
            if resp.status == 401:
                return Go2RtcValidationResult(False, "go2rtc_auth_failed", rtsp_host)
            if resp.status != 200:
                return Go2RtcValidationResult(False, "go2rtc_unreachable", rtsp_host)
    except ClientError:
        return Go2RtcValidationResult(False, "go2rtc_unreachable", rtsp_host)

    # 2) streams PUT check
    test_name = f"ha_check_{uuid.uuid4().hex[:8]}"
    test_src = "rtsp://127.0.0.1:8554/does_not_exist"
    put_qs = urlencode({"name": test_name, "src": test_src})

    try:
        async with session.put(f"{base_url}/api/streams?{put_qs}", headers=headers) as resp:
            if resp.status == 401:
                return Go2RtcValidationResult(False, "go2rtc_auth_failed", rtsp_host)
            if resp.status not in (200, 201, 204):
                body = await resp.text()
                LOGGER.debug("go2rtc streams check failed: %s %s", resp.status, body)
                return Go2RtcValidationResult(False, "go2rtc_streams_api_failed", rtsp_host)
    except ClientError:
        return Go2RtcValidationResult(False, "go2rtc_streams_api_failed", rtsp_host)
    finally:
        # 3) cleanup (best-effort)
        await cleanup_go2rtc_stream(base_url, test_name, session, headers)

    return Go2RtcValidationResult(True, "", rtsp_host)


async def cleanup_go2rtc_stream(base_url: str, stream_name: str, session: ClientSession, headers: dict = None) -> None:
    """Best-effort cleanup stream created by validate_go2rtc."""
    base_url = normalize_base_url(base_url)
    if not base_url or not stream_name:
        return

    # go2rtc API uses src=<stream_name> for delete
    del_qs = urlencode({"src": stream_name})
    try:
        async with session.delete(f"{base_url}/api/streams?{del_qs}", headers=headers or {}) as resp:
            # 404 ok (already gone), 200/204 ok
            if resp.status in (200, 204, 404):
                return
            body = await resp.text()
            LOGGER.debug("go2rtc cleanup failed: %s %s", resp.status, body)
    except ClientError as err:
        LOGGER.debug("go2rtc cleanup request failed: %s", err)
