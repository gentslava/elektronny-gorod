---
name: "source-command-test-config-flow"
description: "Сгенерировать или дополнить тесты config_flow по плану docs/testing/strategy.md."
---

# source-command-test-config-flow

Use this skill when the user asks to run the migrated source command `test-config-flow`.

## Command Template

Ты — QA Engineer. Активируй skill `test-driven-development`.

## Контекст

`tests/test_config_flow.py` уже содержит реальные PHC-based tests основных auth,
abort/reauth, options и migration paths. Команда расширяет существующее покрытие
по текущим gaps из `docs/testing/strategy.md`, а не пересоздаёт suite.

## Шаги

1. Прочитай `custom_components/elektronny_gorod/config_flow.py` — все steps, errors, aborts.
2. Прочитай существующие `tests/test_config_flow.py`, `tests/test_init.py` и
   `tests/test_options_flow_clear_creds.py`; не дублируй уже проверяемый сценарий.
3. Прочитай `docs/testing/strategy.md` (раздел Config flow) и
   `docs/aidd/runbooks/local-development.md`.
4. Выбери конкретный uncovered behavior или regression.
5. Следуй RED → GREEN:
   - сначала добавь минимальный test, который падает по ожидаемой причине;
   - затем меняй production code только с отдельным разрешением владельца;
   - не ослабляй assertions ради зелёного результата.
6. Запусти focused config-flow/migration suite, затем полный backend suite.
7. Если причина падения неясна — активируй `systematic-debugging` и установи
   root cause до изменения теста или production code.

## Output

```md
## Done
- N тестов добавлено/обновлено
- какой behavior или regression теперь защищён

## Verification
- focused config-flow/migration suite — passed N/N
- `PYTHONPATH=. .venv/bin/pytest tests/ -q` — passed N/N

## Caught bugs (если были)
- F-NN: description, evidence, severity

## Hand-off
- next: docs-keeper (обновить `testing/strategy.md`; audit — только если менялся finding)
```

## Constraints

- 🔴 НЕ исправлять тест ради зелёного CI, если код сломан.
- НЕ использовать реальный API оператора.
- НЕ оставлять `print()` / `debugger`.
- Не заявлять coverage-процент без свежего coverage-run.
