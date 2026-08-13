# Rule: No secret logs

**Last reviewed:** 2026-08-11 (canonical AST gate)

**Применимо к:** `custom_components/elektronny_gorod/**.py`

## Правило

🔴 Запрещено логировать (на любом уровне `debug`/`info`/`warning`/`error`):

- `access_token`, `refresh_token`, `accessToken`, `refreshToken`.
- `password`, SMS-код.
- Полные `headers` (там Bearer).
- Полные `entry.data` / `entry.options`.
- Тело auth-response.
- `go2rtc_username` / `go2rtc_password`.

## Что МОЖНО логировать

- `entry.entry_id`.
- `account_id`, `subscriber_id`, `place_id` (PII, но не секреты — используйте обдуманно).
- HTTP метод + URL без query string + статус-код + длина body.
- Структурированные сообщения с `%`-форматированием.

## Как фиксить

```python
# ❌ ПЛОХО
LOGGER.debug("Access token is %s", token)
LOGGER.info(f"Headers: {headers}")
LOGGER.info("Entry %s exists", entry.data)

# ✅ ХОРОШО
# Просто не логировать токен.
from ._logging import redact
LOGGER.info("Headers: %s", redact(headers))
LOGGER.info("Entry %s exists", entry.entry_id)
```

## Где `_logging.py`

Реализован в `custom_components/elektronny_gorod/_logging.py`; контракт зафиксирован в [`docs/decisions/0004-token-redaction.md`](../../docs/decisions/0004-token-redaction.md).

## Pre-commit hook

`.claude/hooks/post-edit-redaction-check.sh` и Codex-адаптер делегируют единой AST-проверке `.codex/hooks/check-secret-logs.py`. Единый worktree-aware entrypoint `bash .codex/hooks/check-secret-logs.sh` сам выбирает проектный Python 3.12+.

## Связь

- ADR-0004
- audit/security.md (S-01..S-05, S-16)
- audit/project-audit.md (A-01..A-04)
