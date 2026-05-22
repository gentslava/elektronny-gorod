# ADR-0004: Token redaction в логах

- **Status:** proposed
- **Date:** 2026-05-22
- **Owner:** Security & Privacy Agent

## Context

Аудит выявил утечки секретов в логи (см. [`audit/security.md`](../audit/security.md) S-01..S-05, S-16):

- Access token логируется явно ([`config_flow.py:77`](../../custom_components/elektronny_gorod/config_flow.py#L77)).
- Headers с `Authorization: Bearer <token>` логируются ([`http.py:13`](../../custom_components/elektronny_gorod/http.py#L13)).
- Request `data` для auth-endpoints (password/SMS) логируется ([`http.py:13`](../../custom_components/elektronny_gorod/http.py#L13)).
- Response body на DEBUG содержит accessToken/refreshToken ([`http.py:22-25`](../../custom_components/elektronny_gorod/http.py#L22-L25)).
- `entry.data` целиком ([`config_flow.py:283,291`](../../custom_components/elektronny_gorod/config_flow.py#L283)).
- `go2rtc_password` хранится в `entry.data` plaintext (S-16).

Это **P0**: любой пользователь с `logger: default: debug` сегодня сливает токены в `home-assistant.log`.

## Decision

Принять **redaction strategy** для логов и diagnostics:

### 1. Sensitive keys

Зафиксированный список (источник правды — это ADR):

```python
SENSITIVE_KEYS = frozenset({
    "access_token",
    "refresh_token",
    "accessToken",       # camelCase из API
    "refreshToken",
    "password",
    "go2rtc_password",
    "go2rtc_username",   # username тоже PII в этом контексте
    "user_agent",        # содержит account_id
    "authorization",     # header
})
```

### 2. Helper-функция

```python
def redact(value, keys=SENSITIVE_KEYS):
    """Заменить значения sensitive-ключей на '***'."""
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in keys else redact(v, keys)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, keys) for v in value]
    return value
```

Расположение: `custom_components/elektronny_gorod/_logging.py` (новый файл).

### 3. Логирование

- **Никогда** не передавать токены/headers/entry.data напрямую в `LOGGER.*`.
- Использовать `redact(...)` для любых dict/headers, попадающих в логи.
- Для request body на auth-endpoints — **не логировать вовсе** (whitelist путей).

### 4. Diagnostics

Создать `diagnostics.py` с `TO_REDACT = SENSITIVE_KEYS`. Использовать `homeassistant.components.diagnostics.async_redact_data`.

### 5. Pre-commit hook

`.claude/hooks/pre-commit-redaction-check.sh`:

```bash
#!/usr/bin/env bash
# Блокирует commit, если в diff есть прямое логирование sensitive-ключей.
if git diff --cached --unified=0 -- 'custom_components/elektronny_gorod/*.py' \
   | grep -E '^\+.*LOGGER\.[a-z]+\(.*(access_token|refresh_token|password|headers|entry\.data|self\.access_token)' \
   | grep -v '#.*safe'; then
    echo "❌ Direct logging of secrets detected. Use redact() helper or remove."
    exit 1
fi
```

## Consequences

### Positive

- Закрывает P0 утечки одной серией правок.
- Hook предотвращает регрессии.
- Diagnostics — безопасный для пользователя экспорт.
- Соответствует HA best practices (`async_redact_data`).

### Negative

- Отладка чуть менее удобна (не видно тело auth-ответа в debug).
- Pre-commit hook добавляет ~100ms на каждый commit.

### Mitigation

- Для локальной отладки разработчика — env var `EG_DEBUG_AUTH=1`, который явно отключает redaction. Никогда не коммитить с этим.

## Alternatives considered

1. **Просто удалить лог-строки.** Отклонено — теряем диагностику; redaction оставляет полезную информацию (status, длина).
2. **Использовать HA `Store` с pin-кодом для токенов.** Отклонено как избыточное — HA core уже шифрует `.storage/*` per-install.
3. **Не делать pre-commit hook.** Отклонено — это P0, регрессии слишком вероятны.

## Supersedes / Superseded by

— (новое)

## Notes

- См. [`docs/audit/security.md`](../audit/security.md) S-01..S-16.
- Изменения в `manifest.json` не требуются.
- Существующие пользователи: рекомендовать **перевыпуск access_token** (через UI config flow → re-authenticate), если они когда-либо имели включён `debug` уровень и/или делились логами/diagnostics.
