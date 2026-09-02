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

from aiohttp import ClientError, ClientTimeout, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ForpostDownloadError
from .const import DOMAIN, LOGGER

_SECRET_KEY = f"{DOMAIN}_clip_signing_secret"
_VIEW_REGISTERED = f"{DOMAIN}_clip_view_registered"
_TOKEN_TTL = 600.0
_CHUNK_SIZE = 64 * 1024

# ErrorCode 102 / HTTP 423: оператор готовит mp4 (mint и storage-слой).
_ERROR_PREPARING = "102"
_HTTP_LOCKED = 423
# Приложение опрашивает подготовку с нарастающей паузой ~1/2/3/4 с
# (снимок 2026-05-25), а не с фиксированной: первая попытка идёт раньше,
# поэтому готовый раньше файл подхватывается быстрее.
_DOWNLOAD_PREPARE_BACKOFF = (1.0, 2.0, 3.0, 4.0)
_DOWNLOAD_PREPARE_BUDGET = 30.0


def _prepare_delay(attempt: int) -> float:
    """Пауза перед попыткой `attempt` (0-based); дальше — последняя из ряда."""
    index = min(attempt, len(_DOWNLOAD_PREPARE_BACKOFF) - 1)
    return _DOWNLOAD_PREPARE_BACKOFF[index]

_CACHE_KEY = f"{DOMAIN}_clip_cache"
_LOCKS_KEY = f"{DOMAIN}_clip_locks"
_SEMAPHORE_KEY = f"{DOMAIN}_clip_downloads"
# Клип живёт ровно столько же, сколько ссылка на него: пока токен валиден,
# перемотка обслуживается из кеша и не трогает оператора.
_CACHE_TTL = _TOKEN_TTL
# 30-секундный ролик ≈ 4.4 МБ (снимок 2026-05-25), события бывают до ~134 с.
# Клип крупнее лимита не кешируется вовсе — иначе один ролик вытеснил бы всё
# остальное и занимал память до конца TTL.
_CLIP_MAX_BYTES = 32 * 1024 * 1024
_CACHE_MAX_BYTES = 128 * 1024 * 1024
# Резидентный кеш — не единственный расход: каждая загрузка держит ещё и свой
# буфер. Ограничиваем число одновременных, иначе пик кратно превышает бюджет.
_MAX_CONCURRENT_DOWNLOADS = 2
_UPSTREAM_TIMEOUT = ClientTimeout(total=120, sock_connect=10, sock_read=30)


class _CachedClip:
    """Готовый mp4 в памяти: источник для наших собственных 206-ответов."""

    __slots__ = ("data", "created")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.created = time.monotonic()

    @property
    def expired(self) -> bool:
        return time.monotonic() - self.created > _CACHE_TTL


def _cache_key(entry_id: str, event_id: str) -> tuple[str, str]:
    """Ключ кеша включает entry: event_id уникален лишь в рамках аккаунта."""
    return (entry_id, event_id)


def _cache_get(
    hass: HomeAssistant, entry_id: str, event_id: str
) -> _CachedClip | None:
    cache: dict[tuple[str, str], _CachedClip] = hass.data.get(_CACHE_KEY) or {}
    key = _cache_key(entry_id, event_id)
    clip = cache.get(key)
    if clip is None:
        return None
    if clip.expired:
        cache.pop(key, None)
        return None
    return clip


def _cache_put(
    hass: HomeAssistant, entry_id: str, event_id: str, data: bytes
) -> _CachedClip:
    cache: dict[tuple[str, str], _CachedClip] = hass.data.setdefault(_CACHE_KEY, {})
    for stale in [key for key, clip in cache.items() if clip.expired]:
        cache.pop(stale, None)
    # Локи не снимаются на выходе из загрузки: выдернуть объект из словаря,
    # пока на нём кто-то ждёт, значит развести ждущего и новичка по разным
    # локам и запустить две загрузки. Вместо этого подметаем свободные.
    locks: dict[tuple[str, str], asyncio.Lock] = hass.data.get(_LOCKS_KEY) or {}
    for idle in [key for key, lock in locks.items() if not lock.locked()]:
        locks.pop(idle, None)
    clip = _CachedClip(data)
    if len(data) > _CACHE_MAX_BYTES:
        # Не кешируем: иначе бюджет был бы превышен самим этим клипом.
        return clip
    cache[_cache_key(entry_id, event_id)] = clip
    # Вытесняем самые старые, пока не уложимся в бюджет памяти.
    while sum(len(item.data) for item in cache.values()) > _CACHE_MAX_BYTES:
        oldest = min(cache, key=lambda key: cache[key].created)
        cache.pop(oldest, None)
    return clip


@callback
def async_release_clip_cache(hass: HomeAssistant, entry_id: str) -> None:
    """Забыть клипы и локи выгружаемого entry, не дожидаясь TTL."""
    cache: dict[tuple[str, str], _CachedClip] = hass.data.get(_CACHE_KEY) or {}
    for key in [key for key in cache if key[0] == entry_id]:
        cache.pop(key, None)
    locks: dict[tuple[str, str], asyncio.Lock] = hass.data.get(_LOCKS_KEY) or {}
    for key in [key for key in locks if key[0] == entry_id]:
        locks.pop(key, None)


_RANGE_IGNORE = "ignore"
_RANGE_UNSATISFIABLE = "unsatisfiable"


def _parse_range(header: str, total: int) -> tuple[int, int] | str:
    """Разобрать один byte-range.

    RFC 9110 §14.2 различает два случая, и путать их нельзя: неразбираемый
    или неизвестный по единице заголовок **игнорируется** (отдаём 200
    целиком), а 416 положен только синтаксически корректному, но
    неудовлетворимому диапазону.

    Несколько диапазонов не поддерживаем: браузерные плееры их не шлют, а
    multipart/byteranges пришлось бы собирать вручную — такой заголовок
    тоже игнорируем.
    """
    spec = header.strip()
    unit, sep, rest = spec.partition("=")
    if unit.strip().lower() != "bytes" or not sep or "," in rest:
        return _RANGE_IGNORE
    first, dash, last = rest.strip().partition("-")
    if not dash:
        return _RANGE_IGNORE
    try:
        if not first:
            if not last:
                return _RANGE_IGNORE
            suffix = int(last)
            if suffix <= 0:
                return _RANGE_UNSATISFIABLE
            return max(total - suffix, 0), total - 1
        start = int(first)
        end = int(last) if last else total - 1
    except ValueError:
        return _RANGE_IGNORE
    if start > end or start >= total:
        return _RANGE_UNSATISFIABLE
    return start, min(end, total - 1)


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
    """Serve one operator clip as same-origin, range-capable video/mp4."""

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

        clip = _cache_get(hass, entry_id, event_id)
        if clip is None:
            # Один клип готовится один раз: параллельные range-запросы
            # браузера ждут первую загрузку, а не плодят минты.
            locks: dict[tuple[str, str], asyncio.Lock] = hass.data.setdefault(
                _LOCKS_KEY, {}
            )
            key = _cache_key(entry_id, event_id)
            lock = locks.setdefault(key, asyncio.Lock())
            async with lock:
                clip = _cache_get(hass, entry_id, event_id)
                if clip is None:
                    clip_or_error = await self._download(
                        hass, coordinator, entry_id, event_id
                    )
                    if isinstance(clip_or_error, web.Response):
                        return clip_or_error
                    clip = clip_or_error
        return await self._serve(request, clip)

    async def _download(
        self, hass: HomeAssistant, coordinator: Any, entry_id: str, event_id: str
    ) -> _CachedClip | web.Response:
        """Mint once, wait for the operator, then fetch the whole file.

        Так делает мобильное приложение (снимок 2026-05-25): один минт, затем
        GET той же ссылки до готовности и скачивание целиком. Повторный минт
        запускает подготовку заново, поэтому ссылка минтится ровно один раз.
        """
        session = async_get_clientsession(hass)
        semaphore: asyncio.Semaphore = hass.data.setdefault(
            _SEMAPHORE_KEY, asyncio.Semaphore(_MAX_CONCURRENT_DOWNLOADS)
        )
        deadline = time.monotonic() + _DOWNLOAD_PREPARE_BUDGET
        attempt = 0
        while True:
            try:
                source_url = await coordinator.api.query_event_download(event_id)
            except ForpostDownloadError as err:
                if err.error_code == _ERROR_PREPARING:
                    if time.monotonic() >= deadline:
                        return self.json_message(
                            "Recording is being prepared, try again shortly", 503
                        )
                    await asyncio.sleep(_prepare_delay(attempt))
                    attempt += 1
                    continue
                # Пользователь увидит лишь ошибку плеера: маппинг кода
                # оператора остаётся здесь единственным следом.
                # str(err) несёт уже санированный код: сырой error_code
                # приходит из JSON оператора и может содержать переводы
                # строк, то есть подделку записей журнала.
                LOGGER.warning(
                    "Clip proxy: оператор отказал в записи event_id=%s (%s)",
                    event_id,
                    err,
                )
                return self.json_message("Recording is not available", 404)
            except Exception as ex:  # noqa: BLE001 - operator boundary
                LOGGER.debug(
                    "Clip proxy download failed for event_id=%s (%s)",
                    event_id,
                    type(ex).__name__,
                )
                return self.json_message("Archive is temporarily unavailable", 502)
            break

        # source_url — подписанный операторский link; никогда не логируется.
        # Range наверх не шлём: приложение его не использует, а storage не
        # анонсирует Accept-Ranges — диапазоны нарезаем сами из кеша.
        attempt = 0
        async with semaphore:
            while True:
                try:
                    upstream = await session.get(
                        source_url, timeout=_UPSTREAM_TIMEOUT
                    )
                except (ClientError, ValueError) as ex:
                    LOGGER.debug(
                        "Clip proxy upstream failed for event_id=%s (%s)",
                        event_id,
                        type(ex).__name__,
                    )
                    return self.json_message("Archive is temporarily unavailable", 502)
                if upstream.status == _HTTP_LOCKED:
                    upstream.release()
                    LOGGER.debug(
                        "Clip proxy storage preparing event_id=%s — waiting",
                        event_id,
                    )
                    if time.monotonic() >= deadline:
                        return self.json_message(
                            "Recording is being prepared, try again shortly", 503
                        )
                    await asyncio.sleep(_prepare_delay(attempt))
                    attempt += 1
                    continue
                if upstream.status != 200:
                    upstream.close()
                    LOGGER.debug(
                        "Clip proxy upstream rejected event_id=%s (status=%s)",
                        event_id,
                        upstream.status,
                    )
                    return self.json_message("Archive is temporarily unavailable", 502)
                declared = upstream.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > _CLIP_MAX_BYTES:
                    upstream.close()
                    LOGGER.debug(
                        "Clip proxy refused oversized event_id=%s (%s bytes)",
                        event_id,
                        declared,
                    )
                    return self.json_message("Recording is too large to play", 502)
                # Читаем чанками с контролем размера: bare read() принял бы тело
                # любой длины и раздул бы процесс до OOM.
                buffer = bytearray()
                try:
                    async for chunk in upstream.content.iter_chunked(_CHUNK_SIZE):
                        buffer.extend(chunk)
                        if len(buffer) > _CLIP_MAX_BYTES:
                            LOGGER.debug(
                                "Clip proxy aborted oversized event_id=%s", event_id
                            )
                            return self.json_message(
                                "Recording is too large to play", 502
                            )
                except (ClientError, ConnectionResetError) as ex:
                    LOGGER.debug(
                        "Clip proxy read failed for event_id=%s (%s)",
                        event_id,
                        type(ex).__name__,
                    )
                    return self.json_message("Archive is temporarily unavailable", 502)
                finally:
                    upstream.close()
                data = bytes(buffer)
                if not data:
                    # Пустое тело нельзя кешировать: следующие 10 минут
                    # клип отдавался бы нулевой длины без пути к оператору.
                    LOGGER.debug(
                        "Clip proxy got an empty body for event_id=%s", event_id
                    )
                    return self.json_message(
                        "Archive is temporarily unavailable", 502
                    )
                LOGGER.debug(
                    "Clip proxy cached event_id=%s (%s bytes)", event_id, len(data)
                )
                return _cache_put(hass, entry_id, event_id, data)

    async def _serve(
        self, request: web.Request, clip: _CachedClip
    ) -> web.StreamResponse:
        """Answer from cache with real byte-range support.

        Перемотка в `<video>` включается только когда ресурс отвечает 206 на
        Range либо анонсирует Accept-Ranges. Оператор ничего из этого не
        отдаёт, поэтому диапазоны обслуживаем сами.
        """
        total = len(clip.data)
        range_header = request.headers.get("Range")
        start, end = 0, total - 1
        status = 200
        if range_header:
            parsed = _parse_range(range_header, total)
            if parsed == _RANGE_UNSATISFIABLE:
                stream = web.Response(status=416)
                stream.headers["Content-Range"] = f"bytes */{total}"
                stream.headers["Accept-Ranges"] = "bytes"
                return stream
            if parsed != _RANGE_IGNORE:
                start, end = parsed
                status = 206
        # memoryview, а не срез: иначе каждый seek копировал бы кусок целиком,
        # а стартовый `bytes=0-` — весь клип, на каждого зрителя.
        body = memoryview(clip.data)[start : end + 1]
        stream = web.StreamResponse(status=status)
        stream.headers["Content-Type"] = "video/mp4"
        stream.headers["Accept-Ranges"] = "bytes"
        stream.headers["Content-Length"] = str(len(body))
        # URL несёт токен: reverse proxy не должен оставлять тело у себя и
        # отдавать его после того, как токен протух.
        stream.headers["Cache-Control"] = "private, no-store"
        if status == 206:
            stream.headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        try:
            await stream.prepare(request)
            for offset in range(0, len(body), _CHUNK_SIZE):
                await stream.write(body[offset : offset + _CHUNK_SIZE])
        except (ClientError, ConnectionResetError):
            return stream
        return stream
