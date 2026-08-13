Status: Active Owner: QA Agent Last reviewed: 2026-08-11 (current diagnostics and open-trap reconciliation)

Source files:
- `custom_components/elektronny_gorod/**`
- `tests/**`

Related docs:
- `../../audit/project-audit.md`
- `../../testing/strategy.md`
- `../quality-gates.md`

Used by agents:
- Implementer, QA, Code Reviewer, Security Auditor

Quality gates:
- TESTS_PASS
- SECURITY_PRECHECK_OK

---

# Runbook: Debugging

Когда что-то странное происходит. Systematic, не угадывание.

## Принцип

> Reproduce → localize → fix → guard

Не пропускать шаги. Не «угадывать» из памяти LLM.

## Шаг 1: Reproduce

Точное описание:
- Что произошло? (с конкретными сообщениями)
- Когда? (после какого действия)
- На какой версии HA / интеграции?
- Уникально ли для одного пользователя / setup?

Источники:
- GitHub issue;
- комментарий в discord;
- собственный dev-инстанс;
- redacted config-entry diagnostics из Home Assistant.

## Шаг 2: Логирование

Включить **отладку строго для нужных модулей** в `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.elektronny_gorod: debug
    homeassistant.components.camera: info
```

> ⚠️ Перед публикацией всё равно проверьте фрагмент лога: не передавайте
> токены, пароли, SMS-коды, заголовки авторизации и персональные данные. Встроенная
> redaction закрывает известные поля интеграции, но сторонние зависимости могут
> писать собственные сообщения.

Перезапустить HA. Воспроизвести проблему. Скопировать релевантный отрезок лога.

## Шаг 3: Localize

Где именно ломается? Используйте:
- стек-трейс из лога;
- `git blame` для подозрительной строки (история обычно помогает);
- [`docs/audit/project-audit.md`](../../audit/project-audit.md) — возможно, это уже известный finding.

## Шаг 4: Hypothesis

Сформулировать гипотезу:
- «Ошибка X возникает, потому что Y».
- Какой код подтвердит / опровергнет?

Сначала гипотеза → потом fix.

## Шаг 5: Fix

- Маленький фикс (1-2 файла).
- Тест, который воспроизводит баг (red), потом fix (green).
- Не «попутный рефакторинг».
- Не «исправить» тест под сломанное поведение.

## Шаг 6: Guard

- Добавить регрессионный тест.
- Если применимо — добавить запись в `docs/audit/project-audit.md` (особенно если это P0/P1).
- Если применимо — pre-commit hook (Итерация 3) или CI-check.

## Skills для применения

- `agent-skills:debugging-and-error-recovery` — обязателен при странном поведении.
- `agent-skills:systematic-debugging` — если root cause не очевиден.
- `agent-skills:security-and-hardening` — если баг трогает auth/logs/headers.

## Антипаттерны

| Антипаттерн | Что вместо |
|---|---|
| try/except на всё подряд | Узкие исключения; не глотать ошибки |
| убрать тест, чтобы CI зелёный | Найти root cause |
| магические `sleep(1)` для гонок | `asyncio.Event` / coordinator pattern |
| `--no-verify` для commit hooks | Зафиксировать причину блокировки |
| вернуть `None` где пользователю нужна ошибка | Поднимать конкретное исключение |

## Известные ловушки этого проекта

| Симптом | Подозрительное место |
|---|---|
| FCM listener завершается и повторяет одну ошибку | внешний FCM-клиент и per-entry recovery — A-80/A-86 |
| Тесты проходят локально, падают в CI | сверить Python/HA matrix, plugins и команды с `testing/strategy.md` и CI workflow |
| Временный сбой operator GET не восстанавливается автоматически | retry/backoff ещё не реализован — остаток A-21 |
| После 401 требуется переподключение аккаунта | auto-refresh и native reauth остаются открыты — A-22/A-25 |
| VPN/WAF выглядит как пустой список камер | HTML service-pipe block маскируется generic API-ошибкой — A-92 |
| API-ошибка превращается в другой exception или пустой результат | широкие fallback-ветки — A-19/A-20 |

## Next reading

- [`../../audit/project-audit.md`](../../audit/project-audit.md) — список известных проблем
- [`testing.md`](testing.md) — как написать тест на воспроизведение
- [`../quality-gates.md`](../quality-gates.md) — что должно быть зелёным перед merge
