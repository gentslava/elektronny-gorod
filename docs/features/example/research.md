# Research: Token redaction patterns

- **Date:** 2026-05-22
- **Owner:** Security & Privacy Agent
- **Linked PRD:** [`prd.md`](prd.md)

## Вопросы

1. Как HA core / другие custom integrations делают redaction?
2. Какие keys считаются sensitive в community?
3. Безопасно ли использовать `logging.Filter` или лучше явный redact?

## Источники

| Источник | Trust | Что взято |
|---|---|---|
| HA developer docs — Diagnostics | high | `async_redact_data` API |
| HA core — `homeassistant.components.diagnostics.util` | high | Реальная реализация redact |
| Несколько core integrations (e.g. `hassio`, `nest`) | high | Примеры `TO_REDACT` |
| OWASP Logging cheat sheet | medium | Принципы redaction |

## Что нашли

### 1. `homeassistant.components.diagnostics.util.async_redact_data`

```python
from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = {"access_token", "refresh_token", "password"}

async def async_get_config_entry_diagnostics(hass, entry):
    return async_redact_data(entry.as_dict(), TO_REDACT)
```

Доступно из HA core, не требует доп. зависимостей. Reцивно обходит dict/list, заменяет значения по ключам на `"**REDACTED**"`.

### 2. Phylosophy в core integrations

`TO_REDACT` всегда включает:
- `access_token`, `refresh_token`;
- `api_key`, `token`, `password`, `pin`;
- `latitude`/`longitude` (PII).

Иногда — credentials provider-specific (`unique_id` если он содержит email).

### 3. Logging vs Diagnostics

Diagnostics — это **только** при экспорте через UI/API. Logging — отдельная история: `logging.Filter` или явный `redact()` перед `LOGGER.*`.

Для проекта **обе** меры обязательны.

## Применимо к нам?

- ✅ Использовать `async_redact_data` для diagnostics.py.
- ✅ Свой `redact()` для logging path.
- ✅ Не выдумывать структуру `TO_REDACT` — взять стандартный набор + наши специфичные (`go2rtc_password`, `user_agent`).

## Risk / unknowns

- ⚠️ `user_agent` в наших entries содержит `account_id` — нестандартно. Зачем-то его нужно либо redact, либо разделить на части.
- ⚠️ `operator_id` — не секретный, но идентифицирующий. Включать ли в redact? По умолчанию — да, в diagnostics, нет — в логах (полезен для debug).

## Рекомендация

1. Использовать готовый `async_redact_data` HA core для diagnostics.
2. Свой `redact()` для логов:
   ```python
   def redact(value, keys=SENSITIVE_KEYS):
       if isinstance(value, dict):
           return {k: ("***" if k.lower() in keys else redact(v)) for k, v in value.items()}
       if isinstance(value, list):
           return [redact(v) for v in value]
       return value
   ```
3. `SENSITIVE_KEYS` — frozenset, источник правды в `_logging.py`.
4. Pre-commit hook через grep.

## Quality gate

`RESEARCH_DONE` ✅
