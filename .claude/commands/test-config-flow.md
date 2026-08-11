---
description: Запустить и дополнить реальные config_flow-тесты по плану docs/testing/strategy.md.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

Ты — QA Engineer. Активируй skill `test-driven-development`.

## Контекст

`tests/test_config_flow.py` содержит рабочие PHC-тесты auth-веток, ошибок и
abort/reauth-сценариев. Актуальный baseline и остающиеся gaps определяются
только по `docs/testing/strategy.md` и реальному test inventory.

## Шаги

1. Прочитай `custom_components/elektronny_gorod/config_flow.py` — все steps, errors, aborts.
2. Прочитай `docs/testing/strategy.md` (раздел 1. Config flow) — canonical
   baseline и список сценариев.
3. Прочитай `docs/aidd/runbooks/local-development.md` — команды и mock strategy.
4. Запусти существующий файл и зафиксируй исходный результат:
   `PYTHONPATH=. .venv/bin/pytest tests/test_config_flow.py -v`.
5. Сопоставь реальные тесты с изменёнными ветками `config_flow.py`, acceptance
   criteria задачи и открытыми gaps из strategy. Добавляй только отсутствующие
   сценарии; существующие рабочие тесты и fixtures не переписывай без доказанной
   причины.
6. Для нового или исправляемого поведения сначала получи ожидаемый RED, затем
   минимальный GREEN и повторно запусти весь `tests/test_config_flow.py`.
7. Если тест падает по непонятной причине — найди root cause через
   `systematic-debugging`. **Не упрощать тест.**

## Output

```md
## Done
- N тестов добавлено/уточнено и какие сценарии они защищают
- если запускался coverage — команда и свежий результат; иначе не оценивать его

## Verification
- `PYTHONPATH=. .venv/bin/pytest tests/test_config_flow.py -v` — passed N/N

## Caught bugs (если были)
- F-NN: description, evidence, severity

## Hand-off
- next: docs-keeper (обновить canonical baseline/gaps в testing/strategy.md,
  только если фактический состав или покрываемый capability изменился)
```

## Constraints

- 🔴 НЕ исправлять тест ради зелёного CI, если код сломан.
- НЕ использовать реальный API оператора.
- НЕ удалять и не переписывать весь существующий test module ради одного gap.
- НЕ оставлять `print()` / `debugger`.
- НЕ импортировать несуществующие сущности.
