# PRD: Token redaction in logs

- **Date:** 2026-05-22
- **Last reviewed:** 2026-08-11
- **Owner:** Security & Privacy Agent
- **Status:** Approved (для example — синтетически)
- **Linked idea:** [`idea.md`](idea.md)

## Problem

Это синтетический пример PRD по уже закрытому инциденту ADR-0004. До фикса при
debug-логировании были зафиксированы четыре класса утечек:

- raw `access_token` из config flow;
- HTTP headers с Bearer и auth payload с password/SMS;
- body auth-ответа с новыми токенами;
- полный `config_entry.data`.

Это историческое описание, а не характеристика текущего кода. Актуальные
evidence и статус принадлежат [`security.md`](../../audit/security.md).

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
- Canonical scanner `.codex/hooks/check-secret-logs.py` с portable shell
  wrapper и thin tool-specific adapters.

См. [ADR-0004](../../decisions/0004-token-redaction.md).

## Acceptance criteria

- [ ] `bash .codex/hooks/check-secret-logs.sh` → `Secret log scan passed`.
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
