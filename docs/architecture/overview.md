Status: Active
Owner: Architecture Agent
Last reviewed: 2026-05-22

Source files:
- `custom_components/elektronny_gorod/__init__.py`
- `custom_components/elektronny_gorod/config_flow.py`
- `custom_components/elektronny_gorod/coordinator.py`
- `custom_components/elektronny_gorod/api.py`
- `custom_components/elektronny_gorod/http.py`
- `custom_components/elektronny_gorod/camera.py`
- `custom_components/elektronny_gorod/lock.py`
- `custom_components/elektronny_gorod/sensor.py`
- `custom_components/elektronny_gorod/go2rtc.py`

Related docs:
- `project-map.md`
- `source-of-truth.md`
- `ha-compatibility.md`
- `project-audit.md`

Used by agents:
- Architecture, HA Expert, Security, QA

Quality gates:
- ARCHITECTURE_UNDERSTOOD

---

# Architecture Overview

## Бизнес-контекст

Интеграция эмулирует мобильный клиент «Мой Дом» / «Умный Дом.ру», обращающийся к API `myhome.proptech.ru`. Полученные домофоны, камеры и баланс ЛС превращаются в HA entity. Опционально потоки камер пробрасываются через `go2rtc` для получения аудио.

## Высокоуровневая схема

```text
┌─────────────────────────────────────────────────────────────┐
│                        Home Assistant                       │
│                                                             │
│   ┌────────────────┐   async_setup_entry   ┌────────────┐   │
│   │  Config Entry  ├──────────────────────►│Coordinator │   │
│   │ data: tokens,  │                       │ (1x load)  │   │
│   │ user_agent,    │                       └──────┬─────┘   │
│   │ options: g2r   │                              │         │
│   └────────────────┘                              │         │
│                                                   │ get_*() │
│                ┌──────────────┬───────────────────┤         │
│                ▼              ▼                   ▼         │
│          ┌──────────┐   ┌──────────┐        ┌──────────┐    │
│          │ Camera   │   │  Lock    │        │  Sensor  │    │
│          │ entities │   │ entities │        │ balance  │    │
│          └────┬─────┘   └────┬─────┘        └────┬─────┘    │
│               │              │                   │          │
│               └──────────────┴───────────────────┘          │
│                              │                              │
│                              ▼                              │
│                  ┌───────────────────────┐                  │
│                  │  ElektronnyGorodAPI   │                  │
│                  └───────────┬───────────┘                  │
│                              │                              │
│                              ▼                              │
│                  ┌───────────────────────┐                  │
│                  │   HTTP (per-request   │  ◄── 🔴 anti-    │
│                  │   ClientSession)      │      pattern     │
│                  └───────────┬───────────┘                  │
└──────────────────────────────┼──────────────────────────────┘
                               ▼
                ┌──────────────────────────────┐
                │  https://myhome.proptech.ru  │
                └──────────────────────────────┘

  опционально, для камер:
                               ▼
                ┌──────────────────────────────┐
                │       go2rtc HTTP API        │
                └──────────────────────────────┘
```

## Lifecycle

### Установка / setup

```text
HACS → restart HA
  ↓
ConfigFlow.async_step_user
  ↓ (phone OR access_token)
ConfigFlow.async_step_password     OR     ConfigFlow.async_step_contract
  ↓                                        ↓
                                ConfigFlow.async_step_sms
  ↓                                        ↓
ConfigFlow.get_account (фетчит профиль, проверяет на дубль/reauth)
  ↓
ConfigFlow.async_step_go2rtc_menu  → go2rtc OR skip_go2rtc
  ↓
async_create_entry(title, data)
  ↓
async_setup_entry:
  1. hass.data.setdefault(DOMAIN, {})
  2. ElektronnyGorodUpdateCoordinator(hass, entry=entry)
  3. await coordinator.async_config_entry_first_refresh()
     → _async_update_data() → api.query_places() → _subscriber_places
  4. hass.data[DOMAIN][entry_id] = coordinator
  5. entry.async_on_unload(entry.add_update_listener(async_update_options))
  6. await hass.config_entries.async_forward_entry_setups(entry, [CAMERA, LOCK, SENSOR])
     → camera.async_setup_entry → coordinator.get_cameras_info() → создание entity
     → lock.async_setup_entry → coordinator.get_locks_info() → создание entity
     → sensor.async_setup_entry → coordinator.get_balances_info() → создание entity
```

### Migration

```text
HA Loader замечает entry.version < config_flow.VERSION (= 3)
  ↓
async_migrate_entry:
  if version == 1: создать user_agent, сохранить как CONF_USER_AGENT (v2)
  if version == 2: добавить use_go2rtc=False + дефолты base_url, rtsp_host (v3)
```

### Update options

```text
OptionsFlow.async_step_init (go2rtc on/off + base_url)
  ↓ validate_go2rtc()
async_update_listener:
  hass.config_entries.async_reload(entry.entry_id)
  → unload → setup snovа
```

### Unload

```text
async_unload_entry:
  await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
  hass.data[DOMAIN].pop(entry_id)
  🔴 НЕ вызывает coordinator.async_unsubscribe() → утечка слушателя
```

## Слои

| Слой | Файлы | Ответственность |
|---|---|---|
| **HA integration interface** | `__init__.py`, `config_flow.py` | вход/выход в HA, миграции |
| **Domain coordinator** | `coordinator.py` | оркестрация бизнес-логики, in-memory state |
| **API client** | `api.py` | REST-обёртка над эндпоинтами |
| **Transport** | `http.py` | низкоуровневый HTTP, headers, Bearer |
| **External integration** | `go2rtc.py` | go2rtc-специфичный код |
| **Auth crypto** | `helpers.py`, `time.py`, `user_agent.py` | reverse-engineered hashing, эмуляция мобильного клиента |
| **Entities (HA platforms)** | `camera.py`, `lock.py`, `sensor.py` | UI представление |
| **Constants & UI strings** | `const.py`, `strings.json`, `translations/*` | конфиг + локализация |

## State management

| Что | Где хранится | TTL |
|---|---|---|
| Access/refresh tokens | `entry.data` | persistent |
| User-Agent emulation | `entry.data[CONF_USER_AGENT]` (json string) | persistent |
| go2rtc settings | `entry.data` + `entry.options` (options override data) | persistent |
| Список subscriber places | `coordinator._subscriber_places` (in-memory) | 1× load на setup |
| Cameras / Locks / Balances data | runtime через `coordinator.get_*_info()` | каждый запрос |
| Camera last go2rtc src | `Camera._last_src` (in-memory) | сессия |
| Lock state | `Lock._state` (in-memory, синтетический) | фейк-таймер |

🔴 Большая проблема: **places загружаются 1 раз**. Если у пользователя меняется список адресов — это не отразится без `reload`.

## Async-паттерны

- ✅ Все методы корректно `async`/`await`.
- 🔴 `aiohttp.ClientSession()` создаётся per-request в [`http.py:56`](../../custom_components/elektronny_gorod/http.py#L56) — должен использоваться `async_get_clientsession(hass)`.
- ⚠️ `traceback.format_exc()` в [`coordinator.py:68`](../../custom_components/elektronny_gorod/coordinator.py#L68) — блокирующая операция; минор. Заменить на `LOGGER.exception(...)`.
- ❌ Никакого `asyncio.gather` для параллельной загрузки camera/lock/balance per-place.

## Data flow

### Setup flow

```
async_setup_entry
  → coordinator.async_config_entry_first_refresh()
    → coordinator._async_update_data()
      → api.query_places()
        → http.get('/rest/v3/subscriber-places')
  → forward_entry_setups
    → camera.async_setup_entry
      → coordinator.get_cameras_info()
        → для каждого place:
          → api.query_access_controls(place_id)
          → api.query_public_cameras(place_id)
          → api.query_sections(place_id)  ← результат игнорируется! 🔴
          → api.query_cameras(place_id)
        → dedupe_by_id
    → lock.async_setup_entry → analogous
    → sensor.async_setup_entry → analogous
```

### Camera image flow

```
HA UI requests snapshot
  → Camera.async_camera_image(width, height)
    → coordinator.get_camera_snapshot(id, w, h)
      → api.query_camera_snapshot(id, w, h)
        → http.get('/rest/v1/forpost/cameras/<id>/snapshots?...', binary=True)
```

### Camera stream flow

```
HA UI requests stream
  → Camera.stream_source()
    → coordinator.get_camera_stream(id)
      → api.query_camera_stream(id) → FLV URL
    if use_go2rtc:
      → _ensure_go2rtc_stream(flv_url):
        → http.put go2rtc /api/streams (ffmpeg:<flv>#video=copy#audio=aac#audio=opus)
      → return f"rtsp://<rtsp_host>:8554/<stream_name>"
    else:
      → return flv_url
```

### Unlock flow

```
HA service call lock.unlock
  → Lock.async_unlock()
    → state = UNLOCKING; write_ha_state
    → coordinator.open_lock(place_id, ac_id, entrance_id)
      → api.open_lock(...)
        → http.post('/rest/v1/places/<p>/accesscontrols/<a>/[entrances/<e>/]actions', {"name": "accessControlOpen"})
    → state = UNLOCKED OR JAMMED; write_ha_state
  →  через 5 сек fake_timer_lock → state = LOCKED
```

## Error flow

| Слой | Стратегия |
|---|---|
| `api.py` | широкий `except Exception`, переброс как `ValueError("invalid_login"/"unknown_status"/...)` |
| `coordinator._async_update_data` | `UpdateFailed(ex) from ex` |
| `config_flow` | словарь `errors={key: translation_key}` или `async_abort(reason=...)` |
| `lock.async_unlock` | `except ClientError` → state = JAMMED |
| Внешние тайм-ауты | 🔴 не обрабатываются (нет `ClientTimeout`) |
| 429 rate limit | ловится в `request_sms_code` → `limit_exceeded`; в остальных местах не специально |
| 401 unauthorized | ловится в `query_profile` → `unauthorized`; **нет автоматического refresh** |

## Entity model

| Entity | Базовый класс | unique_id | device_info |
|---|---|---|---|
| `ElektronnyGorodCamera` | `Camera` | `f"{id}_{name}"` (⚠️ name — локализованный) | ❌ нет |
| `ElektronnyGorodLock` | `LockEntity` | `f"{place}_{ac}_{entr}_{name}"` (⚠️ нестабилен) | ❌ нет |
| `ElektronnyGorodBalanceSensor` | `SensorEntity` | `f"{DOMAIN}_{place_id}_balance"` ✅ | ❌ нет |

🔴 Никто не наследует `CoordinatorEntity` — это нарушение паттерна координатора.

## Цикличность

Пакет линеен:
```
const ← user_agent ← helpers (только utils)
const ← http
const + http + user_agent ← api
const + api + helpers + user_agent ← coordinator
const + (api в config_flow) ← config_flow
const + coordinator ← camera/lock/sensor
const + go2rtc ← config_flow, camera
```

Циклов нет.

## Большие файлы / god objects

- [`config_flow.py`](../../custom_components/elektronny_gorod/config_flow.py) — 422 строки. На грани, но допустимо (все steps в одном flow).
- [`coordinator.py`](../../custom_components/elektronny_gorod/coordinator.py) — 323 строки, **дубликаты** `get_cameras_info` ↔ `update_camera_state`. Рефакторинг — извлечь `_collect_cameras_for_place(place_id)`.
- [`api.py`](../../custom_components/elektronny_gorod/api.py) — 303 строки, 11 endpoints. На грани, но читаемо.

## Слабые места архитектуры

1. **Coordinator не координирует** — нет `update_interval`, entity ходят в `coordinator.update_*_state` напрямую через свой `async_update`. Идиоматично было бы: `coordinator` тикает раз в N секунд, обновляет `data` (dict), entity подписаны через `CoordinatorEntity._handle_coordinator_update`.
2. **Дубликаты в coordinator** — см. выше.
3. **`available_sections`** извлекаются и игнорируются ([`coordinator.py:109,172`](../../custom_components/elektronny_gorod/coordinator.py#L109)). Либо использовать, либо удалить.
4. **Lock как entity модель не идеальна** — домофон не «закрывается». `button` платформа была бы корректнее. Но это breaking change.
5. **Сильная связанность `coordinator` ↔ `api` ↔ `http`** — нельзя протестировать coordinator без mock-а HTTP.
6. **Эмуляция мобильного клиента в `user_agent.py`** — кросс-слойная связанность через `self._api.http.user_agent.place_id = place_id` в [`coordinator.py:88,151,201,288`](../../custom_components/elektronny_gorod/coordinator.py#L88). Лучше прокидывать place_id через параметры.

## Архитектурные решения (планируемые ADR)

| # | Решение | Статус |
|---|---|---|
| ADR-0001 | Принятие AIDD MVP | proposed |
| ADR-0002 | Перевод entity на `CoordinatorEntity` | proposed (см. ROADMAP Итерация 2) |
| ADR-0003 | Стратегия `iot_class` и polling | proposed |
| ADR-0004 | Token-redaction в логах | proposed (см. SECURITY_AUDIT) |
| ADR-0005 | Lock vs Button для домофона | tbd |

## Next reading

- For source of truth: `source-of-truth.md`
- For HA-checklist: `ha-compatibility.md`
- For findings & priorities: `project-audit.md`
- For security details: `security.md`
- For testing: `testing/strategy.md`
