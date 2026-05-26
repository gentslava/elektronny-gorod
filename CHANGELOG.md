# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/),
проект использует [SemVer](https://semver.org/).

## [Unreleased]

### CI

- **PR pre-release auto-cleanup**. Workflow `.github/workflows/prerelease.yaml` теперь слушает `pull_request:closed` и удаляет `pr-NN` release + tag через `gh release delete --cleanup-tag`. Раньше pre-releases накапливались (15+ висящих для merged PR на момент 2026-05-26) — теперь GitHub Releases остаются чистыми, в списке видны только настоящие версии и активные PR pre-releases. Разовая чистка: удалены pr-25, pr-27, pr-31..35, pr-38..40, pr-42..45.

### Fixed

- **Visibility sync: reload cascade + user override** ([A-64](docs/audit/project-audit.md)). Раньше cold start давал **4× reload в 34 сек** (production-лог 2026-05-26): `_migrate_legacy_disabled_state` писал flag в `entry.options` → triggers `async_update_options` listener → `async_reload` → setup_entry; параллельно setup триггерил reload через `migration_changed or sync_changed`. Помимо этого `_sync_visibility` на каждом setup восстанавливал `INTEGRATION` для hidden-в-API камер — перезаписывал юзерский выбор «Показывать на панели» (через 5 мин камера снова hidden в HA UI). **Изменения**: (1) migration flag перенесён в `entry.data` (НЕ триггерит options-listener); backward-compat читает оба места, переносит при первом setup; (2) explicit `async_reload` теперь только при `migration_changed` — sync visibility это live registry update, reload не нужен; (3) `_sync_visibility` track per-entity flags через `entity.options[DOMAIN]` (persistent, не триггерит entry-listener): `we_set_integration` — наша отметка, `user_shown` — детектится когда мы set INTEGRATION, а registry уже None (юзер кликнул «Показывать на панели»). С `user_shown=True` мы НЕ восстанавливаем INTEGRATION даже если API hidden. При un-hide в приложении (API visible) — `user_shown` auto-clear. 5 новых тестов (`tests/test_visibility_user_override.py`). USER hidden_by override продолжает уважаться (regression-guard).

- **Camera: skip stream/snapshot fetch для hidden cameras** ([A-63](docs/audit/project-audit.md)). HA core и downstream-интеграции (frigate, webrtc preview, advanced lovelace) могут вызывать `stream_source()` и `async_camera_image()` для всех зарегистрированных camera entities — включая скрытые в HA UI (`hidden_by` любого reason: `INTEGRATION` от visibility sync на основе `/settings/screens`, `USER` если юзер выключил «Показывать на панели»). Раньше это приводило к лишним HTTP-запросам к operator API для камер, которых юзер не видит (production-лог 2026-05-26: `Camera init id=... hidden=True` → `Fetching camera ... stream URL`). Теперь helper `_is_hidden()` skip-нет вызов БЕЗ обращения к coordinator если `registry_entry.hidden_by is not None`. Чтобы вернуть видео — toggle «Показывать на панели» в entity-edit page (HA устанавливает `hidden_by=None`). 5 regression-тестов (`tests/test_camera_hidden_skip.py`). Visible cameras работают без изменений. **NOTE**: наш sync пока overrides user «Показать» на следующем 5-min refresh — отдельный follow-up.

### Changed

- **Coordinator: убран двойной HTTP в per-place collectors** ([A-61](docs/audit/project-audit.md)). `_collect_locks_for_place` ранее дублировал `query_screens_settings` + `query_access_controls`, уже вызванные `_collect_cameras_for_place`. Теперь pre-fetch в `_async_update_data` (один раз per place), передача в оба collectors как параметры. **Экономия: -2 HTTP per place per 5min refresh** (-576 calls/day для 1 place). Поведение неизменно — 74 tests pass (+3 new regression-guard). NOTE: при ошибке `query_access_controls` теперь и cameras, и locks для того места пусты (раньше locks могли survive независимо — теперь это атомарная per-place операция).

### Added

- **Do Not Disturb switches** ([A-56](docs/audit/project-audit.md)). Для каждого place добавлены 3 switch entity (mirror приложения «Мой Дом» → Настройки → Уведомления → Не беспокоить):
  - `switch.{place}_do_not_disturb` — master switch.
  - `switch.{place}_mute_intercom_calls` — отключить звонки с домофона (dependent, available только если master ON).
  - `switch.{place}_mute_management_company_calls` — отключить уведомления УК (dependent).
  - Полностью server-side: при включении backend перестаёт слать push о звонках. Toggle через HA UI — POST `/api/mh-customer/.../settings/do_not_disturb`. См. api-reference §do_not_disturb.

- **Balance-related entities** ([A-57](docs/audit/project-audit.md)). Для каждого place добавлены 2 entity на основе расширенного `/finance` response:
  - `binary_sensor.{place}_account_blocked` — `device_class=problem`, `True` когда аккаунт заблокирован оператором. Готово для automation «уведомить если blocked».
  - `sensor.{place}_days_to_block` — `device_class=duration`, `unit=d`. Дней до автоматической блокировки. Графики warning возможны.
  - `payment_link` остаётся как attribute `"Payment link"` у `sensor.balance` (для использования через Lovelace `tap_action: url` или automation с `mobile_app.notify` OPEN_URL).
  - **0 новых HTTP calls** — поля приходят в существующем `query_balance` (был unused). Coordinator теперь extract `days_to_block`, `days_to_warning`, `company`.

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
