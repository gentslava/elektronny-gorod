Status: Active
Owner: Project Cartographer Agent
Last reviewed: 2026-06-22

Source files:
- `custom_components/elektronny_gorod/**`
- `tests/**`
- `.github/workflows/**`
- `manifest.json`, `hacs.json`, `info.md`

Related docs:
- `source-of-truth.md`
- `architecture/overview.md`
- `ha-compatibility.md`
- `project-audit.md`

Used by agents:
- Все агенты — обязательное чтение

Quality gates:
- PROJECT_MAP_READY

---

# Project Map

Карта всех ключевых файлов проекта, их назначения и evidence.

## Тип проекта

**Home Assistant custom integration** (`integration_type: hub` — фактически, но не указан в manifest).

- Distribution: **HACS** (см. [`../../hacs.json`](../../hacs.json)).
- Установка: HACS Repository → restart HA → UI config flow.
- Domain: `elektronny_gorod`.
- Версия — в [`manifest.json`](../../custom_components/elektronny_gorod/manifest.json) (поле `version`). В этом документе не фиксируется.

## Структура

```
elektronny-gorod/
├── AGENTS.md                      ← cross-tool agent contract
├── CLAUDE.md                      ← Claude Code adapter
├── conventions.md                 ← code conventions
├── workflow.md                    ← процесс
├── LICENSE                        ← MIT
├── README.md                      ← пользовательская документация (RU)
├── README.en_EN.md                ← минимальная EN-документация
├── info.md                        ← HACS info card
├── hacs.json                      ← HACS manifest
│
├── custom_components/elektronny_gorod/
│   ├── manifest.json              ← HA integration manifest
│   ├── __init__.py                ← entry points + миграции
│   ├── config_flow.py             ← ConfigFlow + OptionsFlow
│   ├── coordinator.py             ← DataUpdateCoordinator
│   ├── api.py                     ← REST API клиент
│   ├── http.py                    ← низкоуровневый HTTP
│   ├── _logging.py                ← redact() + SENSITIVE_KEYS (ADR-0004)
│   ├── camera.py                  ← Camera platform + go2rtc + auto-recovery
│   ├── lock.py                    ← Lock platform
│   ├── sensor.py                  ← Sensor (balance + days-to-block) platform
│   ├── binary_sensor.py           ← account_blocked platform
│   ├── switch.py                  ← DND switches platform
│   ├── event.py                   ← doorbell call event platform (ADR-0011)
│   ├── fcm.py                     ← FCM listener для события вызова (ADR-0011)
│   ├── go2rtc.py                  ← go2rtc валидация / upsert
│   ├── entity_migration.py        ← стабильные unique_id + registry migration
│   ├── diagnostics.py             ← redact-нутая diagnostics-выгрузка (S-08)
│   ├── helpers.py                 ← utils + auth crypto
│   ├── user_agent.py              ← эмуляция Android-клиента
│   ├── time.py                    ← timestamp helpers
│   ├── const.py                   ← константы
│   ├── strings.json               ← UI-строки
│   └── translations/
│       ├── ru.json
│       └── en.json
│
├── tests/                          ← pytest suite (PHC-based, зелёный)
│   ├── conftest.py
│   └── …                          ← см. таблицу тестов ниже
│
├── .github/workflows/
│   ├── hassfest.yaml              ← manifest validation
│   ├── hacs.yaml                  ← HACS validation
│   ├── release.yaml               ← release zip + auto-commit (на event release)
│   └── prerelease.yaml            ← PR pre-release zip (на event pull_request)
│
├── .claude/                       ← Claude Code конфигурация (Full AIDD)
│   ├── agents/                    ← 5 субагентов (HA-expert, security, QA, ...)
│   ├── commands/                  ← slash-команды
│   ├── rules/                     ← path-specific правила
│   ├── hooks/                     ← bash-хуки (pre-commit redaction, etc.)
│   └── settings.json
│
├── .cursor/rules/                 ← правила Cursor (Full AIDD)
├── .github/copilot-instructions.md ← инструкции для Copilot
│
└── docs/                          ← AIDD-документация (см. ниже)
```

## Ключевые файлы

### Метаданные и публикация

| Файл | Назначение | Evidence |
|---|---|---|
| [`manifest.json`](../../custom_components/elektronny_gorod/manifest.json) | HA integration manifest: domain, version, iot_class, config_flow | строки 1-14 |
| [`hacs.json`](../../hacs.json) | HACS publishing: min HA version, zip release, country=RU | строки 1-7 |
| [`info.md`](../../info.md) | HACS info card | — |
| [`README.md`](../../README.md) / [`README.en_EN.md`](../../README.en_EN.md) | пользовательская документация | — |
| [`LICENSE`](../../LICENSE) | MIT | — |

### Entry points

| Файл | Назначение | Evidence |
|---|---|---|
| [`__init__.py`](../../custom_components/elektronny_gorod/__init__.py) | `async_setup_entry` (включая старт `DoorbellFcmListener` — ADR-0011), `async_unload_entry`, `async_migrate_entry` (v1→2→3) | — |
| [`PLATFORMS`](../../custom_components/elektronny_gorod/__init__.py) | BINARY_SENSOR, CAMERA, EVENT, LOCK, SENSOR, SWITCH | — |

### Config flow

| Файл | Назначение | Evidence |
|---|---|---|
| [`config_flow.py`](../../custom_components/elektronny_gorod/config_flow.py) | ConfigFlow v3: user → (password \| contract → sms) → go2rtc_menu → CREATE_ENTRY. Поддерживает optional go2rtc username/password. | — |
| [`config_flow.py`](../../custom_components/elektronny_gorod/config_flow.py) | OptionsFlow (go2rtc, включая username/password) | 386-450 |

### Бизнес-логика

| Файл | Назначение | Особенности |
|---|---|---|
| [`coordinator.py`](../../custom_components/elektronny_gorod/coordinator.py) | `DataUpdateCoordinator` | `update_interval=5min`, `_async_update_data` → `{places, balances, cameras, locks}` (ADR-0002) |
| [`api.py`](../../custom_components/elektronny_gorod/api.py) | REST endpoints: auth, profile, places, access controls, cameras, locks, balance, screens, finance, push-registration (`register_push_device` / `unregister_push_device` — привязка FCM-токена у оператора, ADR-0011) | использует shared `HTTP` (ADR-0008) |
| [`http.py`](../../custom_components/elektronny_gorod/http.py) | низкоуровневый HTTP | shared `async_get_clientsession(hass)` (ADR-0008); per-request copy headers; Bearer не шлётся на `/auth/*`; `redact_path()` в error log |

### Платформы (entity)

| Файл | Платформа | Особенности |
|---|---|---|
| [`camera.py`](../../custom_components/elektronny_gorod/camera.py) | `camera` | `CoordinatorEntity`, stable `unique_id=elektronny_gorod_camera_{id}`, STREAM + опциональный proxy через go2rtc, intercom-камера группируется с lock через entrance_uid |
| [`lock.py`](../../custom_components/elektronny_gorod/lock.py) | `lock` | `CoordinatorEntity`, stable `unique_id=elektronny_gorod_lock_{place}_{ac}_{eid\|main}`, synthetic state через `async_call_later` (без блокировки event loop) |
| [`sensor.py`](../../custom_components/elektronny_gorod/sensor.py) | `sensor` | (1) `balance` — `device_class=MONETARY` + long-term statistics. (2) `days_to_block` (A-57) — `device_class=DURATION` + `unit=d` |
| [`switch.py`](../../custom_components/elektronny_gorod/switch.py) | `switch` | Do Not Disturb (mirror «Мой Дом» → Настройки → Уведомления). 3 entity per place: master `dnd_root` + 2 dependent (`dnd_intercom_calls`, `dnd_management_company_calls`). Dependent `_attr_available = root.status` — HA нативно красит серым при master OFF |
| [`binary_sensor.py`](../../custom_components/elektronny_gorod/binary_sensor.py) | `binary_sensor` | `blocked` (A-57): `device_class=PROBLEM`, `True` когда `blocked=True` в `/finance`. Реюзает balance device через identifier `(DOMAIN, place_{id})` |
| [`event.py`](../../custom_components/elektronny_gorod/event.py) | `event` | Doorbell call (ADR-0011): `device_class=DOORBELL`, типы `ring`/`ended`. Одна сущность на домофон `(place_id, access_control_id)`, дедуп по AC (min entrance), device общий с lock/intercom-camera. Ловит `SIGNAL_DOORBELL` из `fcm.py` через dispatcher, стреляет `_trigger_event` с атрибутами (gate/apartment/call_id/allow_open/…). Открытие двери — существующий `lock`, видео — go2rtc |

### Внешние интеграции

| Файл | Назначение |
|---|---|
| [`go2rtc.py`](../../custom_components/elektronny_gorod/go2rtc.py) | validate_go2rtc (GET /api + PUT /api/streams + cleanup), upsert stream, derive_rtsp_host |
| [`fcm.py`](../../custom_components/elektronny_gorod/fcm.py) | `DoorbellFcmListener` (ADR-0011): эмуляция регистрации Android-устройства в FCM (`firebase-messaging`, Firebase-конфиг приложения в `const.py:FCM_*`) → привязка токена у оператора (`api.register_push_device`) → MTalk-сокет. Парсит `CALL_INCOMING` / `CALL_END_ANSWERED_MOBILE` → `SIGNAL_DOORBELL`. Весь флоу под graceful degradation (приватные API Google) — сбой не валит setup. FCM-creds персистятся в `entry.data` |

### Diagnostics / безопасность

| Файл | Назначение |
|---|---|
| [`_logging.py`](../../custom_components/elektronny_gorod/_logging.py) | `redact()` + `SENSITIVE_KEYS` + `redact_path()` (ADR-0004) |
| [`diagnostics.py`](../../custom_components/elektronny_gorod/diagnostics.py) | `async_get_config_entry_diagnostics` + `TO_REDACT` (S-08/S-16); coordinator-снимок = только счётчики |

### Утилиты

| Файл | Назначение | Особенности |
|---|---|---|
| [`helpers.py`](../../custom_components/elektronny_gorod/helpers.py) | `find`, `dedupe_by_id`, `hash_password` (SHA1+base64), `hash_password_timestamp` (MD5 с reverse-engineered prefix/secret) | ⚠️ hardcoded «соль» |
| [`user_agent.py`](../../custom_components/elektronny_gorod/user_agent.py) | эмуляция Android (Pixel 6-10) — выбирается случайно | ⚠️ ToS-зона серого |
| [`time.py`](../../custom_components/elektronny_gorod/time.py) | timestamp для auth | ⚠️ local time, не UTC |
| [`const.py`](../../custom_components/elektronny_gorod/const.py) | константы, APP_VERSION, ANDROID_DEVICES | — |

### Локализация

| Файл | Назначение |
|---|---|
| [`strings.json`](../../custom_components/elektronny_gorod/strings.json) | source UI-строк |
| [`translations/ru.json`](../../custom_components/elektronny_gorod/translations/ru.json) | RU |
| [`translations/en.json`](../../custom_components/elektronny_gorod/translations/en.json) | EN |

### Тесты

| Файл | Статус |
|---|---|
| [`tests/conftest.py`](../../tests/conftest.py) | fixtures + `enable_custom_integrations` auto-applied |
| [`tests/test_entity_migration.py`](../../tests/test_entity_migration.py) | unit-тесты `_camera_new_uid`/`_lock_new_uid` + golden vector для `lock_unique_id` |
| [`tests/test_logging_redact.py`](../../tests/test_logging_redact.py) | unit-тесты `_logging.redact()` + `redact_path()` |
| [`tests/test_diagnostics.py`](../../tests/test_diagnostics.py) | redaction secrets/options, non-sensitive preserved, coordinator counts-only, TO_REDACT ⊇ SENSITIVE_KEYS |
| [`tests/test_http.py`](../../tests/test_http.py) | Bearer skip на pre-auth, no-leak между запросами, PII redact в error log |
| [`tests/test_visibility.py`](../../tests/test_visibility.py) | hidden_by sync (first_add, USER override, un-hide, re-add) |
| [`tests/test_visibility_real.py`](../../tests/test_visibility_real.py) | production-replica (реальные HAR-данные) + migration v2 |
| [`tests/test_event.py`](../../tests/test_event.py) | doorbell `event`-сущность (ADR-0011): дедуп по AC, фильтр SIGNAL по `(place_id, ac_id)`, `_trigger_event` на `ring`/`ended`, игнор чужого/неизвестного event_type |
| [`tests/test_api_push.py`](../../tests/test_api_push.py) | `register_push_device` / `unregister_push_device`: тело-зеркало (POST с `pushToken` на `device-installations` + `subscriberNotifications`, DELETE без `pushToken`), graceful False на ошибке |
| [`tests/test_fcm.py`](../../tests/test_fcm.py) | `DoorbellFcmListener`: парсинг `CALL_INCOMING` / `CALL_END_ANSWERED_MOBILE` → SIGNAL, graceful degradation при недоступной `firebase-messaging` / сбое start, персист FCM-creds в `entry.data` |
| [`pytest.ini`](../../pytest.ini) | `asyncio_mode = auto`, `testpaths = tests` |

### CI / CD

| Workflow | Триггер | Назначение |
|---|---|---|
| [`hassfest.yaml`](../../.github/workflows/hassfest.yaml) | push / PR | manifest validation |
| [`hacs.yaml`](../../.github/workflows/hacs.yaml) | push / PR / dispatch | HACS validation |
| [`prerelease.yaml`](../../.github/workflows/prerelease.yaml) | PR opened / sync | pre-release ZIP с тегом `pr-N` для тестирования |
| [`release.yaml`](../../.github/workflows/release.yaml) | release published | zip + GH release + автокоммит версии |

🟡 **Отсутствует workflow для pytest** — все 67 тестов проходят локально (`PYTHONPATH=. pytest tests/`), но CI ещё не настроен. Tracking: roadmap → Tests-1.

## Внешние API и зависимости

| Внешний ресурс | Назначение |
|---|---|
| `https://myhome.proptech.ru` | основной API («Мой дом») |
| `go2rtc HTTP API` | опционально, для камер с аудио |
| FCM / Firebase (конфиг приложения в `const.py:FCM_*`) | realtime-канал события вызова домофона (ADR-0011); приём через приватные API Google под graceful degradation |

**Python-зависимости:**
- из HA core (`aiohttp`, `voluptuous`, `yarl`);
- `manifest.json:requirements` — `firebase-messaging>=0.4` (FCM-приём события вызова, ADR-0011; тянет protobuf / http_ece / cryptography).

## Maintenance rules

Две оси (ADR-0010). **Ось A** — «изменён код-файл → обнови docs». **Ось B** —
«изменилось состояние (finding/CI/quality_scale) → обнови docs». Раньше была
только ось A — поэтому `summary.md`/`AGENTS.md`/state-таблицы гнили (D-04).

### Ось A — код-файл → docs

| Если изменён | Обновить |
|---|---|
| `manifest.json` | `project-map.md`, `ha-compatibility.md`, `source-of-truth.md` |
| `hacs.json` / `info.md` | `project-map.md`, `source-of-truth.md` |
| `config_flow.py` | `architecture/overview.md`, `testing/strategy.md`, `ha-compatibility.md` |
| `coordinator.py` | `architecture/overview.md`, `testing/strategy.md`, `project-audit.md` |
| `camera.py` / `lock.py` / `sensor.py` | `architecture/overview.md`, `testing/strategy.md`, `quality-scale.md` |
| `api.py` / `http.py` | `architecture/overview.md`, `security.md`, `project-audit.md` |
| `helpers.py` (crypto) | `security.md` |
| `strings.json` / `translations/*` | `ha-compatibility.md` |
| `tests/**` | `testing/strategy.md`, `quality-gates.md` |
| `.github/workflows/**` | `contributing.md`, `quality-gates.md`, `roadmap.md` |
| новый/удалённый файл в `custom_components/` | `project-map.md`, `AGENTS.md` (`Project structure`) |
| `README.md` | `summary.md`, `index.md` |
| `AGENTS.md` / `CLAUDE.md` (self-описание: стек, hooks, setup) | взаимная сверка обоих + `contributing.md` |

### Ось B — событие состояния → docs

| Событие | Обновить |
|---|---|
| finding → `✅ RESOLVED` (merged в master) | `summary.md` (риски), `CHANGELOG.md`, снять `🔴` в `AGENTS.md` `Project structure` если упоминался |
| finding → `🟢 resolved-in-branch` | `project-audit.md` (статус + `pending merge <ref>`), **не** трогать `summary.md` риски до merge |
| новый finding (A-NN / S-NN) | `project-audit.md` (+ `security.md` если security), `summary.md` риски если P0/P1 |
| разрешён known-антипаттерн в коде | `AGENTS.md` `Project structure` (снять метку), `summary.md` |
| изменилось CI / тест-состояние | `summary.md` «Состояние»; `quality-gates.md` — только ссылкой, не копией |
| изменён `manifest:quality_scale` | сверить с гейтом (D-05); при несоответствии — finding в `project-audit.md` |

🔴 **Запрет (ADR-0010):** дублировать «текущее состояние» в нескольких доках.
Единый источник — `project-audit.md` + `summary.md`. Остальное ссылается.

## Next reading

- For source of truth: `source-of-truth.md`
- For architecture: `architecture/overview.md`
- For HA-checklist: `ha-compatibility.md`
- For audit findings: `project-audit.md`
