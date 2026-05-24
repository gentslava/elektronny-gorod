# ADR-0002: Переход на CoordinatorEntity + update_interval

- **Status:** accepted
- **Date:** 2026-05-22 (accepted 2026-05-24)
- **Owner:** Architecture Agent

> Реализация поэтапная: **slice 3a** (Этап 3) — coordinator сам (`update_interval`,
> `_async_update_data` → dict). **Slice 3b** — entities наследуют CoordinatorEntity.
> **Slice 3c** — entity polish для Bronze: stable `unique_id`, `has_entity_name`,
> `device_info`, sensor `MONETARY/CURRENCY_RUBLE`; миграция legacy UIDs.

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

## Entity naming & unique_id (slice 3c — A-12, A-13, A-14)

### unique_id — стабильный, без user-facing name

Старые форматы зависели от динамического `name` (приходит от API оператора и
меняется при переименовании в приложении), что приводило к появлению дублей
entity:

- camera: `f"{id}_{name}"` → `f"{DOMAIN}_camera_{id}"`
- lock: `f"{place_id}_{ac_id}_{entrance_id}_{name}"` → `f"{DOMAIN}_lock_{place_id}_{ac_id}_{entrance_id or 'main'}"`
- sensor balance: `f"{DOMAIN}_{place_id}_balance"` — уже стабильный, миграции не требует.

Канонический format для lock — функция `entity_migration.lock_unique_id` (одна
точка истины для производства + миграции; покрыта golden-тестом).

### Миграция legacy UIDs

Сделано через `entity_registry.async_migrate_entries` в `async_setup_entry`
после `coordinator.async_config_entry_first_refresh()`, до
`async_forward_entry_setups`. Алгоритм:

1. Из свежего `coordinator.data` строим словари известных camera/lock.
2. Для каждой записи в registry с `platform == DOMAIN`:
   - проверяем, не в новом ли уже формате (если да — skip);
   - если матчится legacy format с какой-то записью — отдаём `{"new_unique_id": ...}`;
   - иначе — None (registry-запись остаётся, HA сообщит «entity not provided by integration», пользователь может удалить).
3. HA-core переименовывает unique_id; historical data, automation references,
   `entity_id` пользовательский — сохраняются.

Версия `ConfigEntry` НЕ повышается — миграция касается только entity_registry,
не данных entry.

### has_entity_name + device_info

- **sensor balance**: `_attr_has_entity_name=True` + `_attr_translation_key="balance"`.
  Имя из `strings.json` → `entity.sensor.balance.name`. Device — per place,
  identifiers `{(DOMAIN, f"place_{place_id}")}`, имя — `place.address.visibleAddress`
  (address от API — это **dict**, не строка; см. [api-reference](../architecture/api-reference.md#place-shape)).
- **lock (intercom entrance)**: `_attr_has_entity_name=True`, `_attr_translation_key="lock"`
  (имя entity = «Замок» / «Lock» из translations; device.name даст префикс
  «Подъезд 2 Замок»). Device identifier — `(DOMAIN, f"entrance_{place}_{ac}_{eid|main}")` —
  общий с intercom-camera **того же entrance**. `via_device → place`.
- **camera (intercom)**: `_attr_name=None` (главный entity домофона), device
  identifier тот же `(DOMAIN, f"entrance_{place}_{ac}_{eid|main}")` — то есть
  **в одном устройстве** с lock того же entrance. `model="Intercom"`.
- **camera (standalone — public/place)**: `_attr_name=None`, device identifier
  `(DOMAIN, f"camera_{id}")`, `model="IP Camera"`, без via_device.
- **device.name**: для intercom — `entrance.name` (единое для camera + lock).

### Группировка intercom: entrance, не access_control

API ([api-reference §Access controls](../architecture/api-reference.md#access-controls-домофоны))
содержит `externalCameraId` **на двух уровнях** — `access_control.externalCameraId`
и `entrances[*].externalCameraId`. Schema допускает их различие; на практике
во всех 11 наблюдаемых AC в HAR значения совпадают (1 entrance на AC).
Однако в реальной установке пользователя `ac.externalCameraId` для одного
AC указывал на камеру **другой** entrance — приложение использует
entrance-level. Поэтому **группировка идёт по entrance**, не по ac:
identifier `entrance_{place}_{ac}_{eid|main}`, источник camera_id —
`entrance.externalCameraId`. AC-level externalCameraId — fallback только
для access_controls без entrances.

### device_class / state_class / unit (sensor balance — A-14)

- `device_class = SensorDeviceClass.MONETARY`
- `state_class = SensorStateClass.TOTAL` (HA long-term statistics для денег)
- `native_unit_of_measurement = "RUB"` (ISO 4217 — требование `MONETARY` device_class; константа `CURRENCY_RUBLE` удалена из `homeassistant.const`)

`extra_state_attributes` оставлены с Title Case ключами (`"Amount sum"` и т.д.) —
A-30 (snake_case) перенесён в Итерацию 3 как breaking change для пользовательских
YAML.

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
