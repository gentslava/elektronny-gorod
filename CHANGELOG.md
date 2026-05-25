# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/),
проект использует [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **Do Not Disturb switches** ([A-56](docs/audit/project-audit.md)). Для каждого place добавлены 3 switch entity (mirror приложения «Мой Дом» → Настройки → Уведомления → Не беспокоить):
  - `switch.{place}_do_not_disturb` — master switch.
  - `switch.{place}_mute_intercom_calls` — отключить звонки с домофона (dependent, available только если master ON).
  - `switch.{place}_mute_management_company_calls` — отключить уведомления УК (dependent).
  - Полностью server-side: при включении backend перестаёт слать push о звонках. Toggle через HA UI — POST `/api/mh-customer/.../settings/do_not_disturb`. См. api-reference §do_not_disturb.

## [3.1.0] - 2026-05-25

### Security 🔴

> **Внимание пользователям:** если вы когда-либо включали `logger: default: debug` или `info` для `custom_components.elektronny_gorod`, рекомендуется **перевыпустить access_token** (пройти reauth через UI), особенно если вы делились логами в issue / Discord / других публичных местах. В предыдущих версиях access_token и Bearer-headers попадали в логи на уровне debug/info.

- Удалено логирование `access_token` после ввода в advanced-режиме config_flow ([A-01](docs/audit/project-audit.md)).
- Headers с `Authorization: Bearer ...` теперь проходят через `redact()` перед попаданием в логи ([A-02](docs/audit/project-audit.md)).
- Тело запроса/ответа для `/auth/*` endpoints не логируется вообще (там приходят/отправляются токены, пароли, SMS-коды) ([A-03](docs/audit/project-audit.md)).
- В логи попадает `entry.entry_id` вместо целиком `entry.data` (которое содержит токены) ([A-04](docs/audit/project-audit.md)).
- Contract object не дампится в логи целиком — только subscriberId ([S-06](docs/audit/security.md)).
- Добавлен helper `_logging.redact()` с `SENSITIVE_KEYS` (источник правды — [ADR-0004](docs/decisions/0004-token-redaction.md)).

### Fixed

- Исправлен баг в `update_camera_state`: поиск по ключу `"ID"` (верхний регистр) вместо `"id"` — приводил к ложному `Camera not found` при каждом async_update камеры ([A-06](docs/audit/project-audit.md)).
- `coordinator._async_update_data` использует `LOGGER.exception(...)` вместо `traceback.format_exc()` (не блокирует event loop).
- В `sensor.py:async_update` exception теперь логируется с traceback (`LOGGER.exception`).
- `http.py:_log_response` больше **не вычитывает** response body для логирования — это устраняет латентный баг, при котором логгер «съедал» тело и caller получал пустой ответ. Сейчас в лог идут только status + content-length (для не-auth paths).

### Changed

- `import base64` поднят на top of file в `camera.py` (был внутри метода) ([A-43](docs/audit/project-audit.md)).
- Заменён `f"..."`-форматирование на `%`-форматирование в `LOGGER` вызовах (`lock.py`, `sensor.py`, `coordinator.py`).
- **HTTP: shared `ClientSession`** через HA-стандартный `async_get_clientsession(hass)`. `HTTP.__init__` и `ElektronnyGorodAPI.__init__` принимают `hass`. Closes [A-05](docs/audit/project-audit.md) / [S-05](docs/audit/security.md). См. [ADR-0008](docs/decisions/0008-shared-client-session.md). Эффект: экономия TLS-handshake на каждом запросе, общий pool с HA-core, нет утечки сокетов в TIME_WAIT.
- **Coordinator pattern: реальный polling** ([ADR-0002](docs/decisions/0002-coordinator-pattern.md), [ADR-0003](docs/decisions/0003-iot-class-strategy.md)). `DataUpdateCoordinator` теперь имеет `update_interval=timedelta(minutes=5)` и `_async_update_data` за один тик собирает `{places, balances, cameras, locks}` (последовательно по places из-за shared UA state). Closes [A-08](docs/audit/project-audit.md), [A-16](docs/audit/project-audit.md) (`async_unsubscribe` из unload), [A-17](docs/audit/project-audit.md) (дубликат сбора камер), [A-18](docs/audit/project-audit.md) (мёртвый `available_sections`).
- **Entities на CoordinatorEntity** (slice 3b). Camera / Lock / Sensor наследуют `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]`. `async_update` удалён из всех 3 платформ — обновления приходят через `_handle_coordinator_update`. Backwards-compat shims (`get_*_info`, `update_*_state`) удалены из coordinator. Lock state-cycle (UNLOCKED → 5s → LOCKED) переписан с `asyncio.sleep` на `async_call_later` — не блокирует event loop, совместимо с `CoordinatorEntity` (`should_poll=False`). Closes [A-09](docs/audit/project-audit.md), [A-44](docs/audit/project-audit.md).
- **Bronze IQS entity polish** (slice 3c, [ADR-0002](docs/decisions/0002-coordinator-pattern.md) §Entity naming).
  - **Stable `unique_id`** ([A-12](docs/audit/project-audit.md)): camera `{DOMAIN}_camera_{id}`, lock `{DOMAIN}_lock_{place_id}_{ac_id}_{entrance_id|main}`. Старые UID содержали динамический `name` от API оператора. Existing entries мигрируются автоматически через `entity_registry.async_migrate_entries` в `async_setup_entry` — `entity_id`, automations и historical data сохраняются.
  - **`_attr_has_entity_name = True`** + `_attr_translation_key = "balance"` для sensor ([A-13](docs/audit/project-audit.md)). Camera/Lock — `_attr_name = None`, имя приходит из `device_info.name`. Добавлен раздел `entity.sensor.balance.name` в `strings.json` + `translations/{ru,en}.json`.
  - **`device_info`** для всех entity: sensor группируется per place, camera/lock — самостоятельные device (lock с `via_device` на place).
  - **Sensor balance — long-term statistics** ([A-14](docs/audit/project-audit.md)): `device_class=MONETARY`, `state_class=TOTAL`, `native_unit_of_measurement="RUB"` (ISO 4217 — требование `MONETARY` device_class; константа `CURRENCY_RUBLE` удалена из HA core).
  - **manifest.json** ([A-34](docs/audit/project-audit.md)): `quality_scale: "bronze"`, `integration_type: "hub"` (cloud account → many devices, по HA dev docs — аналог Tuya/SmartThings/Husqvarna).

### Removed

- Удалён нерабочий `tests/test_config_flow.py` — это был stub из HA scaffold, импортирующий несуществующие сущности (`CannotConnect`, `InvalidAuth`, `PlaceholderHub`). Полноценные тесты config_flow появятся в [Итерации 2](docs/roadmap.md) Bronze IQS ([A-07](docs/audit/project-audit.md)).

### Tests

- Добавлен `tests/test_logging_redact.py` — unit-тесты для `_logging.redact()` helper.
- Добавлен `tests/test_entity_migration.py` — unit-тесты `_camera_new_uid`/`_lock_new_uid` + golden vector для `lock_unique_id`.

### Fixed

- `async_migrate_entity_unique_ids` пропускает коллизии вместо падения с `ValueError`. Если у camera/lock накопилось несколько legacy записей в `entity_registry` (разные `name` за время) — все они мапятся в один stable UID. Мигрируется первая, остальные остаются orphan с warning в лог (пользователь удаляет вручную). Раньше ValueError ломал весь `async_setup_entry` → entity не создавались.
- `manifest.json`: `integration_type: "hub"` (после короткого ошибочного переключения на `service` и отката). По HA dev docs hub = «one config_entry → many devices» (как Tuya/SmartThings/Husqvarna cloud), что точно описывает наш случай (один аккаунт оператора = camera/lock/sensor по местам). `service` подходит только single-service integrations (Spotify, Google Calendar, DuckDNS — 1 entity per account).
- **Группировка intercom по entrance** (HAR-verified). Каждая `entrance` access_control имеет свою `externalCameraId` (api-reference §Access controls). Camera + lock одной entrance → один device с identifier `entrance_{place}_{ac}_{eid|main}`. Раньше группировал по access_control — но `ac.externalCameraId` иногда расходится с `entrance.externalCameraId` в реальных установках, и пользователь видел чужую камеру в device. Coordinator теперь итерирует `entrances[]`, source camera_id = `entrance.externalCameraId`. AC-level используется только когда у access_control нет entrances. Lock entity: `_attr_translation_key="lock"` (раздел `entity.lock.lock.name` в strings + переводы «Замок» / «Lock»), device.name = entrance.name. Standalone камеры (городские / place_cameras) остаются отдельными devices.

### Documentation

- Создан этот `CHANGELOG.md`.

---

## История релизов

Записи до этого Changelog — см. [GitHub Releases](https://github.com/gentslava/HA-ElektronnyGorod/releases).
