Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-22

Source files:
- `custom_components/elektronny_gorod/**`
- `tests/**`
- `.github/workflows/**`

Related docs:
- `project-map.md`
- `source-of-truth.md`
- `architecture/overview.md`
- `ha-compatibility.md`
- `quality-scale.md`
- `security.md`
- `testing/strategy.md`
- `roadmap.md`

Used by agents:
- Все агенты при работе с конкретными находками

Quality gates:
- AUDIT_DONE

---

# Project Audit — все находки с приоритетами

Все известные на 2026-05-22 проблемы. Каждая запись имеет evidence, рекомендуемый fix и first step.

## Приоритеты

- **P0** — критично (utечка секретов, тихие баги, блокеры релиза).
- **P1** — важно (HA best practices, code quality, надёжность).
- **P2** — желательно (UX, читаемость, лёгкие фиксы).
- **P3** — низкий (опечатки, мёртвый код, mikkogeometry).

## P0 — критичные

### A-01. Утечка access_token в логи

- **Status:** ✅ **RESOLVED** в hotfix-ветке `hotfix/p0-security`.
- **Area:** Security
- **Evidence:** `config_flow.py:77` — заменено на `LOGGER.debug("Access token captured (length=%d)", len(self.access_token))`.
- **Original Impact:** debug-логи содержали bearer-токен → полный доступ к чужому аккаунту.
- **Owner agent:** Security & Privacy.
- **Quality gate:** SECURITY_OK.
- **Details:** см. [`security.md#S-01`](security.md).

### A-02. Утечка headers с Bearer и request body в логи

- **Status:** ✅ **RESOLVED**. `http.py:_log_request` теперь:
  - использует `redact(headers)` из `_logging.py` (любые sensitive ключи → `***`);
  - для auth-paths (`/auth/*`) — body не упоминается даже как факт наличия;
  - для остальных — только размер body, не содержимое.
- **Area:** Security
- **Original Impact:** info-логи содержали Authorization headers и тело auth-запросов (с паролем/SMS).
- **Owner agent:** Security & Privacy.
- **Quality gate:** SECURITY_OK.

### A-03. Утечка response body на DEBUG

- **Status:** ✅ **RESOLVED**. `http.py:_log_response` теперь не читает body вообще (для streaming-safety); для auth-paths логируется только status; для остальных — status + content-length.
- **Area:** Security
- **Original Impact:** debug-логи содержали полный ответ на login/refresh — там accessToken/refreshToken.

### A-04. Утечка `entry.data` в логи

- **Status:** ✅ **RESOLVED**. `config_flow.py:283, 291` теперь логируют `entry.entry_id` вместо целого `entry.data`.
- **Area:** Security
- **Original Impact:** `entry.data` содержал токены.

### A-05. `ClientSession` per-request

- **Status:** ✅ **RESOLVED** в ветке `feat/shared-client-session` (ADR-0008). `HTTP.__init__(hass, ...)` + `async_get_clientsession(hass)` в `__request`. `ElektronnyGorodAPI.__init__` принимает `hass`. `config_flow` lazy-init API через `@property`.
- **Area:** Performance / HA-compat
- **Original Impact:** новый TLS-handshake на каждый запрос; не использовал общий pool HA; утечка сокетов.
- **Owner agent:** Architecture.

### A-06. Bug в `update_camera_state`: поиск по `"ID"` вместо `"id"`

- **Status:** ✅ **RESOLVED**. `coordinator.py:182` — заменено `c.get("ID")` → `c.get("id")`.
- **Area:** Correctness
- **Original Impact:** `update_camera_state` всегда падал с `UpdateFailed("Camera ... not found")`.

### A-07. Тесты — нерабочий stub из шаблона HA

- **Status:** ✅ **PARTIALLY RESOLVED**. Stub `tests/test_config_flow.py` удалён. Добавлен реальный `tests/test_logging_redact.py` для нового helper'а. Полноценный test plan для config_flow + coordinator + api → Этап 3 Bronze (slice 3e).
- **Area:** Testing / Correctness

## P1 — важные

### A-08. Coordinator не имеет `update_interval`

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-pattern` (slice 3a). `update_interval=timedelta(minutes=5)`, `_async_update_data` возвращает dict `{places, balances, cameras, locks}`. См. [ADR-0002](../decisions/0002-coordinator-pattern.md).
- **Area:** HA-compat / Architecture
- **Original Impact:** места загружались 1 раз; баланс не обновлялся автоматически.

### A-09. Entity не используют `CoordinatorEntity`

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-entity` (slice 3b). Sensor / Camera / Lock наследуют `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]`. Все `async_update` удалены — обновления приходят через `_handle_coordinator_update`. Backwards-compat shims из coordinator (`get_*_info`, `update_*_state`) тоже удалены (entities читают `coordinator.data` напрямую). Lock state-cycle переписан с `asyncio.sleep` на `async_call_later` — без блокировки event loop.
- **Area:** HA-compat
- **Original Impact:** нарушение паттерна; нет автоматического обновления при тике coordinator.

### A-10. `iot_class: cloud_polling` без реального polling

- **Area:** HA-compat / Manifest
- **Evidence:** [`manifest.json:10`](../../custom_components/elektronny_gorod/manifest.json#L10) vs `coordinator.py`
- **Recommended fix:** либо включить polling (см. A-08) и оставить `cloud_polling`, либо сменить класс.

### A-11. `hacs.json` minimum HA = `2022.8.0`

- **Area:** Manifest / HA-compat
- **Evidence:** [`hacs.json:3`](../../hacs.json#L3); код использует `ConfigFlowResult`, `LockState.LOCKED` (HA ≥ 2024.x).
- **Recommended fix:** поднять до фактической `2024.1.0`.

### A-12. `unique_id` Camera/Lock содержит локализованное `name`

- **Area:** HA-compat / Correctness
- **Evidence:** [`camera.py:122`](../../custom_components/elektronny_gorod/camera.py#L122), [`lock.py:48`](../../custom_components/elektronny_gorod/lock.py#L48)
- **Impact:** при изменении `name` оператором — другой entity в HA registry; ломается история состояний.
- **Recommended fix:** убрать `name` из `unique_id`. Использовать только стабильные идентификаторы.

### A-13. Жёсткое русское имя `_attr_name = "Баланс аккаунта"`

- **Area:** HA-compat / i18n
- **Evidence:** [`sensor.py:43`](../../custom_components/elektronny_gorod/sensor.py#L43)
- **Recommended fix:** `_attr_has_entity_name = True`, `_attr_translation_key = "balance"`; добавить раздел `entity` в `strings.json`.

### A-14. Sensor баланса: нет device_class/state_class/правильного unit

- **Area:** HA-compat
- **Evidence:** [`sensor.py:55-59`](../../custom_components/elektronny_gorod/sensor.py#L55-L59): unit = `"₽"`.
- **Recommended fix:**
  ```python
  _attr_device_class = SensorDeviceClass.MONETARY
  _attr_native_unit_of_measurement = CURRENCY_RUBLE  # из homeassistant.const
  _attr_state_class = SensorStateClass.TOTAL  # или MEASUREMENT
  ```

### A-15. Lock fake-таймер через `asyncio.sleep`

- **Area:** Correctness
- **Evidence:** [`lock.py:112-120`](../../custom_components/elektronny_gorod/lock.py#L112-L120)
- **Impact:** домофон не «закрывается» физически — синтетическое состояние вводит пользователя в заблуждение.
- **Recommended fix:** либо удалить fake-state и оставить только `unlock`, либо переписать на `button` платформу (breaking change → требует ADR).

### A-16. `async_unsubscribe` не вызывается из `async_unload_entry`

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-pattern` (slice 3a). Используется HA-canonical pattern: `entry.async_on_unload(coordinator.async_unsubscribe)` регистрируется в `async_setup_entry`. HA-core вызывает cleanup автоматически, независимо от исхода platform unload (в отличие от ручного вызова под `if unload_ok:`, который теряет cleanup при partial unload).
- **Area:** Reliability / Memory
- **Original Impact:** dispatcher-слушатель оставался подписан после unload.

### A-17. Дубликат логики в coordinator

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-pattern` (slice 3a). Извлечён `_collect_cameras_for_place(place_id)` helper. Прежние `get_cameras_info` и `update_camera_state` больше не дублируют сбор камер — они являются shim-ами над `self.data`.
- **Area:** Maintainability

### A-18. `available_sections` извлекается и игнорируется

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-pattern` (slice 3a). Вызов `query_sections` удалён из coordinator (он действительно был неиспользуемым — endpoint `/rest/v1/places/{p}/screen-sections` возвращает UI-конфиг приложения, не нужный HA-интеграции).
- **Area:** Dead code / Performance

### A-19. Широкий `except Exception` в API + `e.args[0]`

- **Area:** Robustness
- **Evidence:** [`api.py:61-66`](../../custom_components/elektronny_gorod/api.py#L61-L66), [`api.py:88-91`](../../custom_components/elektronny_gorod/api.py#L88-L91) и пр.
- **Impact:** `e.args[0]` может бросить `IndexError` для исключений без args.
- **Recommended fix:** ловить узкие исключения (`ClientResponseError`, `ClientError`, `asyncio.TimeoutError`); использовать `response.status` напрямую через try/finally.

### A-20. `raise ClientError(response)` — некорректное использование

- **Area:** Robustness
- **Evidence:** [`http.py:72`](../../custom_components/elektronny_gorod/http.py#L72)
- **Recommended fix:** `raise ClientResponseError(response.request_info, ...)`.

### A-21. Нет timeout/retry/backoff

- **Area:** Reliability
- **Evidence:** `http.py`, `api.py`
- **Recommended fix:** `ClientTimeout(total=30)` + helper для retry с backoff.

### A-22. Поведение при 401 (auto-refresh — unknown)

- **Area:** UX / Reliability
- **Evidence:** [`api.py:160-162`](../../custom_components/elektronny_gorod/api.py#L160-L162) — при 401 поднимается `ValueError("unauthorized")` без попытки refresh.
- **Note:** оригинальное приложение **в наблюдавшихся HAR-сессиях** не использует `/auth/.../refresh` endpoint. Это **не значит** что endpoint не существует — возможно, мы не поймали сценарий истечения access_token. См. [ADR-0006](../decisions/0006-mirror-app-behavior.md).
- **Текущая рекомендация:** **не реализовывать** auto-refresh «по интуиции». Сначала — собрать HAR со сценарием истечения access_token (запуск приложения после долгого простоя / форсированный logout-on-server). Только после этого — реализовывать в точном соответствии с приложением.
- **Fallback пока HAR нет:** при 401 — graceful UpdateFailed, пользователь проходит reauth через UI. Это сейчас и работает.

### A-23. Отсутствует `diagnostics.py`

- **Area:** HA-compat
- **Evidence:** в `custom_components/elektronny_gorod/` нет файла.
- **Recommended fix:** см. [`SECURITY_AUDIT.md#S-08`](../audit/security.md).

### A-24. Нет workflow для pytest

- **Area:** CI
- **Evidence:** `.github/workflows/` содержит только hassfest, hacs, release.
- **Recommended fix:** см. [`testing/strategy.md`](../testing/strategy.md).

### A-25. Native reauth flow отсутствует

- **Area:** HA-compat / IQS Silver
- **Evidence:** reauth логика «зашита» в [`config_flow.py:get_account`](../../custom_components/elektronny_gorod/config_flow.py#L259), но нет `async_step_reauth_confirm`.
- **Recommended fix:** добавить отдельный reauth-step.

### A-26. Reconfigure flow отсутствует

- **Area:** HA-compat / IQS Gold
- **Recommended fix:** добавить `async_step_reconfigure`.

## P2 — желательно

### A-27. README.md: битая ссылка `[Русский]` на `/README.ru_RU.md`

- **Evidence:** [`README.md:1`](../../README.md#L1)
- **Recommended fix:** удалить или создать файл.

### A-28. README.md: устаревший пример `electronic_city`

- **Evidence:** [`README.md:41-46`](../../README.md#L41-L46)
- **Recommended fix:** заменить на `elektronny_gorod`.

### A-29. `info.md` / `hacs.json` минимальная HA не совпадает с фактом

- См. A-11.

### A-30. `extra_state_attributes` ключи `Title Case`

- **Evidence:** [`lock.py:62-71`](../../custom_components/elektronny_gorod/lock.py#L62-L71), [`sensor.py:75-80`](../../custom_components/elektronny_gorod/sensor.py#L75-L80)
- **Recommended fix:** snake_case (`place_id`, `access_control_id`, ...).

### A-31. `time.py` использует local time

- **Evidence:** [`time.py:8`](../../custom_components/elektronny_gorod/time.py#L8)
- **Recommended fix:** UTC или явный timezone.

### A-32. f-string в LOGGER

- **Evidence:** [`sensor.py:90`](../../custom_components/elektronny_gorod/sensor.py#L90), [`lock.py:38`](../../custom_components/elektronny_gorod/lock.py#L38), [`http.py:13`](../../custom_components/elektronny_gorod/http.py#L13) и другие.
- **Recommended fix:** `%`-форматирование.

### A-33. Magic strings (`"null"`, `"accessControlOpen"`)

- **Recommended fix:** в `const.py`.

### A-34. Manifest без `quality_scale`, `integration_type`

- См. A-01..A-26 — добавить после fixes.

### A-35. CHANGELOG.md отсутствует

- **Recommended fix:** создать (можно сгенерировать из GitHub Releases).

### A-36. CONTRIBUTING.md отсутствует

- **Recommended fix:** создать (минимально — ссылка на `docs/aidd/contributing.md` + dev setup).

### A-37. `parallel_updates` не задан

- **Area:** HA-compat / IQS Silver
- **Recommended fix:** атрибут на entity-классах.

### A-38. Нет обработки unavailable / log-when-unavailable

- **Area:** HA-compat / IQS Silver
- **Recommended fix:** см. правила IQS.

## P3 — низкий

### A-39. `helpers.py` переизобретает stdlib

- `find` ≈ `next((x for x in items if cond(x)), None)`.
- `contains` ≈ `any(cond(x) for x in items)`.

### A-40. `ANDROID_DEVICES_CSV` закомментирован

- **Evidence:** [`const.py:39`](../../custom_components/elektronny_gorod/const.py#L39)
- **Recommended fix:** удалить или включить.

### A-41. DEFAULT_SNAPSHOT_WIDTH = 300

- **Evidence:** [`const.py:31`](../../custom_components/elektronny_gorod/const.py#L31)
- **Impact:** низкое разрешение по дефолту.
- **Recommended fix:** обсудить с owner.

## Изменения после первого аудита

### A-42. Camera availability частично закрыт (улучшение)

- **Status:** PARTIALLY RESOLVED в PR #27.
- **Evidence:** [`camera.py:197-225`](../../custom_components/elektronny_gorod/camera.py#L197-L225) — `_attr_available`/`_attr_is_on` устанавливаются по факту наличия stream_url.
- **Что осталось:** logic находится в `async_update` и `stream_source`, а не идёт через coordinator — связано с A-09 (CoordinatorEntity). Полный fix требует перехода на coordinator pattern.

### A-43. `import base64` внутри метода

- **Status:** ✅ **RESOLVED**. `import base64` поднят на top of file `camera.py`.
- **Severity:** P3
- **Note:** `aiohttp.BasicAuth` вместо ручного кодирования — TBD, оставим в Итерации 3.

### A-44. `async_update` камеры делает доп. запрос к API

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-entity` (slice 3b). `async_update` удалён из `camera.py` вместе с переходом на `CoordinatorEntity`. Stream URL получается лениво в `stream_source()` (по запросу от HA), camera availability определяется по наличию в `coordinator.data["cameras"]`.
- **Severity:** P1
- **Original Impact:** двойная нагрузка на оператора при каждом update.

### A-45. go2rtc credentials в `entry.data` plaintext

- **Severity:** P1 (security)
- **Evidence:** [`config_flow.py:362`](../../custom_components/elektronny_gorod/config_flow.py#L362), [`config_flow.py:419-420`](../../custom_components/elektronny_gorod/config_flow.py#L419-L420); подробно — в [`security.md#S-16`](security.md).
- **Recommended fix:** добавить `go2rtc_username`/`go2rtc_password` в `TO_REDACT` для diagnostics.py (см. S-08).

### A-46. Новый workflow `prerelease.yaml`

- **Status:** ИНФОРМАЦИЯ (не проблема)
- **Evidence:** [`.github/workflows/prerelease.yaml`](../../.github/workflows/prerelease.yaml)
- **Note:** workflow выкатывает pre-release zip для каждого PR. Добавлен в карту проекта.

## Findings из первого HAR-анализа (2026-05-23)

> Источник — HAR-снимки в `research/api/*.har` (gitignored, конкретные имена не фиксируем). Подробности по endpoints — в [`architecture/api-reference.md`](../architecture/api-reference.md). Принцип ADR-0006: «mirror app behavior» соблюдён — все findings основаны на реальных запросах приложения.

### A-47. WebSocket / STOMP real-time канал не реализован

- **Area:** Feature gap (potential push)
- **Severity:** P1 (research-фаза), потенциально P0-feature после spec
- **Evidence:** `wss://myhome.proptech.ru:443/events` + `Sec-WebSocket-Protocol: v12.stomp, v11.stomp, v10.stomp` зафиксированы в HAR. Также `GET /rest/v1/stomp/available-features` как probe.
- **Impact:** возможно, через WebSocket приходят события домофона/камеры в real-time — это ключ к HA-автоматизациям «звонок в дверь → действие».
- **Каверзы:** в HAR содержимое STOMP-фреймов **не зафиксировано**. WebSocket может нести **не все** события — часть может идти через SIP (см. A-49) или FCM. До получения HAR с активным сценарием (реальный звонок в домофон с записью WS-фреймов) — **не строить spec**.
- **Recommended first step:** записать HAR со сценарием звонка через альтернативный capture (mitmproxy с WebSocket-decode опциями, либо `mitmdump --mode reverse:` для расшифровки). Когда фреймы будут на руках — отдельный feature folder с PRD.
- **НЕ делать:** не «угадывать» STOMP topics и схему сообщений (нарушение ADR-0006).

### A-48. Snapshot домофона (`accesscontrols/{ac}/snapshots`) не реализован

- **Severity:** P2
- **Evidence:** `GET /rest/v1/places/{p}/accesscontrols/{ac}/snapshots` зафиксирован в HAR. Возвращает JPEG bytes.
- **Impact:** наша интеграция показывает snapshot **камер**, но не **домофона** — а домофон тоже имеет камеру у двери.
- **Recommended fix:** добавить в `api.py` метод `query_access_control_snapshot(place_id, ac_id, w, h)`, аналогичный `query_camera_snapshot`. Создать camera entity для каждой `accesscontrols` или дополнительный snapshot endpoint в существующих camera entities.

### A-49. SIP credentials endpoint не используется

- **Severity:** P1 (потенциал для звонков)
- **Evidence:** `POST /rest/v1/places/{p}/accesscontrols/{ac}/sipdevices` возвращает `{id, realm, login, password}` — SIP credentials для регистрации в SIP-сервере оператора.
- **Impact:** приложение использует SIP для приёма входящих звонков от домофонов. Это вероятный механизм real-time доставки «кто-то нажал кнопку у подъезда».
- **Caverны:** SIP — это RTP/UDP вне HTTP. Charles HAR этого не покажет. Нужно либо отдельный capture (Wireshark + ключ TLS), либо реверс APK для SIP-клиента приложения.
- **Recommended first step:** spec-фаза с research через документацию SIP-клиентов Android (PjSIP, Linphone) и попытка зарегистрировать SIP-клиент в HA с credentials из `sipdevices` (например, через PJSIP-плагин HA). Затем — реальный звонок и наблюдение.
- **Связано с A-47** — взаимоисключающие или дополняющие каналы?

### A-50. Camera events endpoints не реализованы

- **Severity:** P2
- **Evidence:** 
  - `GET /api/mh-camera-personal/mobile/v1/cameras/{id}/events` — `{externalEvents: [{ID, Time, Duration, isAvailable}], recordingDisabledEvents: []}`
  - `GET /rest/v2/forpost/cameras/{id}/events` — альтернативный v2 endpoint
- **Impact:** история motion-событий / записей с камер. Можно поднять как HA `event` entity или сенсор «последняя запись».
- **Recommended fix:** новый platform `sensor.last_event` или `event` entity для каждой камеры. Polling с разумным интервалом.

### A-51. Bootstrap config endpoint (`device-installations`) не используется

- **Severity:** P2 (зависит от стабильности hardcoded URLs)
- **Evidence:** `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations` возвращает `{AUTH_PROVIDER, MOBILE_URL.domain.{backend, genesys, stomp, expiredAt}, policy}`.
- **Impact:** приложение **динамически** получает URLs (включая STOMP). У нас hardcoded `BASE_API_URL = "myhome.proptech.ru"` — если оператор переедет, мы сломаемся.
- **Recommended fix:** вызывать device-installations при первом setup + при истечении `expiredAt`, кэшировать в `entry.data`. Использовать `MOBILE_URL.domain.backend` вместо hardcoded.

### A-52. Header `traceparent` не отправляется

- **Severity:** P3
- **Evidence:** в HAR каждый запрос приложения содержит W3C trace context: `traceparent: 00-<32hex>-<16hex>-01`. У нас этого нет.
- **Impact:** теоретически мог бы помочь оператору при поддержке — но в нашем случае это просто **отклонение от паттерна приложения**.
- **Recommended fix:** генерировать `traceparent` per-request в `http.py` (uuid4 → 32 hex для trace, 16 hex для span). Не критично, но облегчает «зеркалирование».

### A-53. `GET /public/v1/operators` не используется

- **Severity:** P3
- **Evidence:** приложение запрашивает список операторов при старте.
- **Impact:** наша интеграция хардкодит один оператор. Если пользователь имеет аккаунты у разных операторов — не поддерживаем.
- **Recommended fix:** не приоритет; в текущей модели один config entry = один оператор.

### A-54. FCM-канал и `subscriberNotifications` — за пределами проекта

- **Severity:** P3 (документирование, не реализация)
- **Evidence:** `POST /rest/v1/subscriberNotifications` отправляет `pushToken` (FCM) и метаданные устройства.
- **Impact:** требует APK reverse engineering для FCM project_id, sender_id, server_key. Юридически серая зона. **Не делать** в рамках HA-интеграции, если есть альтернативы через WS/SIP.
- **Status:** оставляем как known endpoint в `api-reference.md`. Реализация не планируется.

### A-55. Unread response body в `request_sms_code`

- **Severity:** P2 (выявлен code-reviewer-ом во время review ветки `feat/shared-client-session`).
- **Evidence:** [`api.py:request_sms_code`](../../custom_components/elektronny_gorod/api.py) (около строк 93-117) — после `await self.http.post(...)` метод просто `return` без чтения body. С прежним per-request `ClientSession` connection закрывался автоматически при exit `async with`. С shared session (после ADR-0008) — connection возвращается в pool только после consume body или GC.
- **Impact:** под нагрузкой может удерживать connection в "in-use" состоянии дольше необходимого. Не блокер, но slightly менее эффективно.
- **Recommended fix:** добавить `await response.read()` перед `return` либо использовать pattern `async with response:` для гарантированного освобождения connection. Сгруппировать с A-19/A-20 в одном PR.
- **Target:** Итерация 3 Bronze (slice 3e, вместе с tighter exception handling).

## Maintenance rules (повтор)

См. [`PROJECT_MAP.md#maintenance-rules`](../project/project-map.md#maintenance-rules).

## Связь с roadmap

| Audit ID | Итерация в [`roadmap.md`](../roadmap.md) |
|---|---|
| A-01..A-05, A-43, A-45 | Итерация 1 (hotfix-релиз) |
| A-06, A-07 | Итерация 1 |
| A-08..A-14, A-16..A-21, A-23, A-24, A-44, A-55 | Итерация 2 |
| A-15, A-22, A-25, A-26, A-37, A-38, A-48, A-51, A-52 | Итерация 3 |
| A-47, A-49, A-50 | Итерация 4 (real-time + push) — после доп. HAR-research |
| A-27..A-36, A-39..A-41, A-53, A-54 | по мере touch / документирование |
| A-42, A-46 | информация (не задача) |

## Next reading

- For security details: `security.md`
- For testing: `testing/strategy.md`
- For HA-compat: `ha-compatibility.md`
- For implementation order: `roadmap.md`
- For gate criteria: `quality-gates.md`
