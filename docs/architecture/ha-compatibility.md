Status: Active
Owner: Home Assistant Expert Agent
Last reviewed: 2026-07-15 (durable history EventEntity lifecycle, Store schema
and ru/en event translations)

Source files:
- `custom_components/elektronny_gorod/manifest.json`
- `custom_components/elektronny_gorod/config_flow.py`
- `custom_components/elektronny_gorod/coordinator.py`
- `custom_components/elektronny_gorod/__init__.py`
- `custom_components/elektronny_gorod/camera.py`
- `custom_components/elektronny_gorod/lock.py`
- `custom_components/elektronny_gorod/sensor.py`
- `custom_components/elektronny_gorod/event.py`
- `custom_components/elektronny_gorod/history.py`
- `custom_components/elektronny_gorod/strings.json`
- `custom_components/elektronny_gorod/translations/*`
- `hacs.json`

Related docs:
- `quality-scale.md`
- `architecture/overview.md`
- `project-audit.md`
- `security.md`
- `testing/strategy.md`

Used by agents:
- HA Expert, Architecture, QA

Quality gates:
- AUDIT_DONE

---

# Home Assistant Compatibility Audit

Проверка соответствия проекта официальным требованиям Home Assistant.

## Manifest checklist

| Поле | Текущее | Ожидаемое | Статус |
|---|---|---|---|
| `domain` | `elektronny_gorod` | snake_case, уникален | ✅ |
| `name` | `Электронный город` | человекочитаемое | ✅ |
| `codeowners` | `["@gentslava"]` | хотя бы один | ✅ |
| `version` | см. `manifest.json` | semver, обновляется release workflow | ✅ |
| `documentation` | wiki URL | действующая ссылка | ⚠️ контент wiki не подтверждён |
| `issue_tracker` | issues URL | действующая ссылка | ✅ |
| `requirements` | `firebase-messaging>=0.4`, `audioop-lts>=0.2.1` | все вне HA core, объявлены в manifest | ✅ — `firebase-messaging` для FCM-вызова (ADR-0011), `audioop-lts` для G.711-транскода SIP (A-81; только Python 3.13+, `audioop` удалён из stdlib PEP 594) |
| `dependencies` | `[]` | HA-интеграции, нужные при старте | ✅ |
| `iot_class` | `cloud_polling` | соответствие реальности | ✅ coordinator polling каждые 5 минут |
| `config_flow` | `true` | если есть UI flow | ✅ |
| `integration_type` | `hub` | одна entry → несколько устройств | ✅ |
| `quality_scale` | `bronze` | не выше подтверждённого gate | ✅ — config-flow/migration tests существуют |
| `after_dependencies` | ❌ | при необходимости | n/a |

## HACS / hacs.json

| Поле | Текущее | Замечание |
|---|---|---|
| `name` | `Электронный город` | ✅ |
| `homeassistant` | `2024.10.4` | ✅ — `LockState` enum появился в 2024.10 |
| `zip_release` | `true` | ✅ |
| `filename` | `elektronny_gorod.zip` | ✅ |
| `country` | `RU` | ✅ |
| `render_readme` | ❌ | можно добавить |

## Config Flow

### Структура

```
async_step_user
  ├── (advanced) access_token → get_account
  ├── phone → query_contracts
  │     ├── password=True → async_step_password
  │     └── password=False → async_step_contract
  ├── async_step_password → verify_password → get_account
  ├── async_step_contract → request_sms_code → async_step_sms
  ├── async_step_sms → verify_sms_code → get_account
  ├── get_account:
  │     ├── duplicate by access_token → abort already_configured
  │     ├── match by account+subscriber+name → reauth → abort reauth_successful
  │     └── store _entry_data → async_step_go2rtc_menu
  ├── async_step_go2rtc_menu (menu)
  │     ├── go2rtc → async_step_go2rtc → validate_go2rtc → create_entry
  │     └── skip_go2rtc → async_step_skip_go2rtc → create_entry
  └── OptionsFlow
        └── async_step_init → validate_go2rtc → update options
```

### Critique

| Критерий | Статус | Файл:строка |
|---|---|---|
| `config_flow: true` в manifest | ✅ | `manifest.json:7` |
| UI-настройка | ✅ | `config_flow.py:43` |
| `VERSION` | `=3` | `config_flow.py:46` |
| Миграции | ✅ v1→2→3 | `__init__.py:47-81` |
| Проверка соединения до сохранения | ⚠️ Частично: `query_profile` ходит до create_entry; `validate_go2rtc` отдельно | `config_flow.py:265-279, 343-347` |
| Защита от дубликатов | ✅ по `access_token`; ✅ по `account+subscriber+name` (reauth) | `config_flow.py:281-310` |
| Обработка ошибок | ⚠️ есть `errors`-словарь, но широкие `except Exception` | `api.py:61-66` etc |
| Translations всех steps | ✅ ru/en | `translations/*.json` |
| **Native reauth step** (`async_step_reauth`) | ❌ — reauth выполняется внутри `get_account` | требуется `async_step_reauth_confirm` |
| **Reconfigure flow** | ❌ | требуется `async_step_reconfigure` |
| Tests | ✅ реальные config-flow/migration tests | `tests/test_config_flow.py`, `tests/test_init.py` |
| `show_advanced_options` ветка | ✅ есть | `config_flow.py:111-117` |

## Coordinator / Data Fetching

| Критерий | Статус | Файл:строка |
|---|---|---|
| Использование `DataUpdateCoordinator` | ✅ | `coordinator.py:53` |
| `name` задано | ✅ `name=DOMAIN` | `coordinator.py:78-83` |
| `update_interval` задан | ✅ 5 минут | `coordinator.py:50,82` |
| `_async_update_data` реализован | ✅ единый snapshot places/balances/cameras/locks/dnd | `coordinator.py:126+` |
| Возвращаемое `data` используется entity | ✅ через `CoordinatorEntity` | `camera.py`, `lock.py`, `sensor.py`, `switch.py` |
| `UpdateFailed` при ошибке | ✅ fatal places; per-place partial data | `coordinator.py:_async_update_data` |
| Timeout per request | ✅ REST 30с / binary 60с / connect 10с | `http.py:15-22,120-126` |
| Retry / backoff | 🟡 нет; history error изолируется до следующего poll/UI refresh | `api.py`, `history.py`, `history_ws.py`, A-21 |
| Rate limiting | 🔴 нет | — |
| Caching | 🔴 нет | — |
| Никаких blocking ops в loop | ✅ async I/O; blocking subprocess не используется | integration code |
| `async_unsubscribe` вызывается при unload | ✅ через `entry.async_on_unload` | `__init__.py:69-72` |
| History interval cleanup | ✅ `HistoryManager.async_stop` через config-entry unload; overlapping tick пропускается | `history.py`, `__init__.py` |
| Использование `async_get_clientsession(hass)` | ✅ shared HA session | `http.py:96` |

## Entities

| Критерий | Camera | Lock | Sensor (balance) |
|---|---|---|---|
| Наследует `CoordinatorEntity` | ✅ | ✅ | ✅ |
| `_attr_has_entity_name` | ✅ | ✅ | ✅ |
| `_attr_translation_key` | device-level name | device-level name | ✅ `balance` |
| `unique_id` стабилен | ✅ camera id | ✅ place/access-control/entrance | ✅ place id + balance |
| `device_info` | ✅ | ✅ shared entrance device | ✅ place device |
| `device_class` | n/a | lock native | ✅ `MONETARY` |
| `state_class` | n/a | n/a | ✅ `TOTAL` |
| `native_unit_of_measurement` | n/a | n/a | ✅ `RUB` |
| `available` | default | ⚠️ `self._openable` (может быть None) | default |
| `entity_category` | n/a | n/a | можно `diagnostic` |
| Корректное обновление через coordinator | ✅ | ✅ (+ локальный synthetic unlock timer) | ✅ |
| Хардкод русского имени | нет | нет | нет — translation key ru/en |

History `EventEntity` additive и не требует config-entry migration: stable
unique IDs строятся из place/access-control или camera ID, device identity
совпадает с существующим intercom/camera device. `_trigger_event` получает
только allowlisted attributes; backend message не копируется. Durable
accepted/missed streams не объявляют `device_class=doorbell`, потому что этот
HA-класс требует поддержку `ring`; doorbell-класс остаётся только у realtime
сущности вызова.

## Diagnostics / Repairs / Services

| Артефакт | Наличие | Приоритет |
|---|---|---|
| `diagnostics.py` | ✅ redacted | `TO_REDACT ⊇ SENSITIVE_KEYS`, counters-only snapshot |
| `repairs.py` | ❌ | P2 |
| `services.yaml` (свои сервисы) | ✅ `answer` / `hangup` | SIP-вызов |
| Поддержка `system_health` | ❌ | P3 |

## Translations

| Файл | Статус |
|---|---|
| `strings.json` | ✅ source |
| `translations/ru.json` | ✅ соответствует |
| `translations/en.json` | ✅ соответствует |
| **Entity translations** (раздел `strings.json:entity`) | ✅ ru/en |
| History event types | ✅ `call_accepted`, `call_missed`, `motion` в source/ru/en |

## Платформы и manifest dependencies

PLATFORMS: `[BINARY_SENSOR, CAMERA, EVENT, LOCK, SENSOR, SWITCH]`
([`__init__.py:46-53`](../../custom_components/elektronny_gorod/__init__.py)).

Зависимости HA-core (`dependencies` в manifest) пусты. Импортированный helper
`persistent_notification` и стандартные entity-платформы не требуют отдельного
порядка setup через `dependencies`/`after_dependencies`.

## CI / Validation

| Workflow | Назначение | Статус |
|---|---|---|
| `hassfest.yaml` | manifest validation | ✅ есть |
| `hacs.yaml` | HACS validation | ✅ есть |
| `python-tests.yaml` | pytest + coverage (matrix min/current HA) | ✅ есть |
| `prerelease.yaml` | PR pre-release zip (filtered: paths + draft) | ✅ есть |
| `release.yaml` | release zip + autocommit | ✅ есть |

## Brand assets

- `README.md` ссылается на `https://brands.home-assistant.io/elektronny_gorod/icon.png` — нужно проверить, добавлен ли brand в [home-assistant/brands](https://github.com/home-assistant/brands) репозиторий.

## Сводный план соответствия

| Категория | Bronze blocker | Silver blocker | Gold blocker |
|---|---|---|---|
| Тесты | ✅ config-flow/migration suite | расширять покрытие core paths | покрытие edge cases |
| Diagnostics | — | redacted diagnostics | — |
| Entity model | стабильный unique_id, device_info, translations | reauth flow | расширенные категории |
| Coordinator | реальный coordinator pattern | parallel_updates | — |
| Manifest | ✅ quality_scale + integration_type | — | — |

Подробности — в [`quality-scale.md`](../architecture/quality-scale.md).

## Next reading

- For QS-by-level breakdown: `quality-scale.md`
- For architecture details: `architecture/overview.md`
- For security findings: `security.md`
- For testing plan: `testing/strategy.md`
- For prioritized fixes: `project-audit.md`
