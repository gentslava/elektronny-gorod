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
- diagnostics (когда появится).

## Шаг 2: Логирование

Включить **отладку строго для нужных модулей** в `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.elektronny_gorod: debug
    homeassistant.components.camera: info
```

> ⚠️ Включая debug, **временно** позволяете утечку токенов в лог (до hotfix-релиза). Не делиться этим логом без redaction.

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
| Camera shows unavailable несмотря на live stream | `coordinator.update_camera_state` — A-06 (баг `c.get("ID")`) |
| Тесты «работают» в IDE, падают в CI | `tests/test_config_flow.py` stub (A-07) — реальных тестов нет |
| После reload интеграции теряется список устройств | `coordinator._async_update_data` — A-08 (нет update_interval) |
| go2rtc 401 несмотря на правильные URL/username/password | проверить, не залогирован ли заголовок Authorization (S-02) |
| Балансы «застряли» | A-08 + A-09 (нет CoordinatorEntity) |

## Next reading

- [`../../audit/project-audit.md`](../../audit/project-audit.md) — список известных проблем
- [`testing.md`](testing.md) — как написать тест на воспроизведение
- [`../quality-gates.md`](../quality-gates.md) — что должно быть зелёным перед merge
