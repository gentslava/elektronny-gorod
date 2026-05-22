# GitHub Copilot — instructions for `elektronny-gorod`

Home Assistant custom integration для российских операторов «Электронный город» (Новотелеком) и «Дом.ру».

## Обязательное чтение

- `AGENTS.md`
- `conventions.md`
- `docs/index.md`

## Правила, которые ВЫ должны соблюдать

### 1. Безопасность секретов

🔴 **Никогда** не предлагать код, который логирует:
- `access_token`, `refresh_token`, `accessToken`, `refreshToken`
- `password`, SMS-код
- `headers` целиком (там Bearer)
- `entry.data`, `entry.options` целиком
- Тело auth-ответов
- `go2rtc_password`, `go2rtc_username`

### 2. HTTP-сессии

- Только `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)`.
- 🔴 Не предлагать `aiohttp.ClientSession()` напрямую.

### 3. Entity / coordinator

- Entity должны наследовать `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]` (когда [ADR-0002](../docs/decisions/0002-coordinator-pattern.md) реализован).
- `unique_id` — без локализованных имён.
- `_attr_has_entity_name = True` + `_attr_translation_key`.

### 4. Logging

- `%`-форматирование, не f-strings внутри `LOGGER.*`.
- `LOGGER.exception(...)` для error c traceback.

### 5. Async

- `async def` для I/O.
- Никаких блокирующих операций в event loop.
- `ClientTimeout(total=N)` на запросах.

### 6. Tests

- Реальные тесты, не stub.
- Mock через `aioresponses` + `pytest-homeassistant-custom-component`.
- Не «исправлять» тест ради зелёного CI.

### 7. Документация

- При изменении кода предлагать обновление соответствующих документов в `docs/`.
- Maintenance rules — в `docs/project/project-map.md`.

## Структура

```
custom_components/elektronny_gorod/    — основной код
tests/                                  — тесты (сейчас stub)
docs/                                   — AIDD-документация
.github/workflows/                      — CI
.claude/                                — конфигурация Claude Code
.cursor/rules/                          — правила Cursor
```

## Целевые версии

- Python 3.12+
- Home Assistant ≥ значения из `hacs.json` (проверять перед использованием новой HA API)

## Что не предлагать

- Конкретные номера версий в текстах документации (только в changelog).
- SHA коммитов в текстах.
- Magic strings в коде (выносить в `const.py`).
- f-string внутри `LOGGER.*`.
- `import base64` (и аналогичных) внутри методов.

## См. также

- [`docs/audit/project-audit.md`](../docs/audit/project-audit.md) — все известные проблемы и их статус.
- [`docs/roadmap.md`](../docs/roadmap.md) — план изменений.
- [`docs/aidd/contributing.md`](../docs/aidd/contributing.md) — как корректно вносить вклад через AI.
