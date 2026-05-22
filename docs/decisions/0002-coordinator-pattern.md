# ADR-0002: Переход на CoordinatorEntity + update_interval

- **Status:** proposed
- **Date:** 2026-05-22
- **Owner:** Architecture Agent

## Context

Сейчас [`coordinator.py`](../../custom_components/elektronny_gorod/coordinator.py) — `DataUpdateCoordinator` номинально, но:

- Нет `update_interval`.
- `_async_update_data` грузит `_subscriber_places` **один раз** на setup.
- Entity не наследуют `CoordinatorEntity`; они ходят в `coordinator.update_*_state()` через свой `async_update`.
- `manifest.json` указывает `iot_class: cloud_polling`, что не соответствует реальности.

Последствия текущего состояния:
- Баланс ЛС не обновляется автоматически.
- Список мест/устройств не обновляется без reload entry.
- Camera `async_update` делает доп. запрос `get_camera_stream` (A-44), создавая лишнюю нагрузку.
- Lock `fake_timer_lock` через `asyncio.sleep` — синтетический state.
- IQS Bronze blocker.

## Decision

В **Итерации 2** перевести проект на каноничный coordinator-pattern Home Assistant:

1. `ElektronnyGorodUpdateCoordinator`:
   - Задать `update_interval=timedelta(minutes=5)` (точное значение — в Итерации 2 через бенчмарк).
   - В `_async_update_data` обновлять: places, балансы (всех), статус локов. Стримы — по запросу, не в общем тике.
   - Возвращать `data: dict` с ключами `places`, `balances`, `cameras`, `locks`.
2. Все entity наследуют `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]`:
   - Удалить собственный `async_update`.
   - Использовать `_handle_coordinator_update` для копирования релевантной части `coordinator.data` в локальные атрибуты.
   - `available` определяется по факту присутствия данных в `coordinator.data`.

## Consequences

### Positive

- Закрывает A-08, A-09, A-44 одной серией изменений.
- IQS Bronze становится достижим.
- Снижает нагрузку на API оператора (один тик, не N отдельных `async_update`).
- Lock fake-timer (A-15) можно удалить — состояние идёт из coordinator.

### Negative

- Перепись 3 платформ + coordinator одновременно — большой PR.
- Существующие пользователи увидят **другой** интервал обновления.
- Camera snapshot всё равно остаётся on-demand — паттерн coordinator-а для бинарных данных не идеален.

### Mitigation

- Разбить на vertical slices: сначала coordinator, потом по одной платформе.
- Покрыть тестами **до** merge (test-driven подход).
- В CHANGELOG явно описать изменение update-интервала.

## Alternatives considered

1. **Оставить как есть, исправить только `iot_class`.** Отклонено — это маскирует проблему.
2. **Перейти на `PollingMixin` без CoordinatorEntity.** Отклонено — coordinator pattern — стандарт HA.
3. **Webhook вместо polling.** Отклонено — API оператора webhook не предоставляет.

## Supersedes / Superseded by

— (новое решение)

## Notes

См. также:
- [ADR-0003](0003-iot-class-strategy.md) — `iot_class` после внедрения этого ADR.
- [`docs/audit/project-audit.md#A-08`](../audit/project-audit.md), `A-09`, `A-44`.
- [`docs/architecture/quality-scale.md#bronze`](../architecture/quality-scale.md).
