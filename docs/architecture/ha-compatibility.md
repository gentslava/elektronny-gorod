Status: Active
Owner: Home Assistant Expert Agent
Last reviewed: 2026-05-22

Source files:
- `custom_components/elektronny_gorod/manifest.json`
- `custom_components/elektronny_gorod/config_flow.py`
- `custom_components/elektronny_gorod/coordinator.py`
- `custom_components/elektronny_gorod/__init__.py`
- `custom_components/elektronny_gorod/camera.py`
- `custom_components/elektronny_gorod/lock.py`
- `custom_components/elektronny_gorod/sensor.py`
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
| `requirements` | `[]` | все вне HA core | ✅ |
| `dependencies` | `[]` | HA-интеграции, нужные при старте | ✅ |
| `iot_class` | `cloud_polling` | соответствие реальности | 🔴 **НЕТ polling в coordinator** |
| `config_flow` | `true` | если есть UI flow | ✅ |
| `integration_type` | ❌ отсутствует | `hub` | 🔴 добавить |
| `quality_scale` | ❌ отсутствует | `bronze`/`silver`/... | 🔴 добавить (после фиксов — `bronze`) |
| `after_dependencies` | ❌ | при необходимости | n/a |

## HACS / hacs.json

| Поле | Текущее | Замечание |
|---|---|---|
| `name` | `Электронный город` | ✅ |
| `homeassistant` | `2022.8.0` | 🔴 неверно — реальная min ≥ 2024.1 |
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
| Tests | 🔴 нет реальных | `tests/test_config_flow.py` — stub |
| `show_advanced_options` ветка | ✅ есть | `config_flow.py:111-117` |

## Coordinator / Data Fetching

| Критерий | Статус | Файл:строка |
|---|---|---|
| Использование `DataUpdateCoordinator` | ✅ номинально | `coordinator.py:29` |
| `name` задано | ✅ `name=DOMAIN` | `coordinator.py:55` |
| `update_interval` задан | 🔴 **НЕТ** | `coordinator.py:32-55` |
| `_async_update_data` реализован | ⚠️ да, но грузит места только 1 раз и не возвращает `data` | `coordinator.py:62-69` |
| Возвращаемое `data` используется entity | ❌ entity ходят через свои `update_*_state` методы | `sensor.py:83-91`, `camera.py:191-193`, `lock.py:117-124` |
| `UpdateFailed` при ошибке | ✅ | `coordinator.py:69` |
| Timeout per request | 🔴 нет `ClientTimeout` | `http.py` |
| Retry / backoff | 🔴 нет | `api.py`, `http.py` |
| Rate limiting | 🔴 нет | — |
| Caching | 🔴 нет | — |
| Никаких blocking ops в loop | ⚠️ `traceback.format_exc` минор | `coordinator.py:68` |
| `async_unsubscribe` вызывается при unload | 🔴 нет, утечка слушателя | `__init__.py:89-94` vs `coordinator.py:71-74` |
| Использование `async_get_clientsession(hass)` | 🔴 нет, `ClientSession()` per-request | `http.py:56` |

## Entities

| Критерий | Camera | Lock | Sensor (balance) |
|---|---|---|---|
| Наследует `CoordinatorEntity` | ❌ | ❌ | ❌ |
| `_attr_has_entity_name` | ❌ | ❌ | ❌ |
| `_attr_translation_key` | ❌ | ❌ | ❌ |
| `unique_id` стабилен | ⚠️ `f"{id}_{name}"` | 🔴 содержит `name` | ✅ `f"{DOMAIN}_{place_id}_balance"` |
| `device_info` | ❌ | ❌ | ❌ |
| `device_class` | n/a | ❌ нет | 🔴 нет (должен быть `MONETARY`) |
| `state_class` | n/a | n/a | 🔴 нет (`MEASUREMENT`) |
| `native_unit_of_measurement` | n/a | n/a | 🔴 `"₽"` (должен `"RUB"` / `CURRENCY_RUBLE`) |
| `available` | default | ⚠️ `self._openable` (может быть None) | default |
| `entity_category` | n/a | n/a | можно `diagnostic` |
| Корректное обновление через coordinator | ❌ через свой `async_update` | ❌ свой `async_update` + fake-timer | ❌ свой `async_update` |
| Хардкод русского имени | ✅ (использует `camera_info.name`) | ✅ (использует `lock_info.name`) | 🔴 `"Баланс аккаунта"` |

## Diagnostics / Repairs / Services

| Артефакт | Наличие | Приоритет |
|---|---|---|
| `diagnostics.py` | ❌ | P1 — критично, в `entry.data` есть токены |
| `repairs.py` | ❌ | P2 |
| `services.yaml` (свои сервисы) | ❌ | n/a |
| Поддержка `system_health` | ❌ | P3 |

## Translations

| Файл | Статус |
|---|---|
| `strings.json` | ✅ source |
| `translations/ru.json` | ✅ соответствует |
| `translations/en.json` | ✅ соответствует |
| **Entity translations** (отдельный раздел в `strings.json:entity`) | ❌ — entity имеют хардкод-имена |

## Платформы и manifest dependencies

PLATFORMS: `[CAMERA, LOCK, SENSOR]` ([`__init__.py:25-29`](../../custom_components/elektronny_gorod/__init__.py#L25-L29)).

Зависимости HA-core (`dependencies` в manifest): пусто. Фактически используются:
- `homeassistant.components.persistent_notification` ([`coordinator.py:8`](../../custom_components/elektronny_gorod/coordinator.py#L8)) — должен быть в `dependencies` или `after_dependencies`.
- `homeassistant.components.camera`, `lock`, `sensor` — стандартные платформы, явные declarations не нужны.

## CI / Validation

| Workflow | Назначение | Статус |
|---|---|---|
| `hassfest.yaml` | manifest validation | ✅ есть |
| `hacs.yaml` | HACS validation | ✅ есть |
| **pytest workflow** | unit tests | 🔴 отсутствует |
| `release.yaml` | release zip + autocommit | ✅ есть |

## Brand assets

- `README.md` ссылается на `https://brands.home-assistant.io/elektronny_gorod/icon.png` — нужно проверить, добавлен ли brand в [home-assistant/brands](https://github.com/home-assistant/brands) репозиторий.

## Сводный план соответствия

| Категория | Bronze blocker | Silver blocker | Gold blocker |
|---|---|---|---|
| Тесты | реальный config_flow test | покрытие core paths | покрытие edge cases |
| Diagnostics | — | redacted diagnostics | — |
| Entity model | стабильный unique_id, device_info, translations | reauth flow | расширенные категории |
| Coordinator | реальный coordinator pattern | parallel_updates | — |
| Manifest | quality_scale, integration_type | — | — |

Подробности — в [`quality-scale.md`](../architecture/quality-scale.md).

## Next reading

- For QS-by-level breakdown: `quality-scale.md`
- For architecture details: `architecture/overview.md`
- For security findings: `security.md`
- For testing plan: `testing/strategy.md`
- For prioritized fixes: `project-audit.md`
