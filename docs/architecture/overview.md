Status: Active
Owner: Architecture Agent
Last reviewed: 2026-07-13 (PR #69: stock pre-answer REGISTER/100 Trying,
video anti-churn, held caller switching, FCM-ended guard; A-54/A-58/A-81/A-85 в master)

Source files:
- `custom_components/elektronny_gorod/__init__.py`
- `custom_components/elektronny_gorod/config_flow.py`
- `custom_components/elektronny_gorod/coordinator.py`
- `custom_components/elektronny_gorod/api.py`
- `custom_components/elektronny_gorod/http.py`
- `custom_components/elektronny_gorod/_logging.py`
- `custom_components/elektronny_gorod/entity_migration.py`
- `custom_components/elektronny_gorod/camera.py`
- `custom_components/elektronny_gorod/call_camera.py`
- `custom_components/elektronny_gorod/lock.py`
- `custom_components/elektronny_gorod/sensor.py`
- `custom_components/elektronny_gorod/switch.py`
- `custom_components/elektronny_gorod/go2rtc.py`
- `custom_components/elektronny_gorod/uplink_ws.py`
- `custom_components/elektronny_gorod/sip/`

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

Интеграция эмулирует мобильный клиент «Мой Дом» / «Умный Дом.ру», обращающийся к API `myhome.proptech.ru`. Полученные домофоны, камеры, балансы ЛС и DND-настройки превращаются в HA entity. Опционально потоки камер пробрасываются через `go2rtc` для получения аудио. Подробности про mirror-стратегию — см. [ADR-0006](../decisions/0006-mirror-app-behavior.md).

## Высокоуровневая схема

```text
┌────────────────────────────────────────────────────────────────┐
│                         Home Assistant                         │
│                                                                │
│   ┌────────────────┐   async_setup_entry   ┌────────────────┐  │
│   │  Config Entry  ├──────────────────────►│  Coordinator   │  │
│   │ data: tokens,  │                       │ DataUpdate-    │  │
│   │ user_agent,    │                       │ Coordinator    │  │
│   │ options: g2r   │                       │ interval=5min  │  │
│   └────────────────┘                       └────────┬───────┘  │
│                                                     │ data     │
│                                                     │ {places, │
│                                                     │  cameras,│
│                                                     │  locks,  │
│                                                     │  balances│
│                                                     │  dnd}    │
│                                                     ▼          │
│         ┌────────────┬─────────────┬───────────────────┐       │
│         ▼            ▼             ▼                   ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       ┌──────────┐   │
│  │ Camera   │  │  Lock    │  │ Balance  │       │  DND     │   │
│  │ entities │  │ entities │  │  Sensor  │       │ Switches │   │
│  │ (Coord-  │  │ (Coord-  │  │ (Coord-  │       │ (Coord-  │   │
│  │ Entity)  │  │ Entity)  │  │ Entity)  │       │ Entity)  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       └────┬─────┘   │
│       │             │             │                  │         │
│       └─────────────┴─────────────┴──────────────────┘         │
│                              │                                 │
│                              ▼                                 │
│                  ┌───────────────────────┐                     │
│                  │  ElektronnyGorodAPI   │                     │
│                  └───────────┬───────────┘                     │
│                              │                                 │
│                              ▼                                 │
│                  ┌───────────────────────┐                     │
│                  │  HTTP (shared HA      │                     │
│                  │  ClientSession via    │  ADR-0008           │
│                  │  async_get_client-    │                     │
│                  │  session(hass))       │                     │
│                  └───────────┬───────────┘                     │
└──────────────────────────────┼─────────────────────────────────┘
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
     → _async_update_data() → собирает один snapshot:
       places + per-place {balance, cameras, locks, dnd}
       → coordinator.data: dict[str, Any]
  4. hass.data[DOMAIN][entry_id] = coordinator
  5. async_migrate_entity_unique_ids — legacy `{id}_{name}` → stable формат (A-12)
  6. entry.async_on_unload(coordinator.async_unsubscribe)
     entry.async_on_unload(entry.add_update_listener(async_update_options))
  7. await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
     → каждая платформа читает `coordinator.data` и создаёт entity:
       - camera.async_setup_entry: data["cameras"] → ElektronnyGorodCamera
       - lock.async_setup_entry:   data["locks"]   → ElektronnyGorodLock
       - sensor.async_setup_entry: data["balances"] → ElektronnyGorodBalanceSensor
       - switch.async_setup_entry: data["dnd"]      → ElektronnyGorodDNDSwitch (×3 per place)
  8. _migrate_legacy_disabled_state (one-time per entry)
  9. _sync_visibility — `hidden` из `/settings/screens` → entity.hidden_by=INTEGRATION
  10. async_register_uplink_ws_command(hass) — WS-команда intercom_uplink (ADR-0013)
  11. await async_register_uplink_card(hass) — static-ресурс Lovelace-карты микрофона
     (оба идемпотентны, регистрируются один раз на интеграцию — см. `__init__.py:~100`)
```

### Migration

```text
HA Loader замечает entry.version < config_flow.VERSION (= 3)
  ↓
async_migrate_entry:
  if version == 1: создать user_agent, сохранить как CONF_USER_AGENT (v2)
  if version == 2: добавить use_go2rtc=False + дефолты base_url, rtsp_host (v3)

Параллельно (вызывается из async_setup_entry, не из async_migrate_entry):
- async_migrate_entity_unique_ids — миграция camera/lock UID на stable формат.
- _migrate_legacy_disabled_state  — one-time cleanup `disabled_by` markers
  от legacy visibility-логики (флаг в entry.options).
```

### Update options

```text
OptionsFlow.async_step_init (go2rtc on/off + base_url)
  ↓ validate_go2rtc()
async_update_options:
  hass.config_entries.async_reload(entry.entry_id)
  → unload → setup snova
```

### Unload

```text
async_unload_entry:
  await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
  if unload_ok: hass.data[DOMAIN].pop(entry_id)
  ── coordinator.async_unsubscribe вызывается HA-core автоматически через
     `entry.async_on_unload`, независимо от исхода unload платформ (A-16).
```

## Слои

| Слой | Файлы | Ответственность |
|---|---|---|
| **HA integration interface** | `__init__.py`, `config_flow.py` | вход/выход в HA, миграции, entity visibility sync |
| **Domain coordinator** | `coordinator.py` | оркестрация refresh, snapshot `coordinator.data` |
| **Entity migration** | `entity_migration.py` | stable `unique_id` для camera/lock (legacy → new) |
| **API client** | `api.py` | REST-обёртка над эндпоинтами `myhome.proptech.ru`; включая `mint_sip_device` (A-81) |
| **Transport** | `http.py` | shared HA `ClientSession`, headers, conditional Bearer |
| **Logging redaction** | `_logging.py` | `redact()` для headers/dict, `redact_path()` для auth URLs |
| **External integration** | `go2rtc.py` | go2rtc-специфичный код (validate + upsert/cleanup); `upsert_audio_stream` / `remove_audio_stream` для аудио-стрима вызова |
| **SIP subsystem** | `sip/` (14 модулей) | SIP-UAS: REGISTER-on-ring → held-INVITE → 200 OK → RTP-latching; AudioBridge (downlink → go2rtc); `uplink.py` `UplinkSink` (микрофон-PCM → G.711) + дрейф-компенсированный RTP-uplink (`rtp.py`); ADR-0012, ADR-0013 |
| **Uplink transport** | `uplink_ws.py`, `www/eg-intercom-mic-card.js` | WS-команда `elektronny_gorod/intercom_uplink` (`async_register_binary_handler`): Int16-PCM микрофона из Lovelace-карты `getUserMedia` → `DoorbellCallController.feed_uplink` → `UplinkSink`; static-регистрация JS-карты (ADR-0013) |
| **Call camera** | `call_camera.py` | camera-сущность активного вызова: `stream_source()` собирает свежий `eg_intercom_call` (видео + аудио-мост) → RTSP; вне вызова → `None` |
| **FCM listener** | `fcm.py` | `DoorbellFcmListener` — FCM-триггер вызова → `SIGNAL_DOORBELL` → `DoorbellCallController.handle_signal` |
| **Auth crypto** | `helpers.py`, `time.py`, `user_agent.py` | reverse-engineered hashing, эмуляция мобильного клиента |
| **Entities (HA platforms)** | `camera.py`, `lock.py`, `sensor.py`, `switch.py`, `event.py`, `binary_sensor.py` | UI представление, все `CoordinatorEntity[...]`; `event.py` — doorbell call event (ADR-0011) |
| **Constants & UI strings** | `const.py`, `strings.json`, `translations/*` | конфиг + локализация |

## State management

| Что | Где хранится | TTL |
|---|---|---|
| Access/refresh tokens | `entry.data` | persistent |
| User-Agent emulation | `entry.data[CONF_USER_AGENT]` (json string) | persistent |
| go2rtc settings | `entry.data` + `entry.options` (options override data) | persistent |
| Snapshot всего: `{places, balances, cameras, locks, dnd}` | `coordinator.data` (dict) | обновляется каждые 5 минут |
| Synthetic lock state cycle | `Lock._state` + `_cancel_reset` (in-memory) | 5 сек на unlock action |
| Camera last go2rtc src | `Camera._last_src` (in-memory) | сессия |
| Visibility migration flag | `entry.options["visibility_migration_v2"]` | one-time per entry |

Интервал refresh — 5 минут (`UPDATE_INTERVAL` в `coordinator.py`); см. [ADR-0003](../decisions/0003-iot-class-strategy.md).

## Async-паттерны

- ✅ Все методы корректно `async`/`await`.
- ✅ HTTP через `async_get_clientsession(hass)` ([ADR-0008](../decisions/0008-shared-client-session.md)) — никаких per-request `ClientSession()`.
- ✅ `Authorization: Bearer` не отправляется на pre-auth paths (`/auth/*`) — иначе backend видит expired Bearer и отдаёт 401 даже на login, блокируя reauth (см. `http.py` `__request`).
- ✅ Token-redaction: `_logging.redact()` для headers (case + dash-insensitive), `_logging.redact_path()` маскирует PII в `/auth/v*/*/{phone|contract|account_id}` URL-path.
- ✅ Lock `async_unlock` использует `async_call_later` для возврата state→LOCKED (без `asyncio.sleep` в event loop).
- ✅ `LOGGER.exception(...)` вместо блокирующего `traceback.format_exc()` в hot path.
- ⚠️ **Serial-per-place refresh** в `_async_update_data`: parallelize нельзя без рефакторинга, т.к. `self._api.http.user_agent.place_id` — shared state, читаемое в момент построения HTTP-headers. См. module docstring `coordinator.py`. Race-free, но не оптимально по latency.
- ✅ Operator API использует явные REST/binary `ClientTimeout` (A-21/S-09);
  retry/backoff для идемпотентных GET остаётся follow-up.

## Data flow

### Setup flow

```
async_setup_entry
  → coordinator.async_config_entry_first_refresh()
    → coordinator._async_update_data()
      → api.query_places()
        → http.get('/rest/v3/subscriber-places')
      → для каждого place_id (serial):
        → set self._api.http.user_agent.place_id = place_id
        → _fetch_balance(place_id)            → api.query_balance
        → _collect_cameras_for_place(place_id) → screens + access_controls
                                               + place_cameras + public_cameras
        → _collect_locks_for_place(place_id)   → access_controls (+ screens hidden)
        → _fetch_dnd(place_id)                 → api.query_dnd_settings
      → dedupe_by_id(cameras)
      → return {places, balances, cameras, locks, dnd}
  → async_migrate_entity_unique_ids(coordinator.data)
  → forward_entry_setups
    → каждая платформа читает coordinator.data и async_add_entities(...)
```

### Camera image flow

```
HA UI requests snapshot
  → Camera.async_camera_image(width, height)
    if not self.available: return None
    → coordinator.get_camera_snapshot(id, w, h)   ← on-demand action
      → api.query_camera_snapshot(id, w, h)
        → http.get('/rest/v1/forpost/cameras/<id>/snapshots?...', binary=True)
```

### Camera stream flow

```
HA UI requests stream
  → Camera.stream_source()
    → coordinator.get_camera_stream(id)           ← on-demand action
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
    → self._state = UNLOCKING; async_write_ha_state
    → coordinator.open_lock(place_id, ac_id, entrance_id)
      → api.open_lock(...)
        → http.post('/rest/v1/places/<p>/accesscontrols/<a>/[entrances/<e>/]actions',
                    {"name": "accessControlOpen"})
    if ClientError:
      → self._state = JAMMED; _schedule_reset(LOCK_JAMMED_DELAY)
    else:
      → self._state = UNLOCKED; _schedule_reset(LOCK_UNLOCK_DELAY)
    → async_call_later(hass, delay, _restore_locked):
        when fires: self._state = LOCKED; async_write_ha_state
```

### Doorbell call / SIP two-way audio flow (ADR-0011, ADR-0012)

```
Домофон нажата кнопка
  → FCM CALL_INCOMING (fcm.py DoorbellFcmListener)
    → SIGNAL_DOORBELL → event.py (ring) + DoorbellCallController.handle_signal
      → api.mint_sip_device(place_id, ac_id)   ← SIP-креды
        → sip/manager.py SipManager.register_and_hold()
          → sip/protocol.py: UDP REGISTER (Expires=30, push-params) → 200 OK от сервера
          → ждём forked INVITE → sip/message.py parse → 100 Trying (hold)
    ← экран вызова: timer ~30с (CallInvalidated)
    ← ElektronnyGorodCallCamera.stream_source() → None (нет активного вызова)

  Пользователь «Ответить» → сервис elektronny_gorod.answer
    → DoorbellCallController.answer(call_id)
      → SipManager.accept(on_downlink)
        → sip/dialog.py build_200_ok (эхо Via/Record-Route) → UDP ответ
        → sip/rtp.py: uplink G.711 + STUN-keepalive (активируют RTP-latching)
        → downlink: on_downlink(frame) → sip/bridge.py AudioBridge.feed_downlink()
          → ffmpeg: G.711 → mpegts/aac → HTTP-сервер (:40020)
          → go2rtc: upsert_audio_stream(eg_intercom_call, [video_rtsp, http://bridge])
      → ElektronnyGorodCallCamera.stream_source() → eg_intercom_call → RTSP → HA-native WebRTC → браузер

  Uplink (говорить гостю, ADR-0013):
    Lovelace-карта getUserMedia → Int16 PCM по HA-WS elektronny_gorod/intercom_uplink
      → uplink_ws.ws_intercom_uplink (async_register_binary_handler)
        → DoorbellCallController.feed_uplink(pcm, rate)
          → sip/uplink.py UplinkSink.feed() → resample 8к → G.711-кадры (джиттер-буфер)
      → SipManager.uplink_provider (= UplinkSink.next_frame)
        → sip/rtp.py run_uplink: дрейф-компенсированный пейсинг → RTP G.711 → домофон

  Сброс с панели → SIP CANCEL → sip/protocol.py → on_cancelled
    → EVENT_SIP_CALL active=false → dismiss экрана мгновенно

  «Положить трубку» → сервис elektronny_gorod.hangup
    → DoorbellCallController.hangup()
      → SipManager.async_hangup() → BYE → on_bye
      → AudioBridge.stop() → remove_audio_stream(eg_intercom_call)
```

### DND toggle flow

```
HA service call switch.turn_on / turn_off
  → DNDSwitch.async_turn_on/off()
    → coordinator.set_dnd(place_id, key, status=True/False)
      → api.update_dnd_settings(place_id, [{type, status, ...}])
        → http.post('/api/mh-customer/.../settings/do_not_disturb', body)
    → await coordinator.async_request_refresh()  ← подтянуть фактическое состояние
```

## Error flow

| Слой | Стратегия |
|---|---|
| `api.py` | широкий `except Exception`, переброс как `ValueError("invalid_login"/"unauthorized"/...)` |
| `coordinator._async_update_data` | `UpdateFailed(ex) from ex` на fatal (places); per-place failure — `LOGGER.warning` + partial data |
| `config_flow` | словарь `errors={key: translation_key}` или `async_abort(reason=...)` |
| `lock.async_unlock` | `except ClientError` → state = JAMMED + reset через `async_call_later` |
| Внешние тайм-ауты | ✅ REST 30с / binary 60с, connect 10с (`http.py`, A-21/S-09); retry/backoff остаётся follow-up |
| 429 rate limit | ловится в `request_sms_code` → `limit_exceeded`; в остальных местах не специально |
| 401 unauthorized | `query_profile` → `ValueError("unauthorized")` → HA триггерит reauth flow через config_entry. Bearer на pre-auth endpoints больше не отправляется (см. `http.py`), поэтому reauth login проходит без коллизий. Auto-refresh access_token — отложен (см. A-22, [ADR-0006](../decisions/0006-mirror-app-behavior.md)) |

## Entity model

| Entity | Базовый класс | unique_id | device_info |
|---|---|---|---|
| `ElektronnyGorodCamera` | `CoordinatorEntity[..]`, `Camera` | `f"{DOMAIN}_camera_{camera_id}"` | ✅ intercom → shared `entrance_{place}_{ac}_{eid|main}` (с lock того же entrance); place/public → standalone `camera_{id}` |
| `ElektronnyGorodLock` | `CoordinatorEntity[..]`, `LockEntity` | `f"{DOMAIN}_lock_{place}_{ac}_{eid|main}"` (см. `entity_migration.lock_unique_id`) | ✅ shared `entrance_{place}_{ac}_{eid|main}` |
| `ElektronnyGorodBalanceSensor` | `CoordinatorEntity[..]`, `SensorEntity` | `f"{DOMAIN}_{place_id}_balance"` | ✅ `place_{place_id}` |
| `ElektronnyGorodDNDSwitch` | `CoordinatorEntity[..]`, `SwitchEntity` | `f"{DOMAIN}_dnd_{place_id}_{key}"` (key ∈ root / intercom_calls / management_company_calls) | ✅ `place_{place_id}` |
| `ElektronnyGorodCallCamera` | `Camera` (НЕ CoordinatorEntity — нет coordinator-данных; вызов отслеживает DoorbellCallController) | `f"{DOMAIN}_{entry_id}_intercom_call"` | ✅ `{entry_id}_intercom_call` (отдельное устройство «Вызов домофона») |

Legacy формат (`f"{id}_{name}"` для camera, `f"{place}_{ac}_{eid}_{name}"` для lock) мигрируется в `async_setup_entry` через `entity_migration.async_migrate_entity_unique_ids` (A-12).

Все entity:
- наследуют `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]` (slice 3b);
- читают live state из `self.coordinator.data` в property-методах;
- реализуют `_handle_coordinator_update` → `async_write_ha_state`;
- имеют `_attr_has_entity_name = True` + `_attr_translation_key` (или `name=None` для camera как device-level entity).

## Цикличность

Пакет линеен:
```
const ← user_agent ← helpers (только utils)
const ← _logging ← http
const + http + user_agent ← api
const + api + helpers + user_agent ← coordinator
const + (api в config_flow) ← config_flow
const ← entity_migration
const + coordinator + entity_migration ← camera/lock/sensor/switch
const + go2rtc ← config_flow, camera
```

Циклов нет.

## Большие файлы / god objects

- [`config_flow.py`](../../custom_components/elektronny_gorod/config_flow.py) — на грани, но допустимо (все steps в одном flow). Reauth/reconfigure native steps пока не выделены (A-25, A-26).
- [`coordinator.py`](../../custom_components/elektronny_gorod/coordinator.py) — после slice 3a/3b чище: `_async_update_data` + per-place collectors + on-demand actions; legacy shim-методы удалены.
- [`api.py`](../../custom_components/elektronny_gorod/api.py) — 11+ endpoints, продолжает расти (DND, screens). На грани readable; разделение по subscriber/intercom/payments/notifications — кандидат на slice (A-19 + общая модульность).

## Слабые места архитектуры

1. **Lock как entity-модель** — домофон не «закрывается». Synthetic state-cycle (UNLOCKED → LOCKED) — cosmetic UX. `button` платформа была бы корректнее. Open: [ADR-0005](../decisions/0005-lock-vs-button.md), статус proposed (breaking change → ждёт планирования).
2. **`available_sections`** игнорируются (`api.query_sections` исторически вызывался без потребления результата; в текущем `coordinator` вызов удалён, но endpoint в `api.py` остался — кандидат на cleanup при следующем touch coordinator).
3. **Сильная связанность `coordinator` ↔ `api` ↔ `http`** — coordinator unit-тестируется только с mock `aioresponses` (см. `tests/`); inject-абстракции пока нет.
4. **UA shared state в `user_agent.place_id`** — кросс-слойная связанность через `self._api.http.user_agent.place_id = place_id`. Из-за этого refresh идёт сериально по places (см. async-паттерны). Лучше прокидывать `place_id` через параметры HTTP-вызовов; рефакторинг open.
5. **Нет retry/backoff для идемпотентных GET** (остаток A-21). Явный
   `ClientTimeout` уже есть; POST/login/open_lock намеренно не ретраятся автоматически.
6. **FCM опирается на приватные API Google** (A-80) — realtime-вызов работает
   под graceful degradation, но долгосрочная совместимость не гарантирована.

Добавлено с момента предыдущего ревью (2026-06-24):
- ✅ **Uplink-микрофон — two-way audio завершён** (A-85, ADR-0013) — `uplink_ws.py` (WS-команда `intercom_uplink` + Lovelace-карта `www/eg-intercom-mic-card.js`), `sip/uplink.py` `UplinkSink`, дрейф-компенсированный RTP-uplink (`sip/rtp.py`). Механизм #1 (HA WebSocket binary-audio) — без go2rtc/TURN/новых зависимостей. Live-прод 2026-06-24 (микрофон дошёл до домофона). #2/#3/#4 эмпирически отвергнуты.
- ✅ **SIP two-way audio фундамент** (A-81, ADR-0012) — `sip/` пакет (14 модулей), `DoorbellCallController`, `AudioBridge`, `ElektronnyGorodCallCamera`. Приём вызова live + показ экрана вызова (видео + звук гостя) через HA-native WebRTC + downlink.
- ✅ **FCM-событие вызова** (A-54/A-58, ADR-0011) — `fcm.py`, `event`-сущность
  DOORBELL и push-регистрация находятся в master.
- ✅ **Надёжность вызова PR #69** — один video producer на звонок с concurrent
  first-open dedup/teardown (A-88), смена звонящего во время held (A-89),
  игнор FCM `ended` в живом SIP-разговоре (A-90).
- ✅ **Pre-answer профиль подтверждён полным Android PCAP** (A-91): FCM ring →
  REGISTER (`Call-Id`, `Accept: application/sdp`, stock Contact) → INVITE →
  `100 Trying`; `200 OK` только по явному ответу.

Решённые с момента предыдущего ревью архитектуры:
- ✅ Coordinator имеет `update_interval` + dict-snapshot (A-08, slice 3a).
- ✅ Entity наследуют `CoordinatorEntity` (A-09, slice 3b).
- ✅ Дубликаты `get_*_info` / `update_*_state` удалены (slice 3b).
- ✅ Per-request `ClientSession()` → shared HA session ([ADR-0008](../decisions/0008-shared-client-session.md), A-05).
- ✅ Token-redaction ([ADR-0004](../decisions/0004-token-redaction.md), A-01..A-04).
- ✅ Bearer не отправляется на `/auth/*` paths — reauth login flow проходит корректно.
- ✅ Synthetic lock-cycle через `async_call_later` (А-15 частично; полный fix lock→button в [ADR-0005](../decisions/0005-lock-vs-button.md)).
- 🟡 Тестируемость — частично (90+ тестов на config_flow / coordinator / api / migrations / visibility); coverage growing.
- ✅ **Reload-каскад при cold start** (A-64, PR #43) — migration flag перенесён в `entry.data` (не триггерит `async_update_options` listener), explicit reload только при `migration_changed`. `_sync_visibility` отслеживает user_shown override через `entity.options[DOMAIN]`.
- 🟡 **A-63 — Won't fix** (PR #46 final). Skip `stream_source()` для hidden cameras несовместим с HA Stream lifecycle (worker pin-ится к URL, не пересоздаёт session). Лишние HTTP к operator для hidden cameras приняты как acceptable. Skip оставлен только в `async_camera_image` (snapshot on-demand).
- ✅ **go2rtc producer auto-refresh** (A-66, PR #46) — `_ensure_go2rtc_stream` после каждого PUT вызывает `Stream.update_source(rtsp_url)` если HA Stream worker уже running → forces restart с обновлённым ffmpeg producer, избегает 10-30s retry-backoff при истечении operator session token.

## Архитектурные решения (ADR)

| # | Решение | Статус |
|---|---|---|
| [ADR-0001](../decisions/0001-aidd-adoption.md) | Принятие AIDD | **accepted** |
| [ADR-0002](../decisions/0002-coordinator-pattern.md) | Переход на CoordinatorEntity + update_interval | **accepted** (slice 3a/3b реализованы) |
| [ADR-0003](../decisions/0003-iot-class-strategy.md) | Стратегия `iot_class` и polling | **accepted** |
| [ADR-0004](../decisions/0004-token-redaction.md) | Token redaction в логах | **accepted** |
| [ADR-0005](../decisions/0005-lock-vs-button.md) | Lock vs Button для домофона | proposed |
| [ADR-0006](../decisions/0006-mirror-app-behavior.md) | Mirror application behavior | **accepted** |
| [ADR-0007](../decisions/0007-stateful-emulator-baseline.md) | Stateful emulator baseline для HAR-сбора | **accepted** |
| [ADR-0008](../decisions/0008-shared-client-session.md) | Shared `ClientSession` через `async_get_clientsession(hass)` | **accepted** |
| [ADR-0009](../decisions/0009-camera-stream-auto-recovery.md) | Camera stream auto-recovery (operator session TTL) | **accepted** |
| [ADR-0010](../decisions/0010-aidd-state-reconciliation.md) | AIDD state-management + reconciliation findings↔git | **accepted** |
| [ADR-0011](../decisions/0011-doorbell-fcm-channel.md) | Realtime-канал события вызова: приём FCM in-HA | **accepted** |
| [ADR-0012](../decisions/0012-register-on-ring.md) | Register-on-ring (held-short-window) для приёма вызова | **accepted** |
| [ADR-0013](../decisions/0013-uplink-mic-transport.md) | Транспорт uplink-микрофона — HA WebSocket binary-audio (#1) | **accepted** |

## Next reading

- For source of truth: `source-of-truth.md`
- For HA-checklist: `ha-compatibility.md`
- For findings & priorities: `project-audit.md`
- For security details: `security.md`
- For testing: `testing/strategy.md`
