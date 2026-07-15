# Runbook: Testing

Как запускать тесты. План тестов — в [`testing/strategy.md`](../../testing/strategy.md).

## Текущий статус

Suite зелёный; config flow и миграции покрыты реальными PHC-тестами. Точный
baseline, состав модулей и известные gaps ведутся в
[`testing/strategy.md`](../../testing/strategy.md), а не дублируются здесь.

## Установка

```bash
python3 -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component
.venv/bin/pip install -r requirements_test.txt
```

## Запуск

```bash
# все тесты (канонический локальный gate)
PYTHONPATH=. .venv/bin/pytest tests/ -q

# конкретный файл
PYTHONPATH=. .venv/bin/pytest tests/test_config_flow.py -v

# конкретный тест
PYTHONPATH=. .venv/bin/pytest \
    tests/test_config_flow.py::test_user_phone_sms_skip_go2rtc -v

# с покрытием
PYTHONPATH=. .venv/bin/pytest tests/ \
    --cov=custom_components/elektronny_gorod --cov-report=term-missing -q
```

## Mock-стратегия

| Что мокаем | Чем | Когда |
|---|---|---|
| HTTP к `myhome.proptech.ru` | `AsyncMock` / `aioresponses` | API и config-flow tests |
| HA core (`hass`, ConfigEntry) | `pytest-homeassistant-custom-component` | все integration tests |
| `async_setup_entry` для config-flow | `patch` | как в текущем conftest.py |
| go2rtc HTTP | `aioresponses` | go2rtc tests |
| Время / UUID | `unittest.mock.patch` | для стабильных fixtures |

## Config flow examples

Исполняемые примеры находятся в `tests/test_config_flow.py`; миграции — в
`tests/test_init.py`. Не копируйте fixtures в runbook: тесты являются source of
truth и проверяются CI.

## Что НЕ делать

- 🔴 Не «исправлять» тест, чтобы он зелёный при сломанном коде.
- 🔴 Не использовать реальный API оператора в тестах (rate limits + privacy).
- 🔴 Не оставлять `print()` / реальный network в тестах.

## CI

`.github/workflows/python-tests.yaml` запускает pytest matrix на минимальной и
текущей поддерживаемой Home Assistant.

## Quality gate

`TESTS_PASS` — требуется для merge.

## Next reading

- [`../../testing/strategy.md`](../../testing/strategy.md) — полный test plan
- [`../quality-gates.md`](../quality-gates.md) — критерии TESTS_PASS
