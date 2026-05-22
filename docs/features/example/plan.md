# Plan: Token redaction in logs

- **Date:** 2026-05-22
- **Owner:** Security & Privacy Agent
- **Linked PRD:** [`prd.md`](prd.md)
- **Linked research:** [`research.md`](research.md)

## High-level approach

Один tightly-scoped PR, который:
1. Создаёт `_logging.py` с `redact()` + `SENSITIVE_KEYS`.
2. Заменяет утечки в `http.py` и `config_flow.py`.
3. Создаёт `diagnostics.py` с `async_redact_data`.
4. Добавляет pre-commit hook.
5. Релиз `patch` с changelog «security».

Никаких side-улучшений — это hotfix, не refactor.

## Vertical slices

### Slice 1: `_logging.py` helper

- **Файлы:** `custom_components/elektronny_gorod/_logging.py` (новый).
- **Что:** `redact()` + `SENSITIVE_KEYS` (frozenset).
- **Acceptance:** unit test `test_redact_dict_with_token` зелёный.
- **Risk:** низкий.

### Slice 2: `http.py` redaction

- **Файлы:** `custom_components/elektronny_gorod/http.py`.
- **Что:**
  - `_log_request`: маскировать `headers`; не логировать `data` для auth path (whitelist).
  - `_log_response`: маскировать body для auth path.
- **Acceptance:**
  - unit test `test_log_request_redacts_authorization` зелёный.
  - `grep` через diff не находит прямых утечек.
- **Risk:** средний (touch hot path).

### Slice 3: `config_flow.py` cleanup

- **Файлы:** `custom_components/elektronny_gorod/config_flow.py`.
- **Что:**
  - удалить `LOGGER.debug("Access token is %s", ...)` на строке 77;
  - заменить `entry.data` на `entry.entry_id` в строках 283, 291;
  - logger contract обезличить на строке 201.
- **Acceptance:** grep + test config flow зелёный.
- **Risk:** низкий.

### Slice 4: `diagnostics.py`

- **Файлы:** `custom_components/elektronny_gorod/diagnostics.py` (новый).
- **Что:** `async_get_config_entry_diagnostics` через `async_redact_data`.
- **Acceptance:**
  - unit test `test_diagnostics_redacts_tokens` зелёный.
  - Manual: экспорт diagnostics через UI содержит `**REDACTED**`.
- **Risk:** низкий.

### Slice 5: Pre-commit hook

- **Файлы:** `.claude/hooks/pre-commit-redaction-check.sh`, `.claude/settings.json`.
- **Что:** bash-скрипт, блокирующий commit при прямом логировании sensitive ключей.
- **Acceptance:** ручной dry-run на staged diff с заведомой утечкой → блокирует.
- **Risk:** низкий.

## Зависимости между slices

```text
Slice 1 (helper) ─┬─► Slice 2 (http.py)
                  ├─► Slice 3 (config_flow.py)
                  └─► Slice 4 (diagnostics.py)
Slice 5 (hook)    ◄── независим, можно делать первым или последним
```

## Тесты

- `tests/test_logging_redact.py` (новый) — unit tests для `redact()`.
- `tests/test_http_redaction.py` (новый) — `_log_request`/`_log_response`.
- `tests/test_diagnostics.py` (новый) — `async_get_config_entry_diagnostics`.

См. [`docs/testing/strategy.md`](../../testing/strategy.md).

## Docs update

| Документ | Что обновить |
|---|---|
| `docs/audit/security.md` | пометить S-01..S-05, S-16 как RESOLVED |
| `docs/audit/project-audit.md` | A-01..A-04 как RESOLVED |
| `docs/architecture/overview.md` | секция логирования / diagnostics |
| `docs/roadmap.md` | Итерация 1 — частично закрыта |
| `CHANGELOG.md` | новая запись (создаётся вместе) |

## Migration plan

Не требуется — изменения не трогают entry.data структуру.

## Rollback plan

Hotfix-релиз patch+1 с revert при критическом регрессе.

## Open questions

- [ ] Финальный список `SENSITIVE_KEYS`: `operator_id` включать или нет?
- [ ] `EG_DEBUG_AUTH=1` env var override — нужен или нет?

## Quality gate

`PLAN_APPROVED` ✅
