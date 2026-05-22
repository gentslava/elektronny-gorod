# PRD: Token redaction in logs

- **Date:** 2026-05-22
- **Owner:** Security & Privacy Agent
- **Status:** Approved (для example — синтетически)
- **Linked idea:** [`idea.md`](idea.md)

## Problem

При уровне `logger: default: debug` все ниже строки сливают секреты пользователя:

- [`config_flow.py:77`](../../../custom_components/elektronny_gorod/config_flow.py#L77) — `access_token` напрямую.
- [`http.py:11-13`](../../../custom_components/elektronny_gorod/http.py#L11-L13) — `headers` (Bearer) + `data` (password/SMS).
- [`http.py:22-25`](../../../custom_components/elektronny_gorod/http.py#L22-L25) — body auth-ответа (новые токены).
- [`config_flow.py:283,291`](../../../custom_components/elektronny_gorod/config_flow.py#L283) — `entry.data` целиком.

Evidence — issue + аудит [`security.md`](../../audit/security.md).

## Users

- Все пользователи интеграции (ничего хорошего не получают, защищены от утечки).
- Особенно — те, кто делится логом/diagnostics в issue или Discord.

## Goals

1. Никакие секреты не попадают в `home-assistant.log` ни при каком уровне логирования.
2. Diagnostics-выгрузка не содержит токенов / паролей.
3. Pre-commit hook предотвращает регрессии.

## Non-goals

- Не делаем шифрование `entry.data` в `.storage/`.
- Не меняем crypto в `helpers.py`.

## Solution

- Создать `_logging.py` с `redact()` helper и `SENSITIVE_KEYS`.
- Заменить все прямые логи токенов на `redact(headers/data)` либо удалить.
- Создать `diagnostics.py` с `TO_REDACT = SENSITIVE_KEYS`.
- Hook `.claude/hooks/pre-commit-redaction-check.sh`.

См. [ADR-0004](../../decisions/0004-token-redaction.md).

## Acceptance criteria

- [ ] `grep -rE "LOGGER\..*(token|password|sms|headers|entry\.data)" custom_components/` → 0 matches.
- [ ] Diagnostics-выгрузка через UI содержит `"***"` вместо реальных токенов.
- [ ] Pre-commit hook блокирует регрессии.
- [ ] Hotfix-релиз с changelog «security: redact tokens in logs» опубликован.

## Затронутые модули

- `custom_components/elektronny_gorod/_logging.py` (новый).
- `custom_components/elektronny_gorod/diagnostics.py` (новый).
- `custom_components/elektronny_gorod/http.py`.
- `custom_components/elektronny_gorod/config_flow.py`.

## Влияние на existing entries

Никакого. Не трогаем `entry.data` / VERSION.

## Влияние на HA QS

- Закрывает security blocker для Bronze (диагностика).

## Открытые вопросы

- [ ] Делать ли redaction опциональным через `EG_DEBUG_AUTH=1` env var (ADR-0004 предлагает) — нужен feedback owner.

## Quality gate

`SPEC_READY` ✅
