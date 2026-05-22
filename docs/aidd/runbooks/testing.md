# Runbook: Testing

Как запускать тесты. План тестов — в [`testing/strategy.md`](../../testing/strategy.md).

## Текущий статус

🔴 Существующий `tests/test_config_flow.py` — нерабочий stub из HA scaffold, **не запускать его «как есть»**. Сначала пометить как skip или удалить (см. A-07).

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install \
    pytest \
    pytest-asyncio \
    pytest-homeassistant-custom-component \
    aioresponses
```

## Запуск

```bash
# все тесты
pytest tests/ -v

# конкретный файл
pytest tests/test_config_flow.py -v

# конкретный тест
pytest tests/test_config_flow.py::test_user_phone_sms_skip_go2rtc -v

# с покрытием
pytest tests/ --cov=custom_components.elektronny_gorod --cov-report=term-missing
```

## Mock-стратегия

| Что мокаем | Чем | Когда |
|---|---|---|
| HTTP к `myhome.proptech.ru` | `aioresponses` | API tests, coordinator tests |
| HA core (`hass`, ConfigEntry) | `pytest-homeassistant-custom-component` | все integration tests |
| `async_setup_entry` для config-flow | `patch` | как в текущем conftest.py |
| go2rtc HTTP | `aioresponses` | go2rtc tests |
| Время / UUID | `freezegun` / `unittest.mock.patch` | для стабильных fixtures |

## Минимальный config flow тест (пример)

```python
"""Test config flow happy path."""
from unittest.mock import patch
import pytest
from aioresponses import aioresponses
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.elektronny_gorod.const import DOMAIN


async def test_user_phone_sms_skip_go2rtc(hass):
    """phone → contract → SMS → go2rtc skip → CREATE_ENTRY."""
    with aioresponses() as m:
        m.get(
            "https://myhome.proptech.ru/auth/v2/login/+79991112233",
            status=300,
            payload=[{"accountId": "A1", "subscriberId": "S1",
                      "operatorId": 1, "address": "addr", "placeId": "P1"}],
        )
        m.post(
            "https://myhome.proptech.ru/auth/v2/confirmation/+79991112233",
            status=200,
        )
        m.post(
            "https://myhome.proptech.ru/auth/v3/auth/+79991112233/confirmation",
            payload={"accessToken": "T1", "refreshToken": "R1", "operatorId": 1},
        )
        m.get(
            "https://myhome.proptech.ru/rest/v1/subscribers/profiles",
            payload={"data": {"subscriber": {"id": "S1", "accountId": "A1", "name": "Test"}}},
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"phone": "+79991112233"}
        )
        assert result["step_id"] == "contract"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"contract": "S1"}
        )
        assert result["step_id"] == "sms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"sms": "123456"}
        )
        # Меню go2rtc:
        assert result["type"] == FlowResultType.MENU

        # Выбираем skip_go2rtc:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "skip_go2rtc"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["account_id"] == "A1"
```

## Что НЕ делать

- 🔴 Не «исправлять» тест, чтобы он зелёный при сломанном коде.
- 🔴 Не использовать реальный API оператора в тестах (rate limits + privacy).
- 🔴 Не оставлять `print()` / реальный network в тестах.

## CI

После Итерации 2 — `.github/workflows/python-tests.yaml`.

## Quality gate

`TESTS_PASS` — требуется для merge.

## Next reading

- [`../../testing/strategy.md`](../../testing/strategy.md) — полный test plan
- [`../quality-gates.md`](../quality-gates.md) — критерии TESTS_PASS
