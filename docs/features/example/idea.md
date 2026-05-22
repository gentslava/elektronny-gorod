# Idea: Token redaction in logs

- **Date:** 2026-05-22
- **Source:** AIDD audit (S-01..S-05)
- **Owner:** Security & Privacy Agent

## Что предлагается

Перестать логировать секреты (access_token, refresh_token, headers с Bearer, тело auth-ответов, entry.data) в `home-assistant.log`. Заменить на redact-helper + diagnostics.py.

## Почему

Любой пользователь с `logger: default: debug` сегодня сливает свой токен в файл лога. Токен даёт полный доступ к камерам/замкам/балансу.

## Кому это нужно

Всем пользователям интеграции. Никто не должен делиться `home-assistant.log` с риском утечки контроля над домофоном.

## Альтернативы

- Просто удалить лог-строки → потеряем диагностику.
- Использовать HA `Store` шифрование → не помогает с runtime-логами.
- Не делать ничего → P0 риск.

## Что НЕ входит

- Refactor crypto в `helpers.py` (это не утечка, а наследие API).
- Encryption-at-rest для `entry.data` (HA core уже шифрует `.storage/*`).

## Следующий шаг

- [x] PRD создан → [`prd.md`](prd.md)
- [ ] Research → [`research.md`](research.md)
- [ ] Plan → [`plan.md`](plan.md)
- [ ] Реализация в Итерации 1

## Quality gate

`IDEA_CAPTURED` ✅
