# ADR-0008: Shared `ClientSession` через `async_get_clientsession(hass)`

- **Status:** accepted
- **Date:** 2026-05-24
- **Owner:** Architecture + HA Expert Agent

## Context

Сейчас [`http.py:56`](../../custom_components/elektronny_gorod/http.py#L56) создаёт `aiohttp.ClientSession()` **per-request**:

```python
async with ClientSession() as session:
    ...
```

Это нарушает HA-конвенцию ([audit A-05](../audit/project-audit.md), [security S-05](../audit/security.md)). На каждый HTTP-запрос:
- новый TCP + TLS handshake (~50-200ms);
- новый connector pool (нет HTTP/2 multiplexing, нет keep-alive reuse);
- накопление сокетов в `TIME_WAIT` после закрытия;
- невозможность HA-core централизованно ограничивать concurrent requests / monitoring.

Home Assistant предоставляет `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` — общий pool на весь HA-инстанс. Это стандарт для **всех** интеграций.

## Decision

Прокинуть `hass: HomeAssistant` через слои `Coordinator → API → HTTP` и использовать `async_get_clientsession(hass)` в `HTTP.__request`.

### Изменения сигнатур

```python
class HTTP:
    def __init__(
        self,
        hass: HomeAssistant,       # ← новое
        user_agent: UserAgent,
        access_token: str | None,
        refresh_token: str | None,
        operator: str | None,
    ) -> None:
        self._hass = hass
        ...

class ElektronnyGorodAPI:
    def __init__(
        self,
        hass: HomeAssistant,       # ← новое
        user_agent: UserAgent,
        access_token: str | None = None,
        refresh_token: str | None = None,
        operator: str | None = None,
    ) -> None:
        self.http = HTTP(hass, user_agent, access_token, refresh_token, operator)
        ...
```

В `HTTP.__request`:

```python
session = async_get_clientsession(self._hass)
# больше НЕ `async with ClientSession() as session:`
if method == "GET":
    response = await session.get(url, headers=self._headers)
elif method == "POST":
    response = await session.post(url, data=data, headers=self._headers)
```

Важно: **не закрывать** session через `async with` или `session.close()` — это shared pool, его lifecycle управляется HA-core.

### Места вызовов

- `coordinator.py:__init__` — `ElektronnyGorodAPI(hass, user_agent, ...)`. `hass` уже есть в этой функции.
- `config_flow.py:__init__` — `ElektronnyGorodAPI(self.hass, self.user_agent)`. `self.hass` доступен в `ConfigFlow`.

## Consequences

### Positive

- Закрывает [audit A-05](../audit/project-audit.md), [security S-05](../audit/security.md).
- Экономия TLS handshake (~50-200ms per request) — заметно при последовательной серии snapshot-запросов камер.
- Нет утечки сокетов в `TIME_WAIT`.
- Согласуется с HA Bronze IQS требованиями.
- Совместимо с будущим `ClientTimeout` (A-21) — `async_get_clientsession(hass)` возвращает session, в которой можно передать timeout через каждый request.

### Negative

- **Breaking change** для внутреннего API `HTTP.__init__` / `ElektronnyGorodAPI.__init__` (новый параметр `hass`). На существующих интеграциях не сломается, т.к. вызовы только из `coordinator.py` и `config_flow.py` (внутренние).
- Тесты, которые инстанцируют `HTTP` / `API` напрямую (будущие в Этапе 3 Bronze) должны передавать mock-hass.

### Mitigation

- Сигнатуры обновлены атомарно — один commit, никаких поэтапных deprecations внутри проекта.
- HA-core mock через `pytest-homeassistant-custom-component` предоставит совместимый `hass`.

## Alternatives considered

1. **Создать одну `ClientSession` в `HTTP.__init__` и переиспользовать без `hass`.** Отклонено — не идиоматично для HA, ломает закрытие на unload, не использует HA-core monitoring.
2. **Lazy session per HTTP instance**, кэшированная в self.\_session. Отклонено — то же.
3. **Использовать `async_create_clientsession(hass)` вместо `async_get_clientsession(hass)`** (создание своей session с custom-конфигом). Отклонено — нам не нужен custom-конфиг сейчас; shared pool достаточно.

## Supersedes / Superseded by

—

## Notes

- Связано с [ADR-0002](0002-coordinator-pattern.md) (coordinator pattern) — A-05 нужно решить **до** реализации ADR-0002, чтобы новый CoordinatorEntity не наследовал плохой паттерн.
- Audit IDs закрываемые: A-05 (P0 — performance/HA-compat), S-05 (security — связано с реликвиями).
- Не закрывает A-21 (`ClientTimeout`) — отдельная задача в Этапе 3 Bronze.
- Не закрывает A-19/A-20 (узкие исключения) — отдельная задача.
