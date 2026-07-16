from __future__ import annotations

import asyncio
import base64
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .const import GO2RTC_RTSP_PORT, LOGGER

# G-7 / A-79: TCP-probe RTSP-порта go2rtc после успешной HTTP-валидации.
# Если HTTP API открыт, а RTSP-порт закрыт (firewall, иной bind-address,
# go2rtc собран без RTSP) — раньше юзер узнавал только при попытке
# стриминга. Probe — 3с timeout, чтобы не висеть на медленных сетях.
RTSP_PROBE_TIMEOUT_SEC = 3.0
_STREAM_API_TIMEOUT = ClientTimeout(total=10)


@dataclass(frozen=True)
class Go2RtcValidationResult:
    ok: bool
    error: str = ""
    rtsp_host: str | None = None


@dataclass(frozen=True)
class Go2RtcStreamInfo:
    """Sanitized producer/consumer metadata for one go2rtc stream."""

    producers: tuple[dict[str, Any], ...]
    consumer_count: int
    producer_active: bool


class Go2RtcRequestError(RuntimeError):
    """Sanitized go2rtc transport failure safe to cross module boundaries."""

    def __init__(self, operation: str, category: str) -> None:
        super().__init__(f"go2rtc {operation} failed: {category}")
        self.operation = operation
        self.category = category


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


def _parse_stream_info(payload: Any) -> Go2RtcStreamInfo | None:
    """Parse one go2rtc stream object without retaining source URLs."""
    if not isinstance(payload, dict) or not payload:
        return None
    raw_producers = payload.get("producers")
    producer_items = (
        tuple(item for item in raw_producers if isinstance(item, dict))
        if isinstance(raw_producers, list)
        else ()
    )
    producer_active = any(
        any(key != "url" for key in item) for item in producer_items
    )
    producers = tuple(
        (
            {"bytes_recv": item["bytes_recv"]}
            if isinstance(item.get("bytes_recv"), int)
            else {}
        )
        for item in producer_items
    )
    raw_consumers = payload.get("consumers")
    consumer_count = len(raw_consumers) if isinstance(raw_consumers, list) else 0
    return Go2RtcStreamInfo(
        producers=producers,
        consumer_count=consumer_count,
        producer_active=producer_active,
    )


class Go2RtcClient:
    """Sanitized transport for integration-owned operator camera streams."""

    def __init__(
        self,
        *,
        base_url: str,
        rtsp_host: str,
        session: ClientSession,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.rtsp_host = rtsp_host
        self._session = session
        self._username = username
        self._password = password
        self._headers = go2rtc_auth_headers(username, password)

    async def async_patch_stream(self, name: str, src: str) -> None:
        """Create/update an in-memory stream without destructive PUT fallback."""
        query = urlencode({"name": name, "src": src})
        url = f"{self.base_url}/api/streams?{query}"
        try:
            async with self._session.patch(
                url,
                headers=self._headers,
                timeout=_STREAM_API_TIMEOUT,
            ) as response:
                if response.status in (200, 201, 204):
                    return
                raise Go2RtcRequestError(
                    "patch", f"http_{response.status}"
                ) from None
        except Go2RtcRequestError:
            raise
        except asyncio.TimeoutError:
            raise Go2RtcRequestError("patch", "timeout") from None
        except ClientError:
            raise Go2RtcRequestError("patch", "client_error") from None

    async def async_list_streams(self) -> dict[str, Go2RtcStreamInfo]:
        """Return one sanitized snapshot of all go2rtc streams."""
        payload = await self._async_get_json(
            f"{self.base_url}/api/streams", operation="list"
        )
        if not isinstance(payload, dict):
            raise Go2RtcRequestError("list", "invalid_response") from None
        result: dict[str, Go2RtcStreamInfo] = {}
        for name, raw_info in payload.items():
            if not isinstance(name, str):
                continue
            info = _parse_stream_info(raw_info)
            if info is not None:
                result[name] = info
        return result

    async def async_get_stream(self, name: str) -> Go2RtcStreamInfo | None:
        """Return sanitized metadata for one named stream, if it exists."""
        query = urlencode({"src": name})
        payload = await self._async_get_json(
            f"{self.base_url}/api/streams?{query}", operation="get"
        )
        return _parse_stream_info(payload)

    async def async_list_preloads(self) -> set[str]:
        """Return the stable names of all active go2rtc preloads."""
        payload = await self._async_get_json(
            f"{self.base_url}/api/preload",
            operation="preload_list",
        )
        if not isinstance(payload, dict):
            raise Go2RtcRequestError(
                "preload_list", "invalid_response"
            ) from None
        return {name for name in payload if isinstance(name, str)}

    async def async_enable_preload(self, name: str) -> None:
        """Attach a persistent go2rtc consumer to a named stream."""
        await self._async_mutate_preload(
            name,
            enable=True,
        )

    async def async_disable_preload(self, name: str) -> None:
        """Remove a named preload; an already missing preload is clean."""
        await self._async_mutate_preload(
            name,
            enable=False,
        )

    async def async_delete_stream(self, name: str) -> None:
        """Delete a named stream; missing streams are already clean."""
        query = urlencode({"src": name})
        url = f"{self.base_url}/api/streams?{query}"
        try:
            async with self._session.delete(
                url,
                headers=self._headers,
                timeout=_STREAM_API_TIMEOUT,
            ) as response:
                if response.status in (200, 201, 204, 404):
                    return
                raise Go2RtcRequestError(
                    "delete", f"http_{response.status}"
                ) from None
        except Go2RtcRequestError:
            raise
        except asyncio.TimeoutError:
            raise Go2RtcRequestError("delete", "timeout") from None
        except ClientError:
            raise Go2RtcRequestError("delete", "client_error") from None

    def rtsp_url(self, name: str, *, include_credentials: bool) -> str:
        """Build a stable local RTSP URL, optionally with encoded credentials."""
        auth = ""
        if include_credentials and self._username and self._password:
            username = quote(self._username, safe="")
            password = quote(self._password, safe="")
            auth = f"{username}:{password}@"
        stream_name = quote(name, safe="")
        return f"rtsp://{auth}{self.rtsp_host}:{GO2RTC_RTSP_PORT}/{stream_name}"

    async def _async_mutate_preload(
        self,
        name: str,
        *,
        enable: bool,
    ) -> None:
        """Enable/disable preload without leaking request or response data."""
        query = urlencode({"src": name})
        url = f"{self.base_url}/api/preload?{query}"
        operation = "preload_enable" if enable else "preload_disable"
        request = self._session.put if enable else self._session.delete
        accepted = (200, 201, 204) if enable else (200, 201, 204, 404)
        try:
            async with request(
                url,
                headers=self._headers,
                timeout=_STREAM_API_TIMEOUT,
            ) as response:
                if response.status in accepted:
                    return
                raise Go2RtcRequestError(
                    operation, f"http_{response.status}"
                ) from None
        except Go2RtcRequestError:
            raise
        except asyncio.TimeoutError:
            raise Go2RtcRequestError(operation, "timeout") from None
        except ClientError:
            raise Go2RtcRequestError(operation, "client_error") from None

    async def _async_get_json(self, url: str, *, operation: str) -> Any:
        """GET JSON while preventing request/body details from escaping."""
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=_STREAM_API_TIMEOUT,
            ) as response:
                if response.status != 200:
                    raise Go2RtcRequestError(
                        operation, f"http_{response.status}"
                    ) from None
                try:
                    return await response.json()
                except (TypeError, ValueError):
                    raise Go2RtcRequestError(
                        operation, "invalid_response"
                    ) from None
        except Go2RtcRequestError:
            raise
        except asyncio.TimeoutError:
            raise Go2RtcRequestError(operation, "timeout") from None
        except ClientError:
            raise Go2RtcRequestError(operation, "client_error") from None


async def _probe_rtsp_port(host: str, port: int, timeout: float) -> bool:
    """TCP-handshake probe `host:port`. True если порт открыт.

    Используется validate_go2rtc для G-7/A-79: HTTP API может быть открыт,
    а RTSP-порт — закрыт (firewall, иной bind-address, go2rtc собран без
    RTSP-модуля). Без probe юзер обнаруживает проблему только когда
    камера не воспроизводится.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        # connection reset во время close — порт всё равно был открыт
        pass
    return True


async def validate_go2rtc(base_url: str, session: ClientSession, username: str | None = None, password: str | None = None) -> Go2RtcValidationResult:
    """
    Validate go2rtc HTTP API and that streams API is writable.

    Checks:
    1) GET  {base_url}/api -> 200
    2) PUT  {base_url}/api/streams?name=...&src=...
    3) DELETE cleanup {base_url}/api/streams?src=<name> (best-effort)
    4) TCP-probe RTSP-порта (rtsp_host, GO2RTC_RTSP_PORT) — G-7/A-79.

    Returns:
      Go2RtcValidationResult(ok, error, rtsp_host)
    """
    base_url = normalize_base_url(base_url)
    if not base_url:
        return Go2RtcValidationResult(False, "go2rtc_required_fields", None)

    rtsp_host = derive_rtsp_host(base_url)
    if not rtsp_host:
        return Go2RtcValidationResult(False, "go2rtc_invalid_url", None)

    headers = {}
    if username and password:
        userpass = f"{username}:{password}"
        b64 = base64.b64encode(userpass.encode()).decode()
        headers["Authorization"] = f"Basic {b64}"

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

    # 4) TCP-probe RTSP-порта. HTTP API мог пройти, а RTSP-порт быть
    # недоступным (firewall / отдельный bind). Делаем отдельный error key,
    # чтобы юзер сразу видел причину.
    if not await _probe_rtsp_port(rtsp_host, GO2RTC_RTSP_PORT, RTSP_PROBE_TIMEOUT_SEC):
        LOGGER.debug(
            "go2rtc RTSP probe failed: %s:%s unreachable",
            rtsp_host, GO2RTC_RTSP_PORT,
        )
        return Go2RtcValidationResult(False, "go2rtc_rtsp_port_closed", rtsp_host)

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


# ── two-way audio: per-call аудио-стрим вызова (audio-bridge-design.md) ──
# NB: консолидация go2rtc-клиента из camera.py (R1-R6) отложена — это свежие методы.
_AUDIO_STREAM_TIMEOUT = ClientTimeout(total=10)


def go2rtc_auth_headers(username: str | None, password: str | None) -> dict:
    """Basic-auth header для go2rtc (пусто, если креды не заданы)."""
    if not (username and password):
        return {}
    b64 = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {b64}"}


async def upsert_audio_stream(
    base_url: str, name: str, srcs: list[str], session: ClientSession,
    headers: dict | None = None,
) -> None:
    """Создать/обновить go2rtc стрим вызова (PATCH-first, PUT-fallback).

    `srcs` — список источников go2rtc, которые go2rtc склеивает в один стрим:
    - аудио-only: `[ffmpeg:http://<bridge>#audio=aac#audio=opus]` (мост; AAC→MSE, opus→WebRTC);
    - видео+аудио (B): `[rtsp://<rtsp_host>:8554/eg_<camera>#video=copy, <мост>]` — видео
      из RTSP уже существующего go2rtc-стрима камеры (не оператора → токен не трогаем).
    PATCH идемпотентен (не убивает producer); PUT — fallback на 4xx/5xx/ClientError.
    """
    base_url = normalize_base_url(base_url)
    qs = urlencode([("name", name), *[("src", s) for s in srcs]])
    url = f"{base_url}/api/streams?{qs}"
    h = headers or {}
    try:
        async with session.patch(url, headers=h, timeout=_AUDIO_STREAM_TIMEOUT) as resp:
            if resp.status in (200, 201, 204):
                return
    except ClientError:
        pass
    try:
        async with session.put(url, headers=h, timeout=_AUDIO_STREAM_TIMEOUT) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"go2rtc audio PUT failed: HTTP {resp.status}") from None
    except ClientError as exc:
        raise RuntimeError(f"go2rtc audio PUT failed: {type(exc).__name__}") from None


async def remove_audio_stream(
    base_url: str, name: str, session: ClientSession, headers: dict | None = None
) -> None:
    """Снять аудио-стрим вызова (best-effort) — обёртка cleanup_go2rtc_stream."""
    await cleanup_go2rtc_stream(base_url, name, session, headers)
