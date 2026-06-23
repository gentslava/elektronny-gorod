from __future__ import annotations

import asyncio
import uuid
import base64
from dataclasses import dataclass
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .const import GO2RTC_RTSP_PORT, LOGGER

# G-7 / A-79: TCP-probe RTSP-порта go2rtc после успешной HTTP-валидации.
# Если HTTP API открыт, а RTSP-порт закрыт (firewall, иной bind-address,
# go2rtc собран без RTSP) — раньше юзер узнавал только при попытке
# стриминга. Probe — 3с timeout, чтобы не висеть на медленных сетях.
RTSP_PROBE_TIMEOUT_SEC = 3.0


@dataclass(frozen=True)
class Go2RtcValidationResult:
    ok: bool
    error: str = ""
    rtsp_host: str | None = None


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
    base_url: str, name: str, src: str, session: ClientSession, headers: dict | None = None
) -> None:
    """Создать/обновить go2rtc аудио-стрим вызова (PATCH-first, PUT-fallback).

    PATCH идемпотентен (не убивает producer); PUT — fallback на 4xx/5xx/ClientError.
    `src` = `ffmpeg:http://<bridge>#audio=opus` (мост, D-audio-1). Креды НЕ логируем.
    """
    base_url = normalize_base_url(base_url)
    url = f"{base_url}/api/streams?{urlencode({'name': name, 'src': src})}"
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
