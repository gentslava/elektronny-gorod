Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-27 (A-67/A-68 added)

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

Все известные проблемы. Каждая запись имеет evidence, рекомендуемый fix и first step. Дата актуальности — `Last reviewed:` во фронт-блоке.

## Приоритеты

- **P0** — критично (utечка секретов, тихие баги, блокеры релиза).
- **P1** — важно (HA best practices, code quality, надёжность).
- **P2** — желательно (UX, читаемость, лёгкие фиксы).
- **P3** — низкий (опечатки, мёртвый код, mikkogeometry).

## Status vocabulary (reconciliation — ADR-0010)

Этот файл — **единый источник правды** о том, что сделано/открыто (ADR-0010).
Статус сверяется с git master, не пишется авансом:

- **✅ RESOLVED** — фикс **в master** (обязателен commit SHA или merged PR).
- **🟢 resolved-in-branch (pending merge ...)** — код готов, но **ещё не в
  master**. Не считать закрытым для релиза. Перевести в RESOLVED после merge.
- **🟡 PARTIALLY RESOLVED** — часть закрыта, остаток описан.
- **🔴 OPEN / STILL OPEN** — не сделано.
- **🟡 WON'T FIX** — осознанно не чиним (с обоснованием).

🔴 Статус-плейсхолдеры без reconciliation запрещены: указывай либо merged-SHA,
либо `pending merge <ref>`. Сверку гоняет `.claude/hooks/check-audit-reconciliation.sh`.

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

- **Status:** ✅ **RESOLVED**. Stub `tests/test_config_flow.py` удалён. Добавлены реальные тесты: `tests/test_logging_redact.py` (redaction helpers), `tests/test_http.py` (HTTP client + Bearer-omission на pre-auth), `tests/test_entity_migration.py` (lock unique_id migration), `tests/test_visibility.py` + `tests/test_visibility_real.py` (visibility sync). `tests/conftest.py` использует `auto_enable_custom_integrations` фикстуру, `pytest.ini` сконфигурирован. Локально 67 tests pass. CI workflow `.github/workflows/python-tests.yaml` — открытый follow-up (см. A-24 / Tests-1).
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

- **Status:** ✅ **RESOLVED** — `hacs.json:homeassistant` поднят до `2024.10.4` (первая stable с `LockState` enum в `homeassistant.components.lock`, который импортирует `lock.py`). Та же версия в CI matrix как min job — см. `.github/workflows/python-tests.yaml`.
- **Area:** Manifest / HA-compat
- **Evidence:** [`hacs.json:3`](../../hacs.json#L3); код использует `ConfigFlowResult`, `LockState` (HA ≥ 2024.10).
- **Original fix:** поднять до фактической `2024.1.0` (заменено на `2024.10.4` после run 26413140290 — `LockState` отсутствовал в HA 2024.7/2024.8/2024.9, появился только в 2024.10).

### A-12. `unique_id` Camera/Lock содержит локализованное `name`

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-entity` (slice 3c). Новый формат — camera `{DOMAIN}_camera_{id}`, lock `{DOMAIN}_lock_{place_id}_{ac_id}_{entrance_id|main}` (канонический — `entity_migration.lock_unique_id`). Existing entries мигрируются автоматически через `entity_registry.async_migrate_entries` в `async_setup_entry`. См. [ADR-0002](../decisions/0002-coordinator-pattern.md) §Entity naming.
- **Area:** HA-compat / Correctness
- **Original Impact:** при изменении `name` оператором — другой entity в HA registry; ломалась история состояний.

### A-13. Жёсткое русское имя `_attr_name = "Баланс аккаунта"`

- **Status:** ✅ **RESOLVED** в ветке `feat/coordinator-entity` (slice 3c). Sensor — `_attr_has_entity_name=True` + `_attr_translation_key="balance"` (раздел `entity.sensor.balance.name` в `strings.json` + `translations/{ru,en}.json`). Camera/Lock — `_attr_name=None`, имя из `device_info.name` (приходит из API оператора).
- **Area:** HA-compat / i18n

### A-14. Sensor баланса: нет device_class/state_class/правильного unit

- **Status:** ✅ **RESOLVED** в ветке `feat/bronze-entity-polish` (slice 3c). `_attr_device_class = SensorDeviceClass.MONETARY`, `_attr_state_class = SensorStateClass.TOTAL`, `_attr_native_unit_of_measurement = "RUB"` (ISO 4217; константа `CURRENCY_RUBLE` удалена из `homeassistant.const` в свежих HA). Long-term statistics в HA работают корректно.
- **Area:** HA-compat
- **Original Evidence:** [`sensor.py:55-59`](../../custom_components/elektronny_gorod/sensor.py#L55-L59): unit = `"₽"`.
- **Original Fix (для reference):**
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

- **Status:** ✅ **RESOLVED**. Извлечён `_collect_cameras_for_place(place_id)` helper в `coordinator.py` (плюс симметричный `_collect_locks_for_place`). Прежние `get_cameras_info` и `update_camera_state` shim-ы удалены — entities читают `coordinator.data` напрямую.
- **Area:** Maintainability
- **Follow-up:** см. A-61 — `_collect_locks_for_place` и `_collect_cameras_for_place` повторно тянут `query_screens_settings` + `query_access_controls` для одного place. Оставшийся duplicate уже на следующем уровне (per-place fan-out, не per-call).

### A-18. `available_sections` извлекается и игнорируется

- **Status:** ✅ **RESOLVED**. Вызов `query_sections` удалён из coordinator (endpoint `/rest/v1/places/{p}/screen-sections` возвращает UI-конфиг приложения, не нужный HA-интеграции). Подтверждение — в [`coordinator.py:_async_update_data`](../../custom_components/elektronny_gorod/coordinator.py) больше нет упоминаний `available_sections` / `query_sections`.
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

- **Status:** 🟡 **PARTIALLY RESOLVED**. Подзадача «pre-auth endpoints НЕ должны получать stale Bearer» закрыта — [`http.py`](../../custom_components/elektronny_gorod/http.py) (комментарий «Bearer НЕ шлём на pre-auth endpoints (/auth/*) — иначе backend видит expired Bearer и отдаёт 401 даже на login, блокируя reauth flow»). Покрыто `tests/test_http.py`. Это разблокировало возможность native reauth flow (см. A-25).
- **Area:** UX / Reliability
- **Что осталось:** собственно `/auth/.../refresh` endpoint и его триггер по 401 в hot path — **по-прежнему не реализован**. Native `async_step_reauth_confirm` не написан (см. A-25). Пользователь при истечении access_token увидит сначала UpdateFailed, затем должен переинициализировать config_entry.
- **Note:** оригинальное приложение **в наблюдавшихся HAR-сессиях** не использует `/auth/.../refresh` endpoint. Это **не значит** что endpoint не существует — возможно, мы не поймали сценарий истечения access_token. См. [ADR-0006](../decisions/0006-mirror-app-behavior.md).
- **Текущая рекомендация:** **не реализовывать** auto-refresh «по интуиции». Сначала — собрать HAR со сценарием истечения access_token (запуск приложения после долгого простоя / форсированный logout-on-server). Только после этого — реализовывать в точном соответствии с приложением.
- **Fallback пока HAR нет:** при 401 — graceful UpdateFailed, пользователь проходит reauth через UI. Это сейчас и работает.

### A-23. Отсутствует `diagnostics.py`

- **Status:** ✅ **RESOLVED** — добавлен `diagnostics.py` с
  `async_get_config_entry_diagnostics` + `async_redact_data(TO_REDACT)`.
  `TO_REDACT = SENSITIVE_KEYS ∪ PII-идентификаторы` (синхронизирован с
  `_logging.py`). Coordinator-снимок — только счётчики, без значений.
  6 тестов `tests/test_diagnostics.py`. Закрывает
  [`security.md#S-08`](security.md) и [`#S-16`](security.md).
- **Area:** HA-compat / Security

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

- **Status:** ✅ **RESOLVED** в ветке `feat/bronze-entity-polish` (slice 3c). `manifest.json`: `"quality_scale": "bronze"`, `"integration_type": "hub"` (по HA dev docs: «one config_entry → many devices» — аналог Tuya/SmartThings/Husqvarna cloud integrations).

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

- **Status:** 🟡 **MITIGATED** — creds по-прежнему в `entry.data`/`entry.options`
  plaintext (HA-storage limitation), но больше **не утекают** в diagnostics:
  `go2rtc_username`/`go2rtc_password` в `TO_REDACT` (A-23 / S-16). Полное
  шифрование (`Store`/pin) — отдельный backlog-пункт, не блокер.
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

## Findings из второго HAR-research цикла + PR #35

> Источник — HAR-research циклы (gitignored снимки в `research/api/*.har`)
> + PR #35 «visibility sync + Bronze entity polish». Все находки подкреплены
> либо HAR, либо новым кодом в `coordinator.py` / `__init__.py`.

### A-56. DND switches не реализованы

- **Status:** ✅ **RESOLVED** в PR #38 (commit `2dc07ae`). Новая платформа
  `switch.py` с 3 entity per place: master `dnd_root` (всегда available) +
  2 dependent `dnd_intercom_calls` / `dnd_management_company_calls`
  (`_attr_available = root.status`). Coordinator fetches DND state в
  `_async_update_data`, `async_set_dnd()` wrapper для toggle с UA race-safety.
  Translation keys в `entity.switch.{key}.name` (ru/en). 4 unit-теста
  (`tests/test_dnd.py`). См. CHANGELOG `[3.2.0]` (TBD).

### A-57. Sensor balance — нет дополнительных attrs из `/finance` response

- **Status:** ✅ **RESOLVED** — merged в master (commit `e5d9bbd`, PR #39).
  2 entity per place добавлены к существующему balance device:
  - `binary_sensor.{place}_account_blocked` (BinarySensorDeviceClass.PROBLEM).
  - `sensor.{place}_days_to_block` (DURATION + UnitOfTime.DAYS).
  Coordinator `_fetch_balance` теперь extracts `days_to_block`, `days_to_warning`,
  `company`. 0 новых HTTP calls — поля из существующего `/finance` response.
  `amountSum` / `targetDate` / `payment_link` остались в `sensor.balance`
  extra_state_attributes — достаточно для automation (mobile_app.notify
  OPEN_URL, Lovelace tap_action: url, scripts).

  **Дизайн-урок**: первоначально был добавлен `button.{place}_pay` с
  press → persistent_notification, но удалён. HA `ButtonEntity` это
  server-side trigger, не подходит для browser-launch. Открытие URL —
  client-side concern (Lovelace tap_action / mobile push). `payment_link`
  как attribute даёт пользователю гибкость без navigating «button →
  notification → click».

  5 unit-тестов (TDD strict — RED first, потом GREEN). Translations ru/en.
  См. CHANGELOG.

### A-58. Real-time event delivery (polling vs FCM push — research pending)

- **Severity:** P1 (Silver real-time path для домофонных звонков).
- **Area:** Feature gap / real-time alternative.
- **Evidence:** Два кандидатных канала:
  1. **Polling** `POST /rest/v1/events/search?page={n}&sort=occurredAt,DESC`
     с body `{placeIds: [<PLACE_ID>]}` — см.
     [`api-reference.md` §events](../architecture/api-reference.md).
     Spring Pageable, retention ~6 месяцев, page size = 20. Latency 15-30s.
  2. **FCM mimicry** — приложение получает push через Firebase, конфиг
     внутри APK (`google-services.json`). Технически возможно зарегистрировать
     HA как FCM-receiver того же project. Latency sub-second. См. R-1..R-5
     в roadmap Итерации 4.
- **Status:** **research pending**. До завершения R-1..R-5 (APK Firebase
  extraction + feasibility test + legal review) — не принимать ADR-0009
  и не начинать implementation. Polling — safe fallback если push-mimicry
  не получится.
- **ADR:** **ADR-0009** будет написан **после** research как accepted
  выбор одного из вариантов (push primary / polling primary / hybrid).
  См. roadmap Итерация 4.

### A-59. Video archive retention не учитывается при формировании URL

- **Severity:** P3 (UX improvement).
- **Area:** Correctness.
- **Evidence:** Video retention зависит от типа камеры — 14d для
  intercoms (accessControl source), 7d для PUBLIC_CAMERA. Rolling-window
  («граница ползёт» по wall-clock). См.
  [`api-reference.md` §retention](../architecture/api-reference.md).
- **Impact:** интеграция при попытке получить video URL за пределами
  retention окна получит 500 с `errorCode 11005` («archive out of range»).
  Это ложная error для пользователя — данных физически нет, но HA
  показывает «video стримминг недоступен / ошибка».
- **Recommended fix:** helper `is_within_retention(camera_type, ts) -> bool`
  в `helpers.py` (mapping retention per source type) + проверка перед
  любым video URL request. Если вне retention — возвращать `None` (или
  раннее `UpdateFailed` с понятной причиной), не дёргать API.

### A-60. Visibility migration v2 уже applied

- **Status:** ✅ **RESOLVED** (документируется для будущих изменений).
- **Area:** Migration / Documentation.
- **Evidence:** [`__init__.py:_migrate_legacy_disabled_state`](../../custom_components/elektronny_gorod/__init__.py)
  — one-time миграция, флаг `entry.options.visibility_migration_v2`.
  Сбрасывает legacy `disabled_by` markers (entity + device, level
  INTEGRATION/DEVICE/USER) → `None`. Применяется один раз per entry.
- **Impact / зачем фиксировать:** будущие изменения visibility-логики
  должны помнить, что flag `visibility_migration_v2` уже expended на
  всех existing entries. Если потребуется новая cleanup-стадия —
  использовать новый flag-ключ (`visibility_migration_v3` и т.д.),
  не reuse old.

### A-61. Двойной HTTP в per-place collectors

- **Status:** ✅ **RESOLVED** — merged в master (commit `71eb4dd`).
  Pre-fetch `screens` + `access_controls` в `_async_update_data` per place,
  передача в оба collectors как параметры. `_collect_cameras_for_place`
  signature расширена до 4 параметров. `_collect_locks_for_place` теперь
  pure-sync (нет awaitов). **Экономия: -2 HTTP per place per 5min refresh**
  (-576 calls/day для 1 place, scales linearly). 3 new unit-теста (TDD
  strict — RED first → GREEN после refactor). Behavioral NOTE: при ошибке
  `query_access_controls` теперь и cameras, и locks пусты для того place
  (раньше locks могли survive независимо — теперь per-place операция
  атомарна). См. CHANGELOG.

### A-62. FAVORITES section в `/settings/screens` не парсится

- **Severity:** P3 (correctness, fallback OK).
- **Area:** Feature gap / Correctness.
- **Evidence:** [`coordinator.py:_extract_hidden_ids`](../../custom_components/elektronny_gorod/coordinator.py)
  парсит только `PUBLIC_CAMERAS` и `ACCESS_CONTROLS` секции. Секция
  `FAVORITES` (см.
  [`api-reference.md` §screens](../architecture/api-reference.md))
  игнорируется. FAVORITES может иметь mixed entity-types (camera +
  access_control_entrance) — отдельная семантика «избранное на главном
  экране приложения».
- **Impact:** у наших пользователей FAVORITES.hidden обычно пуст
  (исходя из observed HAR-снимков), поэтому fallback на PUBLIC_CAMERAS +
  ACCESS_CONTROLS даёт корректный результат. Но если пользователь явно
  скрыл что-то через FAVORITES в приложении — мы это не учтём.
- **Recommended fix:** расширить `_extract_hidden_ids` чтобы умело
  парсить FAVORITES с учётом mixed-typed items (item.type → camera /
  entrance), затем union с уже извлечёнными hidden_ids. Не блокер.

## Findings из production-логов (2026-05-26)

> Источник — production log `home-assistant_elektronny_gorod_2026-05-26T03-09-25.409Z.log`
> (gitignored, не фиксируем конкретные ID/имена/account_id). Каждый finding
> снят с фактического runtime-поведения интеграции в HA. Принцип ADR-0006
> соблюдён — фиксируем поведение, не догадки.

### A-63. HA prefetches `stream_source()` для hidden cameras

- **Status:** 🟡 **WON'T FIX** (revert через PR #46 — A-66 final). `stream_source()`
  оставлен **без** skip для hidden, всегда возвращает живой URL. Snapshot
  (`async_camera_image`) skip-ает для hidden (lifecycle-safe, on-demand).
- **Severity:** P2 (perf — был оригинальный finding) → **переоценён** как
  acceptable overhead.
- **Почему revert** — A-63 fix фундаментально несовместим с HA Stream lifecycle:
  - HA Stream worker создаёт session при первом `stream_source()` и pin-ится
    к возвращённому URL. Если возвращаем None, worker **никогда** не пере-
    запрашивает stream_source автоматически.
  - Cold start hidden → `self.stream` is None навсегда. Toggle ON не помогает.
  - Эксперимент с 3 вариантами (PR #44 X / #45 Y / #46 Z) подтвердил:
    - X (`_was_hidden` invalidate в stream_source) — не работает, source не дёргается
    - Y (registry listener + `Stream.stop()`/`update_source()`) — частично, требует reload entity
    - Z (revert skip + `Stream.update_source()` в `_ensure_go2rtc_stream`) — работает
  - HA Stream не designed для «entity внезапно перестаёт отдавать stream».
- **Original Evidence:** в production-логе 2026-05-26 повторяющиеся
  `Fetching camera <id> stream URL` для camera_id с `hidden=True`.
- **Реальный impact overhead:**
  - Без frigate: stream_source вызывается редко (только при открытии card) — overhead negligible.
  - С frigate: +10-20 HTTP/мин к operator. **Это поведение было в 3.1.0** — не регрессия.
  - Operator не имеет rate-limit на эти endpoints.
- **Cache rejected** — рассматривался cache stream URL в coordinator с TTL 30s,
  но opasen: cache может вернуть expired URL во время HA Stream recovery
  retry-loop, усугубляя failure. Cache snapshot — мало benefit для сложности.
- **Related (A-66):** Z подход добавил `Stream.update_source()` после каждого
  PUT в go2rtc — это форсит worker restart с обновлённым ffmpeg producer.
  Решает «invalid data при истечении operator токена» автоматически.

### A-66. go2rtc stale producer URL после long idle + revert A-63

- **Status:** ✅ **RESOLVED** в PR #46 (Z variant after experimentation).
  `camera.py:stream_source` больше не skip-ает для hidden cameras (revert A-63).
  Snapshot skip оставлен. `_ensure_go2rtc_stream` после каждого успешного
  PUT вызывает `Stream.update_source(rtsp_url)` если worker уже running —
  forces restart с обновлённым ffmpeg producer (избегаем 10-30s retry-backoff
  при истечении operator токена).
- **Severity:** P2 (UX — было «не грузится после toggle видимости»).
- **Area:** HA Stream lifecycle / go2rtc integration.
- **Evidence (production diagnostics 2026-05-26):**
  - `eg_5593587` в go2rtc держал producer URL `a833471/dZ9lxcy0GDRaZjdxWP2k`
  - `curl` к этому URL → `connection reset` (token expired)
  - HA Stream worker retry → `Invalid data found when processing input` →
    `Server returned 404 Not Found` (после go2rtc evict config)
- **Эксперимент (3 PR-а, X/Y/Z):**
  - **X (PR #44):** `_was_hidden` flag + invalidate `_last_src` при transition.
    **Не работает** — HA Stream не вызывает stream_source повторно, invalidate
    в stream_source мёртвый код.
  - **Y (PR #45):** Registry event listener (hide=`Stream.stop()`,
    unhide=fetch+PUT+`update_source()`). **Работает только после reload entity** —
    cold start hidden даёт `self.stream is None`, нечего restart-ить.
  - **Z (PR #46, accepted):** revert stream_source skip + `Stream.update_source()`
    в `_ensure_go2rtc_stream`. HA Stream lifecycle работает as designed,
    минимум кода (+24/-4 LOC), `update_source()` обеспечивает что после
    каждого operator URL change worker сразу restart-ает с свежим producer.
- **Trade-off:** возвращены лишние HTTP к operator для hidden cameras (см.
  A-63 → Won't fix). Это меньшее зло чем broken video lifecycle.
- **Dev lessons:**
  - HA Stream не designed для «entity внезапно перестаёт отдавать stream»
    — никаких «оптимизаций» через возврат None из stream_source.
  - `Stream.update_source()` — официальный HA API для force restart worker
    с новым source. Использовать когда обновляется upstream producer config.

### A-64. `_sync_visibility` / migration → reload cascade + user override

- **Status:** ✅ **RESOLVED** — merged в master (commit `20867c4`).
  Три изменения в `__init__.py`:
  1. **Migration flag в `entry.data`** (НЕ `entry.options`) — listener
     `async_update_options` не срабатывает. Backward-compat: читает оба
     места, переносит из options в data при первом setup после обновления.
  2. **Reload только при `migration_changed`** — sync visibility теперь это
     live registry update (HA core подхватывает изменения `hidden_by` без
     reload entry). `sync_changed` больше не trigger reload.
  3. **`_sync_visibility` track user override** через
     `entity.options[DOMAIN]` (persistent в core.entity_registry, НЕ триггерит
     entry update listener):
     - `we_set_integration: True` — наша отметка после set INTEGRATION;
     - `user_shown: True` — детектится когда `we_set_integration=True`,
       а registry уже `hidden_by=None` (юзер кликнул «Показывать на панели»).
       С этого момента не восстанавливаем INTEGRATION даже если API hidden.
     - Auto-clear `user_shown` когда приложение тоже разрешит показ —
       цикл закрывается, следующий «Скрыть в приложении» снова даст INTEGRATION.

  5 новых тестов (`tests/test_visibility_user_override.py`): migration storage
  + backward-compat + user override persist across reload + auto-clear после
  un-hide в приложении + USER hidden_by regression-guard. 89 tests pass
  (84 → +5). См. CHANGELOG.
- **Original Severity:** P2 (UX — лишние reload на старте + перезапись user
  выбора каждые 5 минут).
- **Original Evidence:** production-лог 2026-05-26: 4× `Integration loading
  entry` за 34 сек после cold start (`10:07:06.579 → 10.114 migration → 10.117
  reload → 18.017 reload → 40.117 reload`).
- **Связано:** этот fix закрывает known follow-up из A-63
  (наш sync перезаписывал user «Показывать на панели» каждые 5 мин).

### A-65. Log noise от временно broken cameras

- **Status:** ✅ **RESOLVED** — merged в master (commit `d4ea4b3`).
  Per-entity counter `_consecutive_empty_count` в `ElektronnyGorodCamera`.
  В `stream_source()` при empty URL: counter incremented, level выбирается
  динамически — `WARNING` если counter==1, `DEBUG` если counter>=2. При
  первом успешном response counter сбрасывается → следующий fail снова
  WARNING. Per-entity = per-camera независимые counters (другая broken
  camera всегда получает WARNING для первого fail).
- **Severity:** P3 (observability).
- **Original Evidence:** production-лог 2026-05-26 — 10 одинаковых WARNING
  за полчаса от ОДНОЙ temporary-broken hardware-камеры. Особенно noise под
  нагрузкой frigate/webrtc preview которые тычут `stream_source` часто.
- **3 unit-теста** (`tests/test_camera_log_throttle.py`):
  1. 1й fail → WARNING, 2й-6й → DEBUG.
  2. Recovery (success) → counter reset → следующий fail снова WARNING.
  3. Per-camera counters независимы.
- **Skipped optional:** `INFO "Camera recovered after K failures"` —
  избыточно для production logs, можно добавить позже если будет потребность.
- **Out of scope:** transport exceptions из `get_camera_stream` (network/timeout)
  не throttle-аются — counter трогается только для empty-URL path. Это
  другой класс ошибок, логируется отдельно через `LOGGER.exception` в
  coordinator/HTTP слое.

## Findings из production-логов (2026-05-27)

> Источник — production log
> `home-assistant_elektronny_gorod_2026-05-27T06-00-36.030Z.log` (gitignored).
> Логи показывают deployed PR #43 (A-64) и PR #46 (A-66 final).

### A-67. Cold-start go2rtc state mismatch

- **Severity:** P2 (UX — 30-60 sec lag после HA restart до восстановления стримов).
- **Area:** HA Stream lifecycle / go2rtc integration.
- **Evidence (2026-05-27 12:57 log):**
  - HA start at 12:57:14.
  - **12:57:25.816** (через 11 сек) — `Error opening stream (Invalid data found ...
    rtsp://127.0.0.1:8554/eg_5595470)`.
  - 12:57:25.981, 12:57:25.998 — то же для eg_5595471, eg_5595472.
  - 12:58:05.469 — для eg_5593578.
  - 12:58:49.988 — `go2rtc.server WRN ... i/o timeout url=rtsp://127.0.0.1:8554/eg_5595472`.
  - Recovery только в 12:58:54 (через ~90 сек после start) когда HA core
    позвал `stream_source` → fresh PUT в go2rtc → producer обновился.
- **Root cause:** go2rtc — отдельный процесс, **переживает** HA restart.
  При HA shutdown remained config со stale URL (operator token expired).
  После HA start, HA Stream worker (preload_stream) немедленно подключается
  к `rtsp://127.0.0.1:8554/eg_<id>`, go2rtc активирует ffmpeg producer
  с устаревшим upstream URL → fail. HA Stream backoff retry (10-30s) →
  через 1-2 минуты `stream_source` вызывается → A-66 force restart →
  работает.
- **Impact:** юзер открывает Lovelace в первые 1-2 минуты после restart →
  видит ошибки/чёрный экран. UX broken на ~60 секунд после cold start.
- **Recommended fix:** proactive go2rtc warmup в `async_added_to_hass`:
  - Для camera с `use_go2rtc=True` и не hidden → schedule async task
    через `async_call_later(2)` (даём HA core bootstrap).
  - Task делает `await self.coordinator.get_camera_stream(self._id)` +
    `await self._ensure_go2rtc_stream(url)` → fresh PUT в go2rtc.
  - Если HA Stream worker уже подключился → A-66 `Stream.update_source()`
    auto-restart его с fresh producer.
- **Trade-off:** +N HTTP к operator при startup (N = visible cameras).
  На 10 cameras = +10 HTTP в начале (один раз), приемлемо.
- **Test plan:**
  - unit-тест: warmup task scheduled при `async_added_to_hass` (use_go2rtc=True).
  - unit-тест: warmup НЕ запускается для hidden cameras / use_go2rtc=False.
  - integration-тест: после warmup `_ensure_go2rtc_stream` вызван (`_last_src` != None).

### A-68. Concurrent stream_source() для одной camera дублирует HTTP + go2rtc restart

- **Status:** ✅ **RESOLVED** — merged в master (commit `b771ba8`, PR #51).
  In-flight future-pattern в `Camera.stream_source()`. Если
  concurrent caller обнаруживает `self._inflight_stream_future is not None` —
  wait existing future вместо запуска параллельного fetch. Существующая
  логика вынесена в helper `_fetch_stream_source_impl()`. Future cleared в
  `finally` блоке → sequential calls после batch делают свежий fetch.
  Per-instance attr = per-camera dedup. 5 unit-тестов
  (`tests/test_camera_stream_dedup.py`): concurrent dedup / sequential fresh
  fetch / exception propagation / per-camera independence / cancellation
  safety net (P1 follow-up из code-review).
- **Severity:** **P2 (defensive concurrency cleanup)** — снижает thrash на
  operator API + go2rtc PUT при concurrent callers. Изначально классифицирован
  P1 UX (предполагалось что fix устранит видимое мигание видео), но
  production-тест 2026-05-27 показал что мигание имеет **отдельный root
  cause** — A-68 dedup его не устраняет.
- **Area:** HA Stream / go2rtc integration / API throttling.
- **Evidence (2026-05-27 12:59:21 log):**
  ```
  12:59:21.304 Fetching camera 5593578 stream URL    ← запрос #1
  12:59:21.317 Fetching camera 5593578 stream URL    ← запрос #2 (через 13 ms!)
  12:59:21.619 Response 5593578 video [200 OK]      ← разные tokens
  12:59:21.668 Response 5593578 video [200 OK]
  ```
  Этот случай — настоящий concurrent dedup. 13 мс ≪
  `STREAM_RESTART_INCREMENT` (5 сек минимум для HA Stream retry) → не
  retry-цепочка, а два независимых caller'а (HA Stream worker + второй
  источник: Frigate / WebRTC probe / Lovelace card preview / HA Camera
  snapshot polling).

  Второй паттерн из лога (13:00:14-15, gap=0.88 сек, 2× `forced HA Stream
  restart`) **ambiguous**: 0.88 сек укладывается в окно retry-after-error,
  значит может быть следствием отдельного flicker-бага (HA Stream worker
  retries после `Invalid data found` → fresh `stream_source()` → fresh PUT
  → fresh restart). На этот паттерн A-68 dedup **не повлияет** (calls
  sequential, не concurrent).
- **Root cause:** `Camera.stream_source()` может быть вызван конкурентно из
  нескольких источников (HA Stream worker + Frigate + Lovelace tap +
  advanced WebRTC requests). Operator возвращает разные URL (fresh tokens
  каждый раз), поэтому `_last_src != src` → каждый concurrent дубль делает:
  - HTTP к operator
  - PUT в go2rtc
  - `Stream.update_source()` → restart worker
- **Impact:** при активном multi-consumer setup (Frigate motion detection +
  Lovelace card open + WebRTC) — defensive thrash без пользы (N HTTP вместо
  1). С dedup'ом — N-1 HTTP сэкономлено per batch. **Не** фикс видимого
  «мигание видео после cold start» — у него другой root cause (см. отдельный
  track investigation, не закрыт).
- **Recommended fix:** in-flight deduplication через future-pattern в
  `stream_source`:
  ```python
  async def stream_source(self) -> str | None:
      if self._is_hidden():
          return None
      # A-68: dedup concurrent calls
      if self._inflight_stream_future is not None:
          return await self._inflight_stream_future
      fut = asyncio.get_running_loop().create_future()
      self._inflight_stream_future = fut
      try:
          result = await self._fetch_stream_uncached()
          fut.set_result(result)
          return result
      except BaseException as exc:
          fut.set_exception(exc)
          raise
      finally:
          self._inflight_stream_future = None
  ```
  Concurrent вызовы wait-ают первый → получают одинаковый URL → 1 HTTP +
  1 PUT + 1 restart. Future-pattern (а не Lock) потому что Lock привёл
  бы к sequential HTTP, future re-uses single result.
- **Test plan:**
  - unit-тест: 2 concurrent `await stream_source()` → 1 mock HTTP call →
    оба получают одинаковый URL.
  - unit-тест: после первого finish — следующий call делает свежий HTTP
    (не stuck cache).
  - unit-тест: если первый бросает exception → второй тоже получает
    exception (без зависания).

### A-71. Operator forpost session TTL (~30 мин) — long-open video stops без refresh

- **Status:** ✅ **RESOLVED** — merged в master (PR #57, merge commit `aedf2a4`).
  Root cause = by-design лимит бэкенда (НЕ баг). **Auto-recovery**, три пути
  ([ADR-0009](../decisions/0009-camera-stream-auto-recovery.md)):
  - **v1 event-driven** — оборачиваем HA Stream update-callback; при
    `stream.available → False` throttled (`STREAM_RECOVERY_COOLDOWN=30s`)
    re-fetch свежего URL + `_ensure_go2rtc_stream`/`update_source`. Покрывает
    камеры с legacy HA Stream worker (**домофоны**).
  - **v2 go2rtc producer-health poll** — `GET /api/streams?src=eg_<id>` каждые
    `GO2RTC_HEALTH_POLL_INTERVAL=30s`; `bytes_recv` заморожен при `consumers>0`
    → stall → тот же recovery. Покрывает **go2rtc/WebRTC-only камеры (лифты)**,
    у которых нет legacy Stream worker.
  - **v3 proactive keep-alive** — каждые `GO2RTC_PROACTIVE_REFRESH_INTERVAL=25 мин`
    PATCH go2rtc с fresh operator URL **до** TTL hit (только для streams с
    активными consumers — не нагружаем сеть впустую).
  - **ROOT CAUSE (v3.2 fix, 2026-05-30):** `_go2rtc_upsert_stream` исторически
    использовал PUT-first. Эмпирически на go2rtc API: **PUT** на existing
    stream = DESTROY+RECREATE producer (consumers=0), **PATCH** = idempotent
    update (producer survives). Переключение порядка → PATCH-first решает
    catastrophic disruption WebRTC peers при каждом refresh.
  - **Прод-верификация v3.2 (2026-05-30 02:58→04:18):** 4 successful proactive
    cycles, peaceful (bytes_recv растут непрерывно, consumers сохраняются).
    Timestamp discontinuity (DTS jump между producers) — только 1 раз на
    cold-start, после стабилизации pipeline transitions проходят smoothly.
  - 20 unit-тестов (`tests/test_camera_auto_recovery.py`).
- **Severity:** **P2 (UX, by-design)**: видео останавливается через ~30 мин
  непрерывного просмотра. **Оригинальное приложение «Мой Дом» ведёт себя
  идентично** (зависает примерно через те же полчаса) — это архитектурный
  лимит бэкенда оператора, исходящего из того, что лайв не смотрят так долго.
  Помогает ручное переоткрытие карточки (= reopen в приложении).
- **Area:** HA Stream lifecycle / go2rtc producer / operator forpost session.
- **Symptom (user-reported 2026-05-27):** «долго открытое видео перестаёт
  воспроизводиться» — frozen / чёрный экран.
- **Evidence (`...2026-05-27T14-58-18.200Z.log`):**
  - Camera Подъезд (5593590): **16×** `Error demuxing stream while finding
    first packet (Operation timed out, rtsp://127.0.0.1:8554/eg_5593590)`
    непрерывно **20:34:30 → 20:54:23** (~20 мин) — **без единого** `Fetching
    camera 5593590 stream URL` в этом окне (refresh не происходит).
  - go2rtc producer: `error=EOF url=ffmpeg:elektronny_gorod_..._camera_<id>`
    (апстрим оператора закончил поток) + `i/o timeout
    url=rtsp://127.0.0.1:8554/eg_<id>` (consumers не получают пакетов).
  - **Чистый TTL** (по последнему раунду обновления, без загрязнения
    многократными reload): PUT **21:25:14** → first error **21:55:19** =
    **30:05** для 5593590/5593592/5595471 (минтились вместе → умерли вместе).
  - HAR (`session_MyHome_25-05.har`): `data.URL` =
    `https://forpost-N.novotelecom.ru:18081/rtsp/a<NNNNNN>/<token>/d=1` —
    **expiry в URL отсутствует**, TTL чисто серверный; сессия `a<NNNNNN>`
    минтится заново на каждый `/video`.
- **Root cause (causal chain):**
  1. `Camera.stream_source()` вызывается HA **один раз** при старте Stream
     worker'а → тянет operator URL (forpost session TTL ~30 мин) → PUT go2rtc.
  2. Worker держит соединение постоянно (preload / continuous consume).
  3. Через ~30 мин forpost закрывает сессию → go2rtc ffmpeg producer ловит
     EOF → авто-restart на **тот же** (уже мёртвый) URL → reconnect storm.
  4. `_ensure_go2rtc_stream` (единственный refresh source) вызывается **только**
     из `stream_source()`; HA повторно его не зовёт → URL не обновляется.
  5. HA Stream worker → «finding first packet timed out» → retry-backoff
     навсегда. Видео встало до ручного переоткрытия (fresh `stream_source()`).
- **Связь:** это и есть root cause, который искали [A-66](project-audit.md)
  и informal A-69/A-70 (PR #44-46, #52-53 — закрыты без устойчивого фикса).
  A-66 `Stream.update_source()` помогает **только** когда `stream_source()`
  повторно вызван; в long-open сценарии он не вызывается. [A-68](project-audit.md)
  dedup ортогонален.
- **TTL не читается клиентом и не нужен точно.** В URL нет expiry-поля; точное
  значение (~30 мин) не влияет на решение — это известный лимит бэкенда,
  воспроизводимый и в оригинальном приложении. Поэтому **active diagnostic
  patch (измерение TTL) не делается** — измерять нечего, мы уже знаем поведение.
- **Решение = design tradeoff (ADR-0009).** Конфликт с принципом
  [mirror-app-behavior]: интеграция воспроизводит приложение, а приложение
  **намеренно** даёт зависнуть. Рассмотренные варианты:
  - **Вариант 0 — pure mirror:** ничего не «чинить». Отклонён (HA-сценарии
    долгого просмотра ломаются сильнее, чем в мобильном приложении).
  - ✅ **Вариант 1 — auto-recovery (мягкая deviation) — ВЫБРАН:** при детекте
    stall (`stream.available → False`) автоматически дёрнуть свежий
    `stream_source()` — это **те же API-вызовы**, что делает приложение при
    reopen, просто автоматически. Не выдумывает новых эндпоинтов. См.
    [ADR-0009](../decisions/0009-camera-stream-auto-recovery.md).
  - **Вариант 2 — proactive keep-alive (полная deviation):** фоновый refresh
    каждые `T < TTL`. Отклонён как primary (паттерн, которого в приложении нет;
    лишние HTTP). Возможное будущее расширение для WebRTC-only.
- **Secondary:** [api.py:query_camera_stream](../../custom_components/elektronny_gorod/api.py#L343)
  `except Exception: return None` глотает бизнес-ошибку `Error != null` при
  HTTP 200 (см. api-reference §video) — маскирует диагностику истечения.

### A-77. HA Stream worker DTS discontinuity при producer restart

- **Status:** 🟡 **KNOWN limitation** (документирована в
  [ADR-0009 §v3+v3.2 Known limitation](../decisions/0009-camera-stream-auto-recovery.md)
  и [A-71](#a-71-operator-forpost-session-ttl-30-мин--long-open-video-stops-без-refresh)).
  Reactive workaround работает (v1 ловит и recovery'ит) — не блокер.
- **Severity:** **P3 (UX cosmetic)** — ~5 секунд gap в видео раз на
  cold-start cycle. Data loss нет, не блокирует UX надолго.
- **Area:** HA Stream / go2rtc producer transition.
- **Evidence (прод-лог 2026-05-30 03:04, после первого natural EOF):**
  ```
  03:04:26.610 ERROR (stream_worker) podezd_2: Timestamp discontinuity
     detected: last dts = 161820000, dts = 308832340
  03:04:27.437 ERROR (stream_worker) kalitka_2: ... last dts = 79306125,
     dts = 3652483608
  03:04:27.505 ERROR (stream_worker) kalitka_1: ... last dts = 79297362,
     dts = 2820243242
  03:04:30.559 ERROR (stream_worker) lift_pas_1: ... last dts = 161398890,
     dts = 1172830309
  ```
  4 камеры разом при **первом** natural EOF (~30 мин после cold-start).
  Subsequent cycles (03:23, 03:48, 04:13) прошли БЕЗ Timestamp discontinuity —
  pipeline стабилизировался.
- **Root cause:** go2rtc producer (ffmpeg к operator) при перезапуске начинает с
  свежих DTS (PTS/DTS обычно с нуля или с offset). HA Stream worker (тоже
  ffmpeg внутри) видит резкий jump DTS и считает это stream corruption —
  exits с `StreamWorkerError`. Это **fundamental HA Stream behavior**, не bug
  нашей интеграции.
- **Impact:** только при **первом** EOF после cold-start; subsequent producer
  restarts smooth (наблюдено в прод). v1 reactive recovery (`stream.available
  → False` callback) ловит worker error → fresh fetch + `update_source()` →
  restart worker → новый DTS baseline. **Gap ~5 сек**, потом OK.
- **Why subsequent transitions smooth (гипотеза):** после первого force restart
  worker pipeline переустанавливается с новой baseline. Дальнейшие
  EOF/restart cycles в пределах того же session-семейства держат DTS в близкой
  области. Точная динамика — не проверена, требует отдельной DIAG-сессии.
- **Mitigation (текущая):** v1 callback ловит и recovery'ит. Acceptable UX
  для большинства пользователей.
- **Recommended fix (если станет приоритетным — не в этом цикле):**
  - **Option A:** `ffmpeg:URL#input=-fflags +igndts+discardcorrupt#video=copy`
    в go2rtc source spec — ffmpeg игнорирует DTS jumps. Может иметь
    side effects на latency calculations / sync video+audio.
  - **Option B:** `ffmpeg:URL#input=-fflags +genpts` — regenerate PTS. Аналогично.
  - **Option C (изящный):** trigger producer restart по таймеру (контролируемо)
    *до* natural EOF, в момент когда уже есть будущий PATCH с новым URL —
    pipeline войдёт в "restarted" режим до того как настоящий EOF придёт.
    Тонкий код.
- **Trade-off отказа от fix:** один моргание ~5 сек раз на cold-start
  (приемлемо). Возможна жалоба от пользователя с критическим setup
  (recording, NVR pipeline) — тогда выбираем Option A.
- **Test plan:** прод-метрика — частота `Timestamp discontinuity` errors на
  стабильно работающей инсталляции (норма: 0-2/день после первого cold-start).
- **Связь:** [A-66](#a-66-go2rtc-stale-producer-url-после-long-idle--revert-a-63)
  (force restart механизм), [A-71](#a-71-operator-forpost-session-ttl-30-мин--long-open-video-stops-без-refresh)
  (auto-recovery архитектура), [ADR-0009](../decisions/0009-camera-stream-auto-recovery.md).

### A-78. Options flow — нельзя очистить go2rtc creds (voluptuous default back-fill)

- **Status:** ✅ **RESOLVED** — merged в master (PR #58, merge commit `0ae029d`).
- **Severity:** **P2 (UX-baked silent corruption — юзер думает «save успешен», а данные не меняются).**
- **Area:** `config_flow.py:OptionsFlowHandler.async_step_init` (schema construction),
  `go2rtc.py:validate_go2rtc` (UX-улучшение для 401).
- **Symptom:** Юзер открывает «Настройки go2rtc», очищает поля username/password,
  нажимает «Сохранить» — форма показывает «Параметры успешно сохранены»,
  но при следующем открытии options creds **снова на месте**.
- **Evidence (production storage снимок 2026-05-30):**
  Юзер репортил bug; SSH'нул на сервер, посмотрел
  `/opt/homeassistant/.storage/core.config_entries`:
  ```
  "options": {
    "go2rtc_username": "admin",
    "go2rtc_password": "XPzqUkuCTr4639go2rtc",
    ...
  }
  ```
  Хотя юзер только что «сохранил» с пустыми полями.
- **Root cause (real, доказан unit-test'ом):** schema использовала
  `vol.Optional(KEY, default=str(old_value)): str` — это HA frontend омит
  пустые Optional поля при submit → voluptuous подставляет **default обратно** →
  user_input получает старое значение → save «успешен» без изменений.
  Документировано HA: «The default value is used if the user leaves the field
  empty» — это и есть наш сценарий. Изначально я диагностировал bug как
  «validate_go2rtc мапил 401 на unreachable» — это была ВТОРИЧНАЯ проблема
  (юзер видел misleading error). Реальный root cause обнаружен только когда
  юзер сказал «save проходит успешно» — это противоречило моей первой гипотезе.
- **Fix:** канонический HA pattern `add_suggested_values_to_schema`:
  ```python
  schema = vol.Schema({
      vol.Optional(CONF_GO2RTC_USERNAME): str,  # ← НЕТ default
      vol.Optional(CONF_GO2RTC_PASSWORD): str,
  })
  return self.async_show_form(
      step_id="init",
      data_schema=self.add_suggested_values_to_schema(
          schema, {CONF_GO2RTC_USERNAME: old, CONF_GO2RTC_PASSWORD: old}
      ),
  )
  ```
  Подсказка показывает текущие creds в UI, но empty submit остаётся empty.
  Плюс улучшен 401 detection в `validate_go2rtc` (отдельный
  `go2rtc_auth_failed` error code).
- **Regression-guard:** 3 unit-теста в `tests/test_options_flow_clear_creds.py`:
  - `test_clear_creds_when_use_go2rtc_off` — clear creds + uncheck = save empty (этот тест **FAIL без fix**).
  - `test_clear_creds_with_use_go2rtc_on_shows_auth_error` — UX для забывших unchecking.
  - `test_change_creds_to_new_values` — happy path смены.
- **Lesson learned:** при diagnose UX-багов **читай реальное persistent state**
  (HA storage, БД), не только UI feedback. Юзер сказал «creds не очищаются» —
  моя первая гипотеза была про validation block (logically valid, но не root cause).
  SSH'нув на сервер за 1 запрос и посмотрев `core.config_entries.json`, увидел
  что save реально проходит — это сразу указало на schema/voluptuous как
  настоящего виновника.


## Maintenance rules (повтор)

См. [`PROJECT_MAP.md#maintenance-rules`](../project/project-map.md#maintenance-rules).

## Связь с roadmap

| Audit ID | Итерация в [`roadmap.md`](../roadmap.md) |
|---|---|
| A-01..A-05, A-43, A-45 | Итерация 1 (hotfix-релиз) |
| A-06, A-07 | Итерация 1-2 (test infra доехала с Bronze polish) |
| A-08..A-14, A-16..A-21, A-23, A-24, A-44, A-55 | Итерация 2 (Bronze IQS — shipped в 3.1.0) |
| A-60 | Итерация 2 (visibility migration v2 — shipped в 3.1.0) |
| A-15, A-22 (остаток), A-25, A-26, A-37, A-38, A-48, A-51, A-52 | Итерация 3 |
| ✅ A-56 + ✅ A-57 + ✅ A-61 (shipped 3.2.0 TBD), A-58, A-59, A-62 | Итерация 3 (Silver feature gaps) |
| 🟡 A-63 (Won't fix — incompatible с HA Stream lifecycle) + ✅ A-64 (PR #43) + ✅ A-65 (PR #49) + ✅ A-66 (PR #46) | Итерация 3 (Silver — runtime polish из реальных логов 2026-05-26) |
| A-67 (P2 cold-start warmup, TBD) + ✅ A-68 (PR #51 — dedup concurrent stream_source) | Итерация 3 (новые findings из лога 2026-05-27, отдельные PR) |
| ✅ A-71 (long-open video freeze ~30 мин — auto-recovery, ADR-0009) | Итерация 3 (design tradeoff: mirror vs HA-UX) |
| A-58 (research pending), A-47 (P3/skip), A-49 (P3 future), A-50 | Итерация 4 (real-time event detection — research-фаза, ADR-0009 после R-1..R-5) |
| A-27..A-36, A-39..A-41, A-53, A-54 | по мере touch / документирование |
| A-42, A-46 | информация (не задача) |

## Next reading

- For security details: `security.md`
- For testing: `testing/strategy.md`
- For HA-compat: `ha-compatibility.md`
- For implementation order: `roadmap.md`
- For gate criteria: `quality-gates.md`
