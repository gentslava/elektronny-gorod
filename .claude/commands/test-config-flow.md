---
description: Сгенерировать или дополнить тесты config_flow по плану docs/testing/strategy.md.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

Ты — QA Engineer. Активируй skill `agent-skills:test-driven-development`.

## Контекст

`tests/test_config_flow.py` — нерабочий stub из HA scaffold (см. audit A-07). Нужно полностью переписать по плану из `docs/testing/strategy.md` раздел 1.

## Шаги

1. Прочитай `custom_components/elektronny_gorod/config_flow.py` — все steps, errors, aborts.
2. Прочитай `docs/testing/strategy.md` (раздел 1. Config flow) — list test cases.
3. Прочитай `docs/aidd/runbooks/testing.md` — mock стратегия + пример теста.
4. Удали существующий нерабочий `tests/test_config_flow.py` (или замени его содержимое).
5. Напиши тесты в порядке:
   - happy path: phone+SMS+skip_go2rtc
   - happy path: phone+password+skip_go2rtc
   - happy path: access_token (advanced) + skip_go2rtc
   - happy path: with go2rtc setup
   - error: invalid_phone, unregistered, invalid_login, invalid_password, invalid_code, limit_exceeded
   - abort: already_configured (duplicate token)
   - abort: reauth_successful (account+subscriber match)
6. Запусти `pytest tests/test_config_flow.py -v` — должно быть зелёным.
7. Если тест падает по непонятной причине — root cause через `agent-skills:debugging-and-error-recovery`. **Не упрощать тест.**

## Output

```md
## Done
- N тестов добавлено
- coverage config_flow: a% → b%

## Verification
- `pytest tests/test_config_flow.py -v` — passed N/N

## Caught bugs (если были)
- F-NN: description, evidence, severity

## Hand-off
- next: docs-keeper (обновить testing/strategy.md как RESOLVED)
```

## Constraints

- 🔴 НЕ исправлять тест ради зелёного CI, если код сломан.
- НЕ использовать реальный API оператора.
- НЕ оставлять `print()` / `debugger`.
- НЕ импортировать несуществующие сущности (как в текущем stub).
