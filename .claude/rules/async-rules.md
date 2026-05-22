# Rule: Async / IO

**Применимо к:** `custom_components/elektronny_gorod/**.py`.

## Правила

### Async-first

- Все I/O операции — `async def`.
- Никаких `requests`, `urllib`, `time.sleep`, синхронных файловых операций в event loop.
- `asyncio.sleep` допустим **только** если нет другого варианта; в идеале — таймеры HA (`async_call_later`, `async_track_time_interval`).

### HTTP

- `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` — единственный способ создать сессию.
- 🔴 Запрещено `aiohttp.ClientSession()` напрямую (см. `audit/project-audit.md` A-05).
- `ClientTimeout(total=N)` на каждом запросе.

### Exceptions

- В `api.py` — узкие исключения: `aiohttp.ClientResponseError`, `aiohttp.ClientError`, `asyncio.TimeoutError`.
- Никаких `except Exception` без явной re-raise.
- `e.args[0]` — антипаттерн (может бросить `IndexError`). Использовать `response.status` атрибуты.

### Coordinator

- `_async_update_data` → `UpdateFailed(...)` для не-fatal ошибок.
- 🔴 Не блокировать event loop через `traceback.format_exc()` в hot path — использовать `LOGGER.exception(...)`.

### Lock-state

- Никаких `asyncio.sleep` для имитации lock-cycle (см. ADR-0005, lock.py:113-120).
- Состояние — из coordinator.data, не синтетическое.

### Parallel

- Использовать `asyncio.gather` для независимых запросов в coordinator (places per N → cameras + locks + balances параллельно).
- Внимание к rate-limits — exponential backoff на 429.

## Связь

- docs/architecture/overview.md (async patterns)
- ADR-0002 (coordinator pattern)
- ADR-0005 (lock vs button)
- audit A-05, A-08, A-15, A-19, A-20, A-21
