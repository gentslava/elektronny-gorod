# ADR-0003: Стратегия `iot_class` и polling

- **Status:** proposed
- **Date:** 2026-05-22
- **Owner:** HA Expert Agent

## Context

В [`manifest.json`](../../custom_components/elektronny_gorod/manifest.json) указано `iot_class: cloud_polling`. Однако:

- `DataUpdateCoordinator` без `update_interval` ([ADR-0002](0002-coordinator-pattern.md)).
- Polling де-факто отсутствует — только разовый refresh на setup.
- Информация из manifest вводит пользователей и HA-core в заблуждение.

[`iot_class` reference](https://developers.home-assistant.io/docs/creating_integration_manifest#iot_class):

| Class | Когда |
|---|---|
| `cloud_polling` | мы периодически опрашиваем cloud API |
| `cloud_push` | cloud push нам события |
| `local_polling` | мы периодически опрашиваем устройство в LAN |
| `local_push` | устройство пушит нам в LAN |
| `assumed_state` | состояние не имеет verified источника |

## Decision

В сочетании с [ADR-0002](0002-coordinator-pattern.md) — оставить `iot_class: cloud_polling` и реально включить polling через `update_interval`.

`update_interval` — `timedelta(minutes=5)` начальная точка. В Итерации 3 — измерить:
- среднее время запроса к API оператора;
- частоту изменений balance и device state;
- rate-limit оператора (см. [`api.py:115`](../../custom_components/elektronny_gorod/api.py#L115) — 429 для SMS, по другим endpoints — неизвестно).

При необходимости снизить частоту до `timedelta(minutes=15)` для balance и до `timedelta(minutes=5)` для locks/cameras availability.

## Consequences

### Positive

- `iot_class` соответствует реальности.
- IQS правило `appropriate-polling` выполнено.
- Пользователи видят актуальный баланс.

### Negative

- Нагрузка на API оператора возрастёт.
- Возможны rate-limit hits, если оператор начнёт применять их к другим endpoints.

### Mitigation

- Реализовать exponential backoff (см. [`audit/security.md#S-10`](../audit/security.md)).
- Логировать (без секретов) частоту 429, чтобы видеть, нужно ли снижать `update_interval`.

## Alternatives considered

1. **Сменить `iot_class` на `assumed_state`.** Отклонено — состояния известны точно (баланс с API).
2. **Удалить `cloud_polling` без замены.** Отклонено — HA требует валидный iot_class.
3. **Каждая entity со своим интервалом.** Отклонено — coordinator pattern идёт с единым interval.

## Supersedes / Superseded by

— (новое)

## Notes

Зависит от [ADR-0002](0002-coordinator-pattern.md) — без него polling не имеет смысла.
