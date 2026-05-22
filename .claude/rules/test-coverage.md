# Rule: Test coverage

**Применимо к:** `tests/**`, `custom_components/elektronny_gorod/**.py`.

## Правила

### Что требует теста

- Каждый config_flow happy path → тест.
- Каждый config_flow error / abort → тест.
- Каждая migration версии config_entry → тест.
- Coordinator: `get_*_info`, `update_*_state` — тесты с mocked API.
- API: каждый endpoint → тест на 200 + основные error-коды (300/204/400/406/429/401).
- go2rtc validation: happy + error paths.
- Helpers: `hash_password`, `hash_password_timestamp` — golden vectors.
- Diagnostics: проверка redaction.

### Bug fix → тест

При исправлении бага:
1. Сначала тест, воспроизводящий баг (red).
2. Потом fix (green).
3. Никогда — fix без теста.

### Что НЕ делать

- 🔴 НЕ «упрощать» тест ради зелёного CI.
- 🔴 НЕ удалять тест без отдельного approval.
- 🔴 НЕ маркировать `@pytest.mark.skip` без причины в комментарии.
- 🔴 НЕ моковать так, что mock возвращает успех даже на сломанный код.

### Mock-стратегия

- HTTP к `myhome.proptech.ru` → `aioresponses`.
- HA core → `pytest-homeassistant-custom-component`.
- `async_setup_entry` для config-flow тестов → `patch` (как в текущем `conftest.py`).

### Покрытие (target)

| Уровень | Цель |
|---|---|
| Bronze | config_flow happy path + abort `already_configured` + migrations |
| Silver | + coordinator + api endpoints + edge cases (≥ 70%) |
| Gold | + entity state transitions + repairs + reconfigure (≥ 80%) |

## Pre-commit

`pytest tests/ -v` должен быть зелёным перед каждым commit, затрагивающим code (после Итерации 2).

## Связь

- docs/testing/strategy.md (полный test plan)
- docs/aidd/runbooks/testing.md (как запускать)
- docs/aidd/quality-gates.md (TESTS_PASS criteria)
