# Conventions — `elektronny-gorod`

Конвенции проекта. Источник правил для агентов и людей. Глубокий контекст — в [`docs/`](docs/index.md).

## Архитектурные принципы

- **KISS**: одна интеграция, один кодовый модуль. Не плодить sub-packages без необходимости.
- **YAGNI**: не добавлять платформы/абстракции «на будущее». Текущие — `camera`, `lock`, `sensor`.
- **MVP-first**: лучше работающий минимум, чем красивая архитектура.
- **Spec-anchored**: значимые изменения начинаются с записи в [`docs/`](docs/index.md), а не сразу с кода.
- **Source of truth**: одно знание — один источник. Конфликты фиксировать в [`project-audit.md`](docs/audit/project-audit.md).

## Python / async

- Python 3.12+, type hints для публичных API.
- `async def` для любых I/O. Никаких `requests` / sync HTTP / `time.sleep` в event loop.
- `asyncio.sleep` допустим **только** если нет другого варианта; в идеале — таймеры HA (`async_call_later`, `async_track_time_interval`).
- Никаких новых `aiohttp.ClientSession()` — использовать `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)`.
- `traceback.format_exc()` в hot path — антипаттерн (минор). Логировать через `LOGGER.exception(...)`.

## Logging policy

🔴 **Категорически нельзя логировать** (никакого уровня, никакого формата):

- `access_token`, `refresh_token`.
- Содержимое `headers` (там Bearer).
- `password`, SMS-код.
- Полное содержимое `entry.data` / `entry.options` (там токены).
- Тело ответа на auth-endpoints (там `accessToken`/`refreshToken`).

✅ **Можно**:

- `entry.entry_id` (опрозрачный идентификатор).
- `account_id`, `subscriber_id`, `place_id` (не секретны, но обезличить желательно).
- HTTP-метод, URL без query string, статус-код, длина тела.
- Структурированные сообщения с `%`-форматированием: `LOGGER.info("Loaded %d places", n)`.

❌ **Антипаттерны**:

- `LOGGER.info(f"...{token}...")` — f-string внутри логера.
- `LOGGER.error(f"Failed: {e}")` — потеря traceback. Использовать `LOGGER.exception("Failed")`.

## Error handling

- В API-слое (`api.py`) — ловить **узкие** исключения: `aiohttp.ClientResponseError`, `aiohttp.ClientError`, `asyncio.TimeoutError`. Никаких `except Exception` без пере-`raise`.
- Не использовать `e.args[0]` для диагностики статуса — может бросить `IndexError`. Использовать атрибуты исключения.
- В `coordinator._async_update_data` — поднимать `UpdateFailed(...)` для не-fatal ошибок.
- В config-flow — возвращать `errors={key: "translation_key"}` или `async_abort(reason=...)`. Каждая `reason`/`error key` обязана быть в `strings.json`.

## Home Assistant lifecycle

- `async_setup_entry`: создать coordinator, `await coordinator.async_config_entry_first_refresh()`, форвард платформ.
- `async_unload_entry`: отгрузить платформы, вызвать `coordinator.async_unsubscribe()`, удалить из `hass.data[DOMAIN]`.
- `async_migrate_entry`: только инкремент `VERSION`. Никаких side-эффектов на сетку/API.
- Все entity должны наследовать `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]`.
- `unique_id` — стабильный: домен + place_id + sub-id, **без** локализованного `name`.
- `device_info` — обязателен для всех entity. Группировка по `place_id`.
- `_attr_has_entity_name = True` + `_attr_translation_key = "..."`. Никаких хардкод-имён по-русски.
- `iot_class` в `manifest.json` должен соответствовать реальной модели (если нет polling — не писать `cloud_polling`).

## Dependency policy

- `manifest.json:requirements` — пусто, если зависимость есть в HA core (`aiohttp`, `voluptuous`, `yarl`).
- Не добавлять зависимости ради конвенции. Каждая — ADR.
- Pin версий — только если есть конкретный bug в более новой.

## Secrets policy

- Никогда не коммитить `.env`, токены, пароли.
- Hardcoded crypto-«соль» в `helpers.py:44` — наследие reverse engineering; не наша секретная информация, но обращаться с этим участком как с legacy: не модифицировать без понимания серверного API.

## Testing expectations

- Каждый config-flow path — тест.
- Каждый migration — тест.
- Coordinator/API/go2rtc — тесты с mocked aiohttp.
- 🔴 Не «исправлять» тесты, чтобы они зелёные при сломанной фиче. Если тест падает — сначала фиксить код, потом — тест.

См. [`testing/strategy.md`](docs/testing/strategy.md).

## Documentation expectations

- README — для пользователя. Установка, настройка, примеры автоматизаций.
- Wiki (опционально) — расширенные сценарии.
- `docs/` — для разработчиков, AI-агентов, code reviewer-ов.
- Каждый AIDD-документ начинается с фронт-блока `Status / Owner / Source / Related / Used by / Gates` и заканчивается «Next reading».
- ADR — для решений, которые сложно откатить (см. `docs/decisions/`).

### Версии, SHA и другая «короткоживущая» информация

Различаем **динамическое текущее состояние** (быстро устаревает) и **статические исторические факты** (не меняются).

**Не фиксировать** (динамика):

- «**Текущая версия:** `X.Y.Z`» — устаревает с каждым релизом. Источник правды — `manifest.json`, в docs писать «см. `manifest.json`».
- «**HEAD на** `abc1234`» — устаревает с каждым коммитом.
- Имена временных веток (`feat/foo`).
- Текущее количество open issues / PR.
- Конкретные номера строк без anchor-ссылки на файл (рефакторинг сдвинет).

**Фиксировать можно** (статика):

- «**Что появилось в X.Y.Z**» — changelog-style, исторический факт, не меняется.
- «**PR #25 добавил Y**» — стабильная ссылка на закрытый PR.
- «**ADR-0003 принят `<дата>`**».
- Дата ревью документа (`Last reviewed:` во фронт-блоке).

Если нужно зафиксировать момент времени для всего документа — это поле `Last reviewed:` в шапке, **не разбрасывать SHA/версии по тексту**.

## Naming

- Файлы: `snake_case.py`.
- Классы: `PascalCase`.
- Функции/переменные: `snake_case`.
- Private: `_leading_underscore`.
- Constants: `UPPER_SNAKE_CASE` в `const.py`.
- Translation keys: `snake_case`, иерархично (`config.error.invalid_phone`).

## Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Один PR — одна логическая задача.
- Commit message объясняет «почему», а не «что» (diff показывает «что»).
- 🔴 Никаких `--no-verify`. Если pre-commit падает — фиксить причину.

## Версионирование

- SemVer: `MAJOR.MINOR.PATCH` в `manifest.json`.
- Версия обновляется через GitHub Release → workflow `release.yaml` пишет в `manifest.json` и коммитит.
- Breaking changes (config-entry migration, новые required-поля) → MAJOR bump.
