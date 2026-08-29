"""Same-origin clip proxy: streams operator mp4 clips through HA.

Chromium ORB blocks the operator storage host in `<video>` elements: it
serves clips as `application/octet-stream` +
`Content-Disposition: attachment` (runtime 2026-08-30), which opaque
response blocking refuses cross-origin. The mobile app downloads via its
own HTTP client, so only browser playback is affected.

The proxy also keeps the operator's signed link server-side: the browser
receives only a short-lived HMAC-signed same-origin URL (camera/tts
proxy pattern — a `<video>` tag cannot attach HA session auth).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from typing import Any

from aiohttp import ClientError, ClientResponse, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ForpostDownloadError
from .const import DOMAIN, LOGGER

_SECRET_KEY = f"{DOMAIN}_clip_signing_secret"
_VIEW_REGISTERED = f"{DOMAIN}_clip_view_registered"
_TOKEN_TTL = 600.0
_CHUNK_SIZE = 64 * 1024

_FORWARDED_HEADERS = ("Content-Range", "Content-Length", "Accept-Ranges")

# ErrorCode 102 / HTTP 423: оператор готовит mp4 (mint и storage-слой).
_ERROR_PREPARING = "102"
_HTTP_LOCKED = 423
_DOWNLOAD_PREPARE_INTERVAL = 2.0
_DOWNLOAD_PREPARE_BUDGET = 30.0


def _get_secret(hass: HomeAssistant) -> str:
    """Return the per-boot signing secret (rotates on HA restart)."""
    secret = hass.data.get(_SECRET_KEY)
    if secret is None:
        secret = secrets.token_hex(32)
        hass.data[_SECRET_KEY] = secret
    return secret


def sign_clip_token(
    hass: HomeAssistant,
    entry_id: str,
    event_id: str,
    *,
    now: float | None = None,
) -> str:
    """Sign one clip token: HMAC over entry, event and expiry."""
    exp = int((time.time() if now is None else now) + _TOKEN_TTL)
    payload = f"clip:{entry_id}:{event_id}:{exp}"
    digest = hmac.new(
        _get_secret(hass).encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{exp}.{digest}"


def verify_clip_token(
    hass: HomeAssistant,
    token: str,
    entry_id: str,
    event_id: str,
    *,
    now: float | None = None,
) -> bool:
    """Constant-time verification of a clip token against its payload."""
    try:
        exp_str, digest = token.split(".", 1)
        exp = int(exp_str)
    except (AttributeError, ValueError):
        return False
    payload = f"clip:{entry_id}:{event_id}:{exp}"
    expected = hmac.new(
        _get_secret(hass).encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    # bytes-compare: str-версия бросает TypeError на non-ASCII digest
    # (unauthenticated 500 — security-auditor I-1, 2026-08-30).
    if not hmac.compare_digest(digest.encode(), expected.encode()):
        return False
    return (time.time() if now is None else now) < exp


def clip_proxy_url(hass: HomeAssistant, entry_id: str, event_id: str) -> str:
    """Relative same-origin playback URL carrying the signed token."""
    return (
        f"/api/elektronny_gorod/clips/{entry_id}/{event_id}"
        f"?t={sign_clip_token(hass, entry_id, event_id)}"
    )


@callback
def async_register_clip_view(hass: HomeAssistant) -> None:
    """Register the streaming view once per HA instance."""
    if hass.data.get(_VIEW_REGISTERED) or hass.http is None:
        return
    hass.http.register_view(ClipProxyView())
    hass.data[_VIEW_REGISTERED] = True


class ClipProxyView(HomeAssistantView):
    """Stream one prepared operator clip as same-origin video/mp4."""

    url = "/api/elektronny_gorod/clips/{entry_id}/{event_id}"
    name = "api:elektronny_gorod:clips"
    requires_auth = False

    async def get(
        self, request: web.Request, entry_id: str, event_id: str
    ) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        if not (event_id.isascii() and event_id.isdigit()) or not verify_clip_token(
            hass, request.query.get("t", ""), entry_id, event_id
        ):
            return self.json_message("Invalid or expired clip link", 403)
        coordinator: Any = (hass.data.get(DOMAIN) or {}).get(entry_id)
        if coordinator is None:
            return self.json_message("Unknown media item", 404)
        session = async_get_clientsession(hass)
        # Runtime 2026-09-01: mint-гейт (ErrorCode 102) и storage-гейт
        # (HTTP 423 на файл) — оператор готовит mp4 по требованию.
        # Контракт мобильного приложения: минт ОДИН раз, затем GET той же
        # ссылки до готовности; re-mint каждый цикл держал storage-гейт
        # вечно непроходимым (production 12:01–12:03).
        deadline = time.monotonic() + _DOWNLOAD_PREPARE_BUDGET
        while True:
            try:
                source_url = await coordinator.api.query_event_download(event_id)
            except ForpostDownloadError as err:
                if err.error_code == _ERROR_PREPARING:
                    if time.monotonic() >= deadline:
                        return self.json_message(
                            "Recording is being prepared, try again shortly", 503
                        )
                    await asyncio.sleep(_DOWNLOAD_PREPARE_INTERVAL)
                    continue
                return self.json_message("Recording is not available", 404)
            except Exception as ex:  # noqa: BLE001 - operator boundary
                LOGGER.debug(
                    "Clip proxy download failed for event_id=%s (%s)",
                    event_id,
                    type(ex).__name__,
                )
                return self.json_message("Archive is temporarily unavailable", 502)
            break

        # Signed link ОДНОРАЗОВЫЙ (runtime 2026-09-01: первый успешный GET
        # погашает token, второй — 404). Поэтому client Range идёт в самих
        # poll-запросах, а первый 200/206 стримится напрямую без re-fetch.
        poll_headers: dict[str, str] = {}
        range_header = request.headers.get("Range")
        if range_header:
            poll_headers["Range"] = range_header
        # source_url — подписанный операторский link; никогда не логируется.
        while True:
            try:
                upstream = await session.get(source_url, headers=poll_headers)
            except (ClientError, ValueError) as ex:
                LOGGER.debug(
                    "Clip proxy upstream failed for event_id=%s (%s)",
                    event_id,
                    type(ex).__name__,
                )
                return self.json_message("Archive is temporarily unavailable", 502)
            if upstream.status == _HTTP_LOCKED:
                upstream.close()
                LOGGER.debug(
                    "Clip proxy storage preparing event_id=%s — waiting",
                    event_id,
                )
                if time.monotonic() >= deadline:
                    return self.json_message(
                        "Recording is being prepared, try again shortly", 503
                    )
                await asyncio.sleep(_DOWNLOAD_PREPARE_INTERVAL)
                continue
            if upstream.status not in (200, 206):
                upstream.close()
                LOGGER.debug(
                    "Clip proxy upstream rejected event_id=%s (status=%s)",
                    event_id,
                    upstream.status,
                )
                return self.json_message("Archive is temporarily unavailable", 502)
            return await self._stream_response(request, upstream)

    async def _stream_response(
        self, request: web.Request, upstream: ClientResponse
    ) -> web.StreamResponse:
        stream = web.StreamResponse(status=upstream.status)
        stream.headers["Content-Type"] = "video/mp4"
        for header in _FORWARDED_HEADERS:
            value = upstream.headers.get(header)
            if not value:
                continue
            # HA-сессия auto-decompress: Content-Length может не совпасть
            # с телом при Content-Encoding на upstream — не форвардим его.
            if header == "Content-Length" and upstream.headers.get(
                "Content-Encoding"
            ):
                continue
            stream.headers[header] = value
        try:
            await stream.prepare(request)
            async for chunk in upstream.content.iter_chunked(_CHUNK_SIZE):
                await stream.write(chunk)
        except (ClientError, ConnectionResetError):
            return stream
        finally:
            upstream.close()
        return stream
