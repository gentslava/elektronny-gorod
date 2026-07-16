Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-07-16 (A-96 PATCH-only live failure, preload revision,
549-test evidence and repeat production-acceptance status reconciled)

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

- **Status:** ✅ **RESOLVED**. Coordinator выполняет реальный cloud polling с
  `update_interval=timedelta(minutes=5)` и возвращает единый snapshot данных;
  `manifest.json:iot_class=cloud_polling` соответствует поведению.
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

- **Status:** 🟡 **PARTIALLY RESOLVED** — timeout закрыт (merged в master,
  commit `3885bb0`): `http.py` шлёт явный `ClientTimeout` (`_REST_TIMEOUT`
  total=30/connect=10; `_BINARY_TIMEOUT` total=60/connect=10 для snapshot).
  **Остаётся открытым:** retry/backoff (вынесен в follow-up — POST/login/
  open_lock не идемпотентны, ADR-0006 mirror-app). Тесты — `tests/test_http.py`.
- **Area:** Reliability
- **Evidence:** `http.py`, `api.py`
- **Recommended fix (остаток):** helper для retry с backoff только для
  идемпотентных GET (5xx / connection errors).

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

- **Status:** ✅ **RESOLVED**. Языковой переключатель ведёт на существующий
  `/README.md`; английская версия — `/README.en_EN.md`.

### A-28. README.md: устаревший пример `electronic_city`

- **Status:** ✅ **RESOLVED**. Инструкция ручной установки использует каталог
  `custom_components/elektronny_gorod`.

### A-29. `info.md` / `hacs.json` минимальная HA не совпадает с фактом

- **Status:** ✅ **RESOLVED**. `hacs.json:homeassistant=2024.10.4`, README badge
  показывает `2024.10+`; см. A-11.

### A-30. `extra_state_attributes` ключи `Title Case`

- **Evidence:** [`lock.py:62-71`](../../custom_components/elektronny_gorod/lock.py#L62-L71), [`sensor.py:75-80`](../../custom_components/elektronny_gorod/sensor.py#L75-L80)
- **Recommended fix:** snake_case (`place_id`, `access_control_id`, ...).

### A-31. `time.py` использует local time

- **Evidence:** [`time.py:8`](../../custom_components/elektronny_gorod/time.py#L8)
- **Recommended fix:** UTC или явный timezone.

### A-32. f-string в LOGGER

- **Status:** ✅ **RESOLVED**. Release security scan по
  `LOGGER\.[a-z]+\(f["']` возвращает 0 совпадений; используется ленивое
  `%`-форматирование.

### A-33. Magic strings (`"null"`, `"accessControlOpen"`)

- **Recommended fix:** в `const.py`.

### A-34. Manifest без `quality_scale`, `integration_type`

- **Status:** ✅ **RESOLVED** в ветке `feat/bronze-entity-polish` (slice 3c). `manifest.json`: `"quality_scale": "bronze"`, `"integration_type": "hub"` (по HA dev docs: «one config_entry → many devices» — аналог Tuya/SmartThings/Husqvarna cloud integrations).

### A-35. CHANGELOG.md отсутствует

- **Status:** ✅ **RESOLVED**. Корневой `CHANGELOG.md` ведётся в формате
  Keep a Changelog; секция `[Unreleased]` подготовлена к 4.0.0.

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

### A-49. SIP credentials endpoint используется call stack

- **Status:** ✅ **RESOLVED** практической реализацией A-81 / ADR-0012:
  `api.mint_sip_device` + register-on-ring SIP stack принимают INVITE и медиа.
- **Original severity:** P1 (потенциал для звонков)
- **Evidence:** `POST /rest/v1/places/{p}/accesscontrols/{ac}/sipdevices` возвращает `{id, realm, login, password}` — SIP credentials для регистрации в SIP-сервере оператора.
- **Resolution evidence:** production + PCAP подтвердили stock sequence
  `REGISTER → INVITE → 100 Trying → 200 OK → RTP`; FCM даёт ring signal, SIP
  даёт call/media. См. A-81 и ADR-0012/0013.

### A-50. Camera motion event stream реализован; archive остаётся

- **Status:** ✅ **RESOLVED IN `feat/durable-event-history`** для verified
  forpost motion stream; Media Source/archive остаётся A-59 / Slice 2.
- **Original severity:** P2
- **Evidence:** 
  - `GET /api/mh-camera-personal/mobile/v1/cameras/{id}/events` — `{externalEvents: [{ID, Time, Duration, isAvailable}], recordingDisabledEvents: []}`
  - `GET /rest/v2/forpost/cameras/{id}/events` — альтернативный v2 endpoint
- **Runtime evidence (9.9.0 AVD):** экран Events открывает archive на точном
  timestamp; archive даёт seek, список clips/duration и download. Signed
  playback/download URL — credential, не entity attribute.
- **Resolution evidence:** `api.query_camera_events` использует exact v2 query,
  parser отбрасывает `Message`, `HistoryManager` делает silent baseline и
  bounded dedup, а per-camera `EventEntity` принимает только verified
  `EventSubjectID=126`. Requested camera ID не смешивается с внутренним
  response `CameraID`; сбой одной камеры изолирован. Motion-history entity
  disabled-by-default, поэтому camera endpoint опрашивается только после её
  явного включения пользователем.
- **Remaining scope:** старый журнал, playback/download и signed URL не входят
  в entity; это Slice 2 в
  [`features/mobile-app-parity`](../features/mobile-app-parity/README.md).

### A-51. Bootstrap response (`device-installations`) не используется для discovery

- **Severity:** P2 (зависит от стабильности hardcoded URLs)
- **Evidence:** `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations` возвращает `{AUTH_PROVIDER, MOBILE_URL.domain.{backend, genesys, stomp, expiredAt}, policy}`.
- **Impact:** интеграция уже вызывает endpoint при FCM bind, но игнорирует
  bootstrap response. Приложение **динамически** получает URLs (включая STOMP).
  У нас hardcoded `BASE_API_URL = "myhome.proptech.ru"` — если оператор
  переедет, мы сломаемся.
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

### A-54. FCM-канал и `subscriberNotifications` — реализован как канал события вызова

- **Status:** ✅ **RESOLVED** — реализация находится в master
  (`b4cece3` event entity, `7244fc4` FCM listener; последующие fixes также merged).
  Переоценено: FCM-канал больше не «за пределами проекта». Эксперимент
  (`research/intercom-call-probe/FINDINGS.md`) доказал, что событие «вызов с
  домофона» приходит **именно по FCM** — реализовано (ADR-0011): `fcm.py`
  (`DoorbellFcmListener`, `firebase-messaging`, project `ntk-myhome`) +
  `api.register_push_device` / `unregister_push_device` (привязка токена через
  `subscriberNotifications` + `device-installations`) + `event`-сущность.
  Публичный Firebase-конфиг (не секрет) — в `const.py`; per-device creds — в
  `entry.data`. Весь флоу под graceful degradation.
- **Severity:** P3 → стала feature (P1 real-time path).
- **Evidence:** `POST /rest/v1/subscriberNotifications` + `device-installations`
  отправляют `pushToken` (FCM); FCM data-push несёт `CALL_INCOMING` /
  `CALL_END_ANSWERED_MOBILE`. См. [`api-reference.md` §Push-регистрация (FCM)](../architecture/api-reference.md).
- **Известный риск / техдолг:** см. A-80 («серая зона» приватных API Google).

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

### A-56. DND switches реализованы

- **Status:** ✅ **RESOLVED** в PR #38 (commit `2dc07ae`). Новая платформа
  `switch.py` с 3 entity per place: master `dnd_root` (всегда available) +
  2 dependent `dnd_intercom_calls` / `dnd_management_company_calls`
  (`_attr_available = root.status`). Coordinator fetches DND state в
  `_async_update_data`, `async_set_dnd()` wrapper для toggle с UA race-safety.
  Translation keys в `entity.switch.{key}.name` (ru/en). 4 unit-теста
  (`tests/test_dnd.py`). См. CHANGELOG `[3.2.0]` (TBD).

### A-57. Finance fields и blocking entities реализованы

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

### A-58. Real-time и durable REST history реализованы

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
- **Status:** ✅ **RESOLVED** в master (`b4cece3`, `7244fc4`) для **события
  вызова домофона** — выбран и реализован **FCM-канал** (push
  primary), не polling. Research R-1..R-5 фактически выполнен экспериментом
  `research/intercom-call-probe/` (live-проверка 3 каналов на прод-аккаунте):
  доказано, что вызов несёт FCM, латентность sub-second. Решение —
  **[ADR-0011](../decisions/0011-doorbell-fcm-channel.md)** (заменил
  гипотетический ADR-0009-event-delivery для этого use-case). Реализация —
  `fcm.py` + `event`-сущность + `api.register_push_device`. Polling
  `/events/search` остаётся возможным fallback/backfill, но для realtime-вызова
  больше не нужен.
- **Durable status:** ✅ **RESOLVED IN `feat/durable-event-history`** — отдельный
  `HistoryManager` читает page 0 раз в пять минут, первый ответ каждого source
  устанавливает silent baseline, bounded opaque-ID watermark переживает
  restart, а overlapping poll пропускается. В HA попадают только verified
  accepted/missed call events; старые страницы не переигрываются в automation.
  `history_ws.py` + `custom:eg-event-history-card` дают постраничный browse
  старых accepted/missed строк. Отдельная history entity создаётся на каждое
  место и привязывается к устройству адреса; карточка может независимо
  объединить несколько мест/аккаунтов и фильтровать по составному source key;
  прежний per-device режим сохранён.
  Dispatcher signal изолирован по config entry; добавление нового
  place/access-control не replay-ит его старую историю. Partial frontend
  refresh сохраняет ранее загруженные строки временно недоступного feed.
  Наблюдавшийся transient `502` на `events/search` остаётся изолированной
  деградацией: browse показывает safe unavailable, poller продолжает на
  следующем интервале без немедленного duplicate POST. History accepted/missed
  entities не используют несовместимый HA doorbell device class (он
  зарезервирован за realtime `ring`/`ended` entity).
  Entity permission/source binding и sanitized allowlist response не допускают
  replay в dispatcher/state или чтение произвольного аккаунта.
- **Remaining product scope:** archive playback/download через Media Source —
  Slice 2, не часть finding о delivery.
- **Каверзы:** канал опирается на приватные API Google — долгосрочных гарантий
  нет (см. A-80). Поэтому весь FCM-флоу под graceful degradation.
- **Scope:** v1 — только NTK/myhome (`myhome.proptech.ru`). Дом.ру (HMS/Huawei
  Push) и двусторонний звук (SIP) — отдельные будущие фичи.

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
  - redacted stream в go2rtc держал redacted producer URL
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
    rtsp://127.0.0.1:8554/eg_<redacted-a>)`.
  - 12:57:25.981, 12:57:25.998 — то же для двух других redacted streams.
  - 12:58:05.469 — для ещё одной redacted camera.
  - 12:58:49.988 — `go2rtc.server WRN ... i/o timeout url=rtsp://127.0.0.1:8554/eg_<redacted-c>`.
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
  12:59:21.304 Fetching camera <redacted> stream URL ← запрос #1
  12:59:21.317 Fetching camera <redacted> stream URL ← запрос #2 (через 13 ms!)
  12:59:21.619 Response <redacted> video [200 OK]    ← разные tokens
  12:59:21.668 Response <redacted> video [200 OK]
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
- **2026-07-16 extension:** A-71 остаётся закрыт для active-consumer
  recovery. Отдельный idle external-RTSP gap и новый per-entry
  writer трекаются как [A-96](#a-96-внешний-rtsp-после-простоя-требует-предварительного-открытия-камеры-в-ha)
  / [ADR-0014](../decisions/0014-go2rtc-stream-manager.md); live acceptance
  нового пути не заменяет историческую прод-верификацию A-71.
- **Severity:** **P2 (UX, by-design)**: видео останавливается через ~30 мин
  непрерывного просмотра. **Оригинальное приложение «Мой Дом» ведёт себя
  идентично** (зависает примерно через те же полчаса) — это архитектурный
  лимит бэкенда оператора, исходящего из того, что лайв не смотрят так долго.
  Помогает ручное переоткрытие карточки (= reopen в приложении).
- **Area:** HA Stream lifecycle / go2rtc producer / operator forpost session.
- **Symptom (user-reported 2026-05-27):** «долго открытое видео перестаёт
  воспроизводиться» — frozen / чёрный экран.
- **Evidence (`...2026-05-27T14-58-18.200Z.log`):**
  - Camera Подъезд (`<redacted>`): **16×** `Error demuxing stream while finding
    first packet (Operation timed out, rtsp://127.0.0.1:8554/eg_<redacted>)`
    непрерывно **20:34:30 → 20:54:23** (~20 мин) — **без единого** `Fetching
    camera <redacted> stream URL` в этом окне (refresh не происходит).
  - go2rtc producer: `error=EOF url=ffmpeg:elektronny_gorod_..._camera_<id>`
    (апстрим оператора закончил поток) + `i/o timeout
    url=rtsp://127.0.0.1:8554/eg_<id>` (consumers не получают пакетов).
  - **Чистый TTL** (по последнему раунду обновления, без загрязнения
    многократными reload): PUT **21:25:14** → first error **21:55:19** =
    **30:05** для трёх камер (минтились вместе → умерли вместе).
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
    "go2rtc_password": "[REDACTED]",
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


### A-79. validate_go2rtc — нет TCP-probe RTSP-порта

- **Status:** ✅ **RESOLVED** — feat/g7-rtsp-probe-and-tests.
- **Severity:** **P3 (UX-улучшение валидации; не блокирует работу).**
- **Area:** `go2rtc.py:validate_go2rtc` (новая фаза probe),
  `tests/test_go2rtc_validate.py`, `tests/test_go2rtc_upsert.py`.
- **Symptom:** До фикса: HTTP API go2rtc успешно валидируется, юзер
  жмёт «Сохранить» — а RTSP-порт `8554` закрыт (firewall, иной
  bind-address, go2rtc собран без RTSP). Юзер обнаруживает проблему
  только когда камера не воспроизводится — нет привязки причины к
  config-flow шагу.
- **Evidence:** аудит интеграции go2rtc-конфигурации (G-1..G-9 review
  по issue #29). HTTP probe покрывает только `/api` и `/api/streams`,
  RTSP-listener не проверяется ни разу.
- **Fix:** после успешного HTTP-чека делаем `asyncio.open_connection
  (rtsp_host, 8554)` с timeout 3с. При неудаче возвращаем отдельный
  error key `go2rtc_rtsp_port_closed` с понятным сообщением (firewall
  / bind-address / RTSP-support).
- **Regression-guard:** 39 unit-тестов в `tests/test_go2rtc_validate.py`
  + `tests/test_go2rtc_upsert.py` — first direct unit coverage для
  `validate_go2rtc` / `_go2rtc_upsert_stream` / `cleanup_go2rtc_stream`
  (раньше тестировались только через options-flow mock или camera
  integration). Закрывает также **G-9** из go2rtc-аудита.
- **Lesson learned:** при добавлении конфигурации с разделёнными
  транспортами (HTTP API + RTSP) — валидировать **каждый** транспорт
  отдельно. HTTP success ≠ RTSP success.

### A-80. FCM-приём вызова — «серая зона» приватных API Google + новая зависимость

- **Status:** 🟡 **KNOWN RISK / accepted tech-debt** (зафиксирован при
  реализации события вызова, [ADR-0011](../decisions/0011-doorbell-fcm-channel.md)).
  Не баг и не задача «исправить» — задокументированный риск с уже встроенным
  митигатором (graceful degradation).
- **Severity:** P2 (надёжность фичи, не блокер интеграции).
- **Area:** `fcm.py` (`DoorbellFcmListener`), `manifest.json:requirements`.
- **Risk 1 — приватные API Google.** Серверный приём FCM без Android-устройства
  опирается на **недокументированные приватные API** (checkin / register /
  MTalk). Google уже ломал их (20.06.2024 — «умерли» старые версии всех
  библиотек). Долгосрочных гарантий нет: «работает, пока работает».
- **Risk 2 — новая зависимость `firebase-messaging>=0.4`** (тянет protobuf /
  http_ece / cryptography). Раньше `requirements` был пуст (всё из HA core) —
  теперь интеграция имеет внешний pip-deps.
- **Risk 3 — ToS.** Эмуляция клиента приложения формально не «официально
  поддержана» (как и весь mirror-app-подход, ADR-0006).
- **Mitigation (уже встроено):** весь FCM-флоу под `try/except` — при любом
  сбое (Google сломал API / нет сети / протух токен) логируется warning,
  остальная интеграция (polling-данные) работает, событие просто не стреляет,
  `async_setup_entry` не падает. Логика изолирована в `fcm.py` за интерфейсом
  `SIGNAL_DOORBELL` — замена механизма (другая библиотека / sidecar-bridge) не
  задевает `event`-сущность.
- **Watch:** при breakage приватного API — bump `firebase-messaging` (линия
  поддержки Lemoine → sdb9696 переживает изменения через обновление зависимости).

### A-81. Приём вызова домофона по SIP + показ экрана вызова (фундамент two-way audio)

- **Status:** ✅ **RESOLVED** — реализация находится в master (включена в историю,
  влитую PR #69); точная pre-answer модель дополнительно подтверждена A-91.
- **Severity:** P1 (real-time path для домофонных звонков — двусторонний звук).
- **Area:** `sip/` (новый пакет, 14 модулей включая `bridge.py` и `uplink.py`), `call_camera.py`
  (новый), `api.mint_sip_device`, `services.yaml` (`answer` / `hangup`),
  `const.py:DOORBELL_CALL_WINDOW_FALLBACK_SEC`, `_logging.py:SENSITIVE_KEYS` (+`realm`),
  `go2rtc.py` (`upsert_audio_stream` / `remove_audio_stream`).
- **Что доставлено:** приём активного вызова домофона + downlink-вывод звука +
  показ экрана вызова. Модель **register-on-ring (ADR-0012, held-short-window)**:
  по FCM `CALL_INCOMING` (до нажатия «Ответить») минтит SIP-креды →
  `REGISTER` (Expires=30, проприет. push-params) → держит форкнутый сервером
  `INVITE` (100 Trying); по нажатию «Ответить» → `200 OK` (локальный SDP,
  G.711, без STUN/ICE/SRTP) → RTP-latching. SIP `CANCEL` (панель сбросила) →
  `487` + мгновенный dismiss экрана. Подробности — в
  [`call-answer-model.md`](../features/intercom-two-way-audio/call-answer-model.md)
  + [ADR-0012](../decisions/0012-register-on-ring.md).
- **Evidence:** полный Android PCAP 2026-07-13: три вызова подряд дали
  `REGISTER → INVITE → 100 Trying`; два held около 24с до `CANCEL`/`603`, один
  принят `200 OK` и перешёл в RTP. Production REGISTER теперь зеркалит Contact
  приложения (`Call-Id` из FCM, без лишнего `transport` parameter) и
  `Accept: application/sdp`. Suite **392 passed**.
- **Scope текущего master:** приём вызова (register-on-ring/ADR-0012) +
  **downlink-вывод звука гостя** (`sip/bridge.py` `AudioBridge`) + показ экрана
  вызова (`call_camera.py`) + **uplink-микрофон** через HA-WebSocket →
  `UplinkSink` → SIP-RTP (ADR-0013/A-85).
- **Deferred (из code-review, by-design на этом слайсе):**
  1. **A-21 layered timeout.** `mint_sip_device` латентно-критичен
     (REGISTER должен опередить INVITE) — обёрнут точечным
     `asyncio.timeout(8с)` в `call_controller.py` (`_MINT_TIMEOUT_SEC`).
     Shared `HTTP` дополнительно применяет глобальные REST/binary
     `ClientTimeout`; в [A-21](#a-21-нет-timeoutretrybackoff) остаётся только
     retry/backoff для идемпотентных GET.
  2. **Single concurrent call (by-design ограничение слайса).** Фиксированные
     порты SIP/RTP + модель **first-answer-wins** → один активный разговор
     одновременно. Guard в `call_controller.py` (два concurrent answer создали
     бы 2 `SipManager` на фикс-портах). Снятие ограничения (динамические порты /
     пул) — будущий слайс, не блокер.
- **Связанные findings:** [A-49](#a-49-sip-credentials-endpoint-не-используется)
  (`sipdevices` endpoint — теперь используется), [A-58](#a-58-real-time-event-delivery-resolved-durable-rest-history-remains)
  / [A-54](#a-54-fcm-канал-и-subscribernotifications--реализован-как-канал-события-вызова)
  (FCM-канал вызова — триггер для answer), [A-80](#a-80-fcm-приём-вызова--серая-зона-приватных-api-google--новая-зависимость)
  (та же mirror-app серая зона + push-params).
- **Контракт безопасности:** SIP `realm` (`{ac_id}.intercom.{operator}.ru` —
  содержит acId, парный к SIP-паролю) добавлен в `SENSITIVE_KEYS`; SIP
  login/password не логируются (no-secret-logs rule).

### A-86. FCM push-receiver молча умирает → вызовы домофона пропадают (watchdog)

- **Status:** ✅ **RESOLVED** — merged в master через **PR #66**
  (`fix/fcm-reconnect-watchdog`, commit `575d885`). Bug-fix; root cause подтверждён
  runtime-evidence (прод-лог 2026-06-24).
- **Severity:** P1 (вызовы домофона молча перестают приходить — пропущенные
  звонки, статус интеграции при этом `loaded`, юзер не узнаёт).
- **Area:** `fcm.py` (`DoorbellFcmListener`: `_async_connect` / `_async_watchdog`
  / `_async_disconnect` / `async_stop`).
- **Симптом:** прод 2026-06-24 после сетевого блипа (работы с роутингом) —
  `firebase_messaging.fcmpushclient: Shutting down push receiver due to 3
  sequential errors of type ErrorType.CONNECTION`; далее FCM-сокет мёртв,
  `CALL_INCOMING`-пуши не приходят, переподнятия нет.
- **Root cause (confirmed):** `FcmPushClientConfig.abort_on_sequential_error_count`
  по умолчанию `3` → библиотека выключает receiver навсегда после 3 ошибок
  подряд. `async_start` был fire-and-forget — контроля живости нет → молчаливая
  смерть.
- **Fix:** (1) `FcmPushClientConfig(abort_on_sequential_error_count=None)` —
  бесконечный reconnect внутри библиотеки; (2) watchdog
  (`async_track_time_interval`, 2 мин) опрашивает `client.is_started()`, при
  мёртвом receiver / провале первичного checkin (`client=None`) логирует warning
  и переподнимает (`_async_connect`); guard `_reconnecting`; таймер отменяется на
  unload. Видимость — лог-warning (по согласованию: отдельный sensor не нужен).
- **Evidence:** прод-лог (20:47:22) + восстановление через `reload_config_entry`
  (`FCM doorbell listener запущен`). 9 тестов `test_fcm.py` (abort=None, watchdog
  reconnect / skip-healthy, idempotency, cleanup). Independent code-review —
  approve (P0/P1 нет), контракт `firebase-messaging 0.4.5` верифицирован.
- **Связь:** [ADR-0011](../decisions/0011-doorbell-fcm-channel.md) (FCM-канал вызова).

### A-87. Фаза вызова залипает в `ringing`/`ended` без FCM `ended` (ring-таймаут)

- **Status:** ✅ **RESOLVED** — merged PR #68 (`feat/intercom-call-ui`, merge `424cd1a`).
  Bug-fix. Root cause подтверждён runtime-evidence (прод logbook/logger 2026-07-06).
- **Severity:** P2 (карточка/сенсор показывают фантомный «Входящий вызов»
  бесконечно; статус интеграции `loaded`, реального звонка нет).
- **Area:** `sip/call_controller.py` (`handle_signal` / `_emit_call_state` /
  `_schedule_ring_timeout` / `_on_ring_expired` / `_schedule_idle_reset`).
- **Симптом:** прод 2026-07-06 — `sensor.*_call_state` двух домофонов застряли:
  один в `ringing`, другой в `ended` (одинаковый `last_changed` = момент старта
  HA). В logbook у застрявшего — единственное событие `→ ringing`, больше ничего.
- **Root cause (confirmed):** контроллер держит `ringing` до FCM `ended`, а
  страховочный release (`_schedule_hold_timeout`) ставится **только** при
  поднятом SIP-hold (`held=True`). В degrade (held не поднялся), при
  неотвеченном звонке без `CALL_END`, и при **реплее протухшей FCM-очереди
  после рестарта HA** (звонок пришёл во время downtime → `CALL_INCOMING`
  доставлен на старте, парный `CALL_END` — нет) фаза `ringing` не имеет
  таймаута. Плюс терминалы `ended`/`error` не возвращались в `idle`.
- **Fix:** (1) **ring-таймаут окна ответа** — на `ring` таймер до
  `call_invalidated`-дедлайна + грейс; если к нему всё ещё `ringing` → авто-
  `ended` (+ release держимого). (2) **guard протухшего `ring`** — если дедлайн
  окна ответа уже в прошлом, фаза `ringing` не публикуется. (3) **возврат
  терминала** — `ended`/`error` через `_IDLE_RESET_SEC` (~6с) сбрасываются в
  `idle`; отменяется новым `ring`/фазой.
- **Evidence:** прод logbook (`kalitka_2_call_state` — единственное `→ ringing`
  20:34:43) + сверка кода (`_schedule_hold_timeout` под `held=True`). 6 тестов
  `test_sip_call_controller.py` (ring-таймаут expiry/noop-after-answer/schedule,
  протухший ring, ended→idle, new-ring отменяет idle-reset) + `test_event.py`
  (drain/cancel loop-таймеров call_controller после A-72). 367 тестов зелёные.
- **Связь:** [ADR-0011](../decisions/0011-doorbell-fcm-channel.md) (FCM-канал),
  [ADR-0012](../decisions/0012-register-on-ring.md) (register-on-ring / окно).

### A-85. Uplink-микрофон — говорить гостю (завершение two-way audio, ADR-0013)

- **Status:** ✅ **RESOLVED** — реализация находится в master (включена в историю,
  влитую PR #69). LIVE-подтверждено в проде **2026-06-24**: микрофон браузера
  дошёл до домофона, пользователь слышал себя у двери.
- **Severity:** P1 (закрывает двусторонний звук — последний хоп over A-81 downlink).
- **Area:** `uplink_ws.py` (новый — WS-команда + регистрация Lovelace-карты),
  `sip/uplink.py` (`UplinkSink`: микрофон-PCM → resample 8к → G.711-кадры),
  `sip/rtp.py` (дрейф-компенсированный пейсинг `run_uplink`),
  `sip/call_controller.py` (`feed_uplink` + lifecycle `UplinkSink`,
  `uplink_provider ← sink.next_frame`), `sip/manager.py` (`uplink_provider`),
  `www/eg-intercom-mic-card.js` (Lovelace-карта `getUserMedia` → HA-WS).
- **Что доставлено (механизм #1 — HA WebSocket binary-audio, ADR-0013):**
  своя Lovelace-карта `getUserMedia` → Int16 PCM по авторизованному HA-WebSocket
  (`elektronny_gorod/intercom_uplink`, `async_register_binary_handler`) →
  `DoorbellCallController.feed_uplink` → `UplinkSink` → resample/G.711 →
  `SipManager.uplink_provider` → дрейф-компенсированный RTP-uplink в домофон.
  **Без go2rtc/TURN/новых зависимостей** (`audioop-lts` уже есть; pure-Python).
- **Evidence:** loopback-самотест (синтетический тон через `UplinkSink`-логику →
  RTP → декод) — дрейф пейсинга **3мс / 9с**, **0 провалов**, тон цел;
  дрейф-фикс `rtp.py:run_uplink` устранил заикания (наивный `asyncio.sleep(0.02)`
  копил ~12% дрейфа → саттурация буфера → drop-кадры). Подробности —
  [ADR-0013](../decisions/0013-uplink-mic-transport.md) §Decision +
  research FINDINGS §D-audio-variants.
- **Отвергнутые варианты (эмпирически, не догадки):** #2 go2rtc WHIP-pull
  (нужен стрим-таргет/yaml + TURN на 4G), #3 go2rtc exec-backchannel
  (`exec:#backchannel=1` заблокирован через REST на Frigate-go2rtc + upstream-баги
  + TURN), #4 aiortc (конфликт `av<17` vs HA `av==17.0.1`, нет колёс armv7l).
  Пробы — `research/intercom-call-probe/` (scaffolding для будущего сравнения,
  не в проде).
- **Известные ограничения / accepted-risk:**
  1. **S-UP-01 (accept-risk, документировано).** Uplink-команда доверяет **всем**
     authenticated HA-юзерам — любой авторизованный HA-юзер может «говорить» в
     активный вызов. Паттерн **зеркалит HA voice-assistant** (тот же
     авторизованный WS, что весь UI); окно вызова эфемерно (~120с). Guard
     **не добавляется** by-design — см. [`security.md#S-19`](security.md).
  2. **P2-2 (multi-call selection недетерминирован).** При нескольких активных
     контроллерах WS-команда выбирает контроллер недетерминированно (single
     concurrent call — by-design ограничение слайса, см. A-81 deferred §2).
  3. **Area-B P3-1 (LAN-exposure downlink-аудио).** `AudioBridge` биндит
     `0.0.0.0:40020` для доступа go2rtc по LAN — эфемерно на время вызова,
     by-design. См. [`security.md#S-19`](security.md).
- **Deferred (polish, Slice 2b):** явная `stop`-команда (handler-слоты idle-копятся
  при многократном toggle в одной сессии — митигирован card-side кэшем подписки,
  не утечка данных, S-UP-02); hands-free (непрерывный поток, джиттер-буфер, UX
  mic-toggle).
- **Связанные findings:** [A-81](#a-81-приём-вызова-домофона-по-sip--показ-экрана-вызова-фундамент-two-way-audio)
  (downlink + приём вызова — фундамент, поверх которого строится uplink),
  [A-49](#a-49-sip-credentials-endpoint-не-используется) (`sipdevices`),
  [A-80](#a-80-fcm-приём-вызова--серая-зона-приватных-api-google--новая-зависимость)
  (mirror-app серая зона).

## Findings из рефактор-оценки camera.py / go2rtc.py (2026-06-23)

> Источник — code-reviewer-оценка `camera.py` (773 строки, god-class на
> 5 ответственностей, накоплен за 3 итерации A-71 v1/v2/v3) + `go2rtc.py`
> на тех-долг (2026-06-23). Главный вывод: go2rtc REST-логика размазана между
> модулями (upsert/src в `camera.py`, validate/cleanup в `go2rtc.py`, 3 копии
> auth-header). Оба finding-а ниже — **тех-долг (maintainability), не bug** —
> low-priority backlog, **не блокируют** аудио-фичу (two-way audio).
>
> **Reconciliation 2026-07-16:** [ADR-0014](../decisions/0014-go2rtc-stream-manager.md)
> довёл консолидацию ordinary operator-camera path: `Go2RtcClient`
> владеет HTTP/RTSP transport, `CameraStreamManager` — write/lifecycle,
> `camera.py` — HA triggers. Поэтому A-82 resolved-in-branch; A-83
> остаётся intentional backlog, A-84 только partially mitigated до
> live persistence check. Security status ведётся отдельно в `security.md`.

### A-82. go2rtc-transport в `ElektronnyGorodCamera` не вынесен в go2rtc-клиент

- **Status:** 🟢 **resolved-in-branch (pending merge
  `feat/go2rtc-stream-manager`)**. Live external-RTSP acceptance отдельно
  трекается в A-96.
- **Severity:** **P3 (maintainability)** — не bug, поведение корректно.
- **Area:** `camera.py` (god-class на 5 ответственностей), `go2rtc.py`.
- **Implementation evidence:** `go2rtc.py:Go2RtcClient` владеет
  list/get/PATCH/DELETE, auth headers и RTSP URL; `stream_manager.py`
  владеет operator-camera write/lifecycle. `camera.py` сохраняет
  только HA-specific wrappers/triggers и не делает go2rtc HTTP.
- **Tests:** `test_go2rtc_client.py`, `test_stream_manager*.py`,
  `test_camera_auto_recovery.py`, `test_camera_call_video_rtsp.py`.
- **Merge reconciliation:** после merge в master перевести в
  `✅ RESOLVED` с merged ref; до этого не считать release state.

### A-83. Auto-recovery state machine (A-71) не выделена в отдельный helper

- **Status:** 🔴 **OPEN / backlog (low-priority, tech-debt)**.
- **Severity:** **P3 (maintainability)** — не bug; код работает в проде
  (ADR-0009, прод-верификация v3.2).
- **Area:** `camera.py` (`_on_stream_state_change`, `_async_recover_stream`,
  `_async_poll_go2rtc_health`, `_async_proactive_refresh`).
- **Evidence:** A-71 auto-recovery (v1 event-driven + v2 go2rtc producer-health
  poll + v3 proactive keep-alive) живёт прямо в `ElektronnyGorodCamera`:
  `_on_stream_state_change`, `_maybe_schedule_stream_recovery`,
  `_async_recover_stream`, `_async_poll_go2rtc_health`, `_async_proactive_refresh`
  Manager теперь владеет write/schedule/reconcile, но сами A-71
  triggers намеренно остались в entity (ADR-0014 non-goal).
- **Motivation:** выделение в отдельный `_StreamRecovery` helper изолировало бы
  ~250 строк state machine от entity-логики (snapshot/stream/coordinator) —
  крупнейший вклад в god-class.
- **Risk / объём:** 🔴 **ВЫСОКИЙ риск.** Это **deterministic-tuned** код
  (тайминги `STREAM_RECOVERY_COOLDOWN` / `GO2RTC_HEALTH_POLL_INTERVAL` /
  `GO2RTC_PROACTIVE_REFRESH_INTERVAL` подобраны эмпирически, ADR-0009,
  PATCH-first ROOT CAUSE v3.2), работает в проде. Рефакторинг ломает auth
  молча, как и любая правка hot-path lifecycle. Объём **L**.
- **Recommended first step:** **НЕ делать спекулятивно.** Только через
  **отдельный ADR** (supersede/extend ADR-0009) + **DIAG-baseline** (снять
  прод-метрику recovery-циклов до рефактора, чтобы доказать поведенческую
  эквивалентность после). Без этого — оставить как есть. low-priority backlog.

### A-84. go2rtc config bloat — стрим дописывается, а не мёржится (unbounded)

- **Status:** 🟡 **PARTIALLY RESOLVED in
  `feat/go2rtc-stream-manager`; live config-persistence check remains.**
- **Severity:** **P2 (real bug + security-smell)** — не косметика: конфиг растёт
  безгранично, протухшие operator-токены копятся на диске.
- **Area:** `go2rtc.py:Go2RtcClient.async_patch_stream`
  (+ `upsert_audio_stream` для call stream), go2rtc config-persist.
- **Evidence (прод, 2026-06-23, найдено пользователем):** в `go2rtc_homekit.yml`
  **сотни** повторяющихся блоков `streams:`, каждый — одна камера со свежим
  operator-RTSP вида `ffmpeg:https://forpost-NN.novotelecom.ru:18081/rtsp/<accId>/<TOKEN>/d=1#video=copy#audio=aac#audio=opus`
  (TOKEN ротируется per-fetch). Симптом в логах: `go2rtc cleanup failed: 400
  yaml: path not exist` (DELETE не находит стрим в дублирующемся YAML).
- **Hypothesis (нужен DIAG):** на каждое `stream_source()` (открытие камеры)
  интеграция получает у оператора **новый** ротируемый RTSP-URL → upsert'ит в
  go2rtc; go2rtc 1.9.14 на API-write **дописывает новый `streams:`-блок** в
  конфиг-файл (не merge в один map) → за время жизни интеграции — сотни блоков.
  YAML дубль-ключи: функционально побеждает последний, но файл растёт безгранично.
- **Impact:** (1) безграничный рост конфига; (2) протухшие **operator-токены на
  диске** в plaintext (security-smell, ср. [`no-secret-logs.md`](../../.claude/rules/no-secret-logs.md));
  (3) `cleanup failed: path not exist` на teardown стримов вызова.
- **Risk / объём:** трогает `stream_source` hot path (proven, история A-71) →
  **через DIAG + go2rtc-консолидацию** (план Task 2 / R1-R7). M-L.
- **Recommended first step:** controlled-DIAG на throwaway-стриме — какой write
  (PATCH vs PUT) дописывает блок (повторить upsert с разным src, посмотреть рост
  конфига) → выбрать фикс: пропускать re-upsert если src не изменился, или
  периодическая компакция конфига, или go2rtc-side опция → **сложить в
  go2rtc-консолидацию (R7)**. Пользователь чистит текущий конфиг сам.
- **2026-07-16 mitigation in branch:** ordinary `eg_<camera_id>` writes теперь
  идут только через PATCH-only client; PUT fallback удалён. Manager
  также удаляет ineligible zero-consumer streams. Это убирает
  известную destructive-write ветку, но не доказывает, что конкретная
  сборка go2rtc не персистит repeated PATCH как duplicate YAML.
- **Remaining acceptance:** после >1h/live cycles сравнить размер и
  структуру go2rtc config; без этого finding не закрывать.

### A-88. Видео вызова рвётся при конкурентных клиентах / пересборка стрима (anti-churn)

- **Status:** ✅ **RESOLVED** — merged PR #69. Прод-верификация сценария
  «2 устройства одновременно» остаётся эксплуатационной проверкой, не merge-блокером.
- **Severity:** **P1** — видео вызова нестабильно у пользователя («на ноуте нет —
  на телефоне есть», задержка 3/5/иногда 20с, иногда только картинка).
- **Area:** `call_camera.py` (`stream_source`), `sip/call_controller.py`
  (`active_call_media`), `go2rtc.py` (`upsert_audio_stream`), `camera.py`
  (общий `eg_<id>`).
- **Evidence (прод 2026-07-08, полный разбор: HA-лог + go2rtc-проба + браузерный
  WebRTC-хук):**
  - Видео вызова = **copy с общей forpost-камеры домофона**: `eg_intercom_call`
    **вложен** в `rtsp://127.0.0.1:8554/eg_<redacted>#video=copy` + аудио-мост. SIP
    от панели несёт **только аудио** (G.711), видео — из camera-API оператора.
  - go2rtc **отдаёт валидный кадр** (проба `frame.jpeg` = 65 КБ, `ff d8 ff`,
    H264) — серверный пайплайн исправен.
  - При нескольких консьюмерах (ноут + телефон, ringing-превью + стрим вызова)
    каждое открытие **пере-фетчит одноразовый operator-URL и пере-собирает
    продюсер** → redacted stream `Error opening (Invalid data)` / `Operation timed
    out`, у части клиентов видео пустое (браузерный хук: `frames=0 0x0`).
  - После звонка HA Stream worker `camera.*_intercom_call` **не гасится** →
    `404 eg_intercom_call` каждые ~60-90с 9+ минут.
- **Root cause:** пересборка/пере-PUT общего продюсера на **каждое** открытие
  клиента; одноразовый forpost-URL + (вероятно) одна operator-сессия на камеру →
  конкурентные консьюмеры рвут друг друга.
- **Recommended fix (фаза A):**
  1. Собирать стрим вызова **один раз на звонок** (warm-up на `answer`), внутри
     звонка все клиенты **делят один продюсер** — не пересобирать per-open (дедуп
     собранного URL, как `_last_src` в `camera.py`).
  2. Обновления только **PATCH** (не PUT — не убивает живой продюсер, A-71).
  3. **Teardown** `eg_intercom_call` + остановка HA Stream worker на завершении
     вызова (убрать вечные 404).
  4. НЕ давать вызову отдельный второй operator-pull (две сессии к одной камере
     → оператор рвёт одну) — делить единый продюсер камеры домофона.
- **First step:** дедуп сборки в пределах звонка в `call_camera.stream_source` +
  teardown стрима/worker на `ended`.
- **Resolution (merged PR #69):**
  1. ✅ Сборка стрима **один раз на звонок** — кэш `(bridge, url)` по объекту
     `bridge` (`call_camera.stream_source`), повторные открытия отдают готовый URL.
  2. ✅ **Dedup конкурентных первых открытий** — in-flight future (warm-up +
     фронтенд одновременно не пере-собирают, зеркалит A-68 в `camera`).
  3. ✅ **Shared producer** — `camera.async_go2rtc_video_rtsp()`: reuse `eg_<id>`
     без второго operator-pull, **только если продюсер живой** (`bytes_recv` > 0).
  4. ✅ **PATCH-first** upsert стрима вызова (`go2rtc.upsert_audio_stream`, A-71).
  5. ✅ **Teardown** `eg_intercom_call` на `ended`/`error` (`_teardown_call_stream`).
  Тесты: `test_call_camera.py`, `test_camera_call_video_rtsp.py`, `test_go2rtc_audio.py`.
  **Остаток:** прод-верификация «2 устройства одновременно → видео на обоих, без
  `Invalid data`; после `ended` нет 404».
- **Rollback:** всё в git-коммитах; прод-файлы восстанавливаются из git + docker cp.

### A-90. Живой разговор гаснет по FCM-пушу `ended` (авто-сброс принятого вызова)

- **Status:** ✅ **RESOLVED** — merged PR #69.
- **Severity:** **P1** — карта «Вызов завершён» на живом разговоре (домофон
  продолжает говорить), пользователь теряет управление вызовом.
- **Area:** `sip/call_controller.py` `handle_signal` (ветка `ended`).
- **Evidence (прод 2026-07-08 20:57):** оператор при «Принять» снимает
  ring-уведомление со ВСЕХ устройств → шлёт FCM `ended` (`reason=answered_elsewhere`)
  через ~0.7с после ответа, хотя SIP-диалог жив (реальный BYE — на ~6с позже).
  `handle_signal("ended")` принимал push за hangup и гасил `sensor.*_call_state`.
  Cross-call guard (A-88-серия) не ловит — тот же `call_id`/`ac`, не чужой вызов.
- **Root cause:** для принятого в HA вызова FCM `ended` — не сигнал завершения
  (это лишь снятие ring-уведомления), но код трактовал его как hangup.
- **Fix:** для уже принятого вызова (`self._manager.in_call`) FCM `ended`
  игнорируется — источник истины о завершении принятого разговора это SIP
  (BYE→`_schedule_audio_cleanup`, CANCEL→`_on_ring_cancelled`, `hangup`, страховка
  `_MAX_CALL_SEC`). Для неотвеченного (`holding`/`ringing`, `in_call`=False) FCM
  `ended` по-прежнему завершает (ответ был не в HA). Guard стоит **после**
  cross-call guard. Тесты — `test_sip_call_controller.py`
  (`test_fcm_ended_ignored_during_active_call`, `test_fcm_ended_clears_held_call_when_not_in_call`).
- **Известный tradeoff:** при потерянном SIP BYE экран «активен» до `_MAX_CALL_SEC`
  (120с) — приемлемо (BYE обычно приходит), backstop задокументирован.

### A-89. Мульти-вызов: смена звонящего домофона (не одновременные разговоры)

- **Status:** ✅ **RESOLVED** — merged PR #69. Прод-верификация сценария
  «звонок №1 не отвечать → звонок №2 → карта показывает №2 → принять №2» остаётся.
- **Severity:** **P2** — UX. Текущее поведение — by-design single concurrent call.
- **Area:** `sip/call_controller.py` `handle_signal` (ring-guard
  `if self._manager is not None: игнор параллельного ring`).
- **Fix (реализовано):** ring-guard ветвится по `self._manager.in_call` vs
  `holding`. `in_call` → игнор (одновременный второй вне scope). `holding` +
  `ring` другого домофона → `_async_switch_caller(old_manager)`: `old_manager.
  async_hangup()` под `_answer_lock` (release SIP/RTP) → `_async_hold_current`
  поднимает новый held; `self._manager` обнуляется синхронно в `handle_signal`
  (иначе hold нового вернётся рано на живом старом), повторный `ring` того же
  `call_id` — дедуп. Карта переключается синхронно (`self._active`=новый + `RINGING`,
  без промежуточного `ENDED`). **Два P1-фикса из code-review до merge:** (1)
  `_emit_call_state` дедуп сделан **identity-aware** (`state==_call_state` И тот же
  `call_id`) — иначе RINGING→RINGING при смене глушился, sensor №2 не получал события,
  карта не переключалась; (2) `SipManager.detach()` синхронно снимает колбэки старого
  manager при switch — иначе поздний CANCEL/BYE №1 в окне до `async_hangup` затирал
  вызов №2 (cross-call порча + утечка портов). Тесты — `test_sip_call_controller.py`
  (`test_ring_switches_caller_while_holding` с проверкой ids №2 в payload,
  `test_ring_same_held_caller_ignored`, `test_ring_ignored_during_active_call`,
  `test_switch_caller_releases_old_and_reholds_new`, `test_switch_detaches_old_manager_callbacks`).
- **Прод-риск (P2-C, не блокер):** rebind фикс-портов SIP/RTP сразу после release —
  asyncio-close отложен → возможен `EADDRINUSE`, hold №2 молча деградирует в
  register-on-answer. Проверить на живом железе (см. Verification B в плане).
- **Evidence (прод):** пока 1-й вызов held (ещё не отвечен), `ring` со 2-го
  домофона **игнорируется** → 2-й домофон не появляется, принять нельзя, пока 1-й
  не завершится.
- **Уточнение требования (пользователь):** НЕ нужны одновременные разговоры по
  нескольким домофонам. Нужна **смена активного звонящего**: курьер позвонил в
  один, потом в другой (пока не открыли) → экран должен **переключиться** на
  новый звонящий домофон.
- **Recommended fix (фаза B):** в `handle_signal` на `ring` различать
  **holding** (ещё не ответили) vs **in_call** (идёт разговор): при holding +
  новый ring — снять старый held (release) и захватить новый вызов (переключение
  звонящего домофона); при in_call — оставить текущий (одновременный разговор вне
  scope). Фикс-порты SIP/RTP свободны для held-переключения.
- **First step:** в ring-guard ветвление holding→release+re-hold нового вызова.

### A-91. Ложная атрибуция «Занято» SIP-механике HA

- **Status:** ✅ **RESOLVED** — merged PR #69; причина отделена от интеграции,
  штатная SIP-модель восстановлена и уточнена по полному PCAP.
- **Severity:** P1 — диагностическая изоляция временно отключала FCM/SIP и ломала
  реальный сценарий ответа, а исходная гипотеза обвиняла pre-answer hold HA.
- **Evidence (production + Android PCAP, 2026-07-13):** при полностью отключённых
  FCM/SIP механизмах HA штатное приложение воспроизводит «Занято» на связанной
  панели B во время звонка с A. Панели имеют общий place, но разные
  access-control id. В PCAP активен один Android Contact; забытых HA/Python SIP
  процессов и дополнительных registrar bindings не обнаружено. Штатный клиент
  на каждом звонке выполняет `REGISTER → INVITE → 100 Trying` и держит INVITE.
- **Fix:** удалена временная push-isolation; основной controller снова делает
  register-on-ring. Production REGISTER теперь точно передаёт `Call-Id` из FCM,
  `Accept: application/sdp` и форму Contact без лишнего `transport` parameter.
  Fallback register-on-answer использует тот же профиль. Suite **392 passed**.
- **Граница вывода:** доказано, что side effect не уникален для HA. PCAP не раскрывает
  внутреннюю логику группировки панелей, поэтому более узкая серверная/аппаратная
  причина не заявляется.

### A-92. HTML service-pipe/VPN block маскируется под обычную API-ошибку

- **Severity:** P2 — diagnostics/reliability, не regression текущего happy path.
- **Area:** `http.py` + широкие fallback-ветки `api.py`.
- **Evidence (static APK diff 9.9.0, 2026-07-15):** stock client распознаёт
  HTML block-page по `REQUEST-ID` либо блоку `id="info"` с `datetime:`/`ip:`,
  бросает отдельный `ServicePipeBlockException` и открывает `VpnWarningActivity`.
  Пользовательский текст явно связывает блокировку с работой вне РФ/VPN.
  В снятых HAR happy-path block page не встречался — формат подтверждён static,
  сам runtime-trigger пока не воспроизведён.
- **Current behavior:** `HTTP.__request` превращает любой non-2xx в generic
  `ClientError`; `query_cameras`/`query_public_cameras`/`query_sections` и часть
  settings-методов ловят широкий `Exception` и возвращают пустые коллекции.
  Геоблок/WAF может выглядеть как «у аккаунта нет камер», а diagnostics не даст
  операторский request-id.
- **Recommended fix:** отдельная безопасная классификация block-page без
  логирования IP/body; сохранять только redacted correlation/request-id и
  поднимать typed error в coordinator/diagnostics вместо empty-data fallback.
  Перед реализацией снять HAR с воспроизведённым VPN/block сценарием и закрепить
  HTML fixture без реальных идентификаторов.
- **Не делать:** не логировать полный HTML, IP, headers или auth context.

### A-93. Guest invitation есть в приложении, но нет HA action

- **Severity:** P2 feature gap; **security-sensitive**.
- **Evidence:** AVD «Мой Дом» 9.9.0: People → Add guest показывает QR и
  share-link. APK Retrofit/DTO: `POST /api/mh-auth/mobile/v1/guests/link`
  с query `placeId`, `app`; response `{data:{link,message}}`. NTK `app=2`,
  ERTH `app=4`. Decrypted runtime capture подтвердил NTK POST без body, HTTP
  200 response и HTTP 401 non-JSON при отсутствующем Authorization. Runtime
  link не сохранён, потому что это access credential.
- **Current behavior:** `query_places(place_id)` уже может получить people
  relations, но action создания приглашения отсутствует.
- **Recommended fix:** owner-side response-only action
  `create_guest_invite`, admin policy, no entity/persistence. Link/message
  возвращаются только вызывающему клиенту; добавить redaction и sentinel test.
  Capture prerequisite закрыт; commit-safe fixtures лежат в
  `tests/fixtures/mobile_app_9_9_0/`. ERTH `app=4` остаётся static-only.
- **Non-goal:** принимать invitation за гостя или публиковать people names/
  account IDs в entity attributes.
- **Plan:** [`features/mobile-app-parity`](../features/mobile-app-parity/README.md).

### A-94. Access-key inventory/settings отсутствуют

- **Severity:** P2 feature gap; account/tariff-dependent.
- **Evidence:** одинаковые static Retrofit/DTO contracts в обеих APK 9.9.0:
  list by `placeId`, lookup, register, delete, rename, reactivate and new
  notification-status PUT under `mh-access-key`. Current AVD account did not
  expose the enabled screen, so runtime contract is missing.
- **Security:** `accessKeyCode` is a physical credential. It must be discarded
  at the parser boundary and never become `unique_id`, state, attributes, log
  or diagnostics. Stable identity is server `key_service_id`.
- **Recommended fix:** after enabled-account HAR, ship read-only inventory
  disabled by default; notification switch is a later non-optimistic slice.
  Register/delete/rename/reactivate require separate admin/security approval.
- **Caveat:** APK labels key-use history “Coming soon”; do not claim support.
- **Plan:** [`features/mobile-app-parity`](../features/mobile-app-parity/README.md).

### A-95. Private-camera controls отсутствуют

- **Severity:** P2 feature gap; private hardware required.
- **Evidence:** static 9.9.0 contracts for feature-info, motion parameters/
  sensitivity, event/continuous record mode, microphone/speaker volume, mirror
  and PTZ. No matching private camera was available on the research account.
- **Transport gap:** current `HTTP` wrapper has GET/POST/DELETE only; these
  settings require additive PUT support.
- **Recommended fix:** hardware HAR first; feature-info gates every entity;
  response ranges drive `NumberEntity`; writes are non-optimistic and refresh
  authoritative state. Mirror/record/PTZ wait for exact enum/action capture.
- **Non-goal:** Wi-Fi provisioning, tariff purchase and firmware update.
- **Plan:** [`features/mobile-app-parity`](../features/mobile-app-parity/README.md).

### A-96. Внешний RTSP после простоя требует предварительного открытия камеры в HA

- **Status:** 🟡 **PARTIALLY RESOLVED** — PATCH-only revision провалила live
  acceptance; preload revision реализована и проходит automated gates в
  `feat/go2rtc-stream-manager`, но повторный production run и merge
  ещё открыты.
- **Severity:** **P1 reliability** для opt-in external RTSP: stable URL
  существует, но после idle не выполняет свой контракт.
- **Area:** `stream_manager.py`, `go2rtc.py:Go2RtcClient`, camera/config-entry
  lifecycle, entity registry eligibility.
- **Symptom (owner report / PR #61):** `eg_<camera_id>` в go2rtc есть,
  но после простоя внешний RTSP отвечает `500/EOF`. Открытие камеры
  в HA минтит fresh operator URL и временно восстанавливает путь.
- **Live failure evidence (2026-07-16):** пять затронутых потоков присутствовали
  в go2rtc, но имели lazy producer (`url` без active metadata) и zero consumers;
  RTSP DESCRIBE возвращал 404/EOF. Живыми остались камеры с фоновым consumer. Canary
  preload против уже протухшего source вернул HTTP 500/TLS EOF.
- **Root cause:** operator source — одноразовая server-side session; PATCH
  менял URL, но не подключал lazy producer. URL истекал до первого внешнего
  consumer, поэтому регистрация stream не означала готовность RTSP.
- **Decision:** [ADR-0014](../decisions/0014-go2rtc-stream-manager.md) —
  сохраняется manager per config entry и PATCH-only source write, но initial
  flow становится `mint → PATCH → preload`. Reconcile сравнивает streams,
  preloads и active producer; cleanup удаляет preload до подсчёта внешних
  consumers. Main/hidden options default false; disabled всегда excluded.
- **Option-off regression and correction (2026-07-16):** replacement manager
  удалял preload, но из-за early return не выполнял stream reconcile. Live
  snapshot показал семь lazy `eg_*` с zero consumers и три active домофона с
  consumer. Итоговый lifecycle возвращает старый контракт: one-shot startup
  cleanup удаляет idle streams, но сохраняет active viewers и не запускает
  фоновые таймеры.
- **Hidden-toggle transient regression (2026-07-16):** при main option on и
  hidden sub-option off go2rtc временно показывал все enabled HA cameras, затем
  reconcile удалял hidden names. При выключении main option происходил такой
  же spike перед cleanup. Лишние operator mint/PATCH увеличивали время
  инициализации integration.
- **Transient root cause and correction:** HA мог вызвать `stream_source()` во
  время platform forwarding, до `_sync_visibility`. Eligibility управляла
  только preload, поэтому refresh безусловно делал mint/PATCH, а policy
  применялась постфактум. ADR-0014 вводит отдельный pre-mint background gate,
  консервативный API-hidden hint до sync и сохраняет persistent user-shown
  override. Setup/background request исключённой hidden camera возвращает
  stable RTSP name для HA Stream lifecycle, но делает zero operator, PATCH и
  preload calls.
- **Hidden HA-open regression and correction (2026-07-16):** первая версия
  gate применяла background policy ко всем refresh reasons. Поэтому явное
  открытие enabled hidden camera в HA возвращало имя отсутствующего go2rtc
  stream и WebRTC падал на RTSP DESCRIBE `404 Not Found`. После manager startup
  `ha_open`, `active_consumer` и `recovery` теперь могут лениво выполнить
  mint/PATCH для любой enabled registry camera. Background-ineligible hidden
  camera не получает preload; reconcile сохраняет её при active viewer и
  удаляет idle registration после ухода viewer. Disabled camera остаётся
  запрещена во всех manager paths.
- **Options-reload churn and latency (2026-07-16):** при изменении main/hidden
  checkbox полный config-entry reload сначала снимал все manager preloads, из-за
  чего producer counts массово падали в zero. Новый manager затем поднимал
  eligible cameras с jitter и только после reconcile удалял excluded streams;
  одновременно без необходимости перезапускались coordinator, platforms,
  history, FCM и SIP.
- **In-place correction:** ADR-0014 оставляет normal reload только для смены
  go2rtc URL/RTSP host/auth или отключения
  go2rtc. Совместимое изменение publication flags применяет текущий manager:
  сохраняет eligible preloads/HA consumers, cleanup-ит excluded из одного
  snapshot и scheduling-ит только newly eligible. Late background mint
  повторно проверяет policy до PATCH/preload; если PATCH уже начался, late
  registration проходит consumer-aware cleanup сразу после ответа и не
  отменяет option-off cleanup.
- **Policy-on latency follow-up (2026-07-16):** после in-place correction
  existing producers больше не обнулялись, но новые sources появлялись по
  одному с заметной задержкой. Причина локальная и детерминированная:
  `async_update_policy()` ошибочно переиспользовал cold-start hash jitter
  `0..60s`. Интерактивный path теперь ставит первую missing camera на `0s`,
  следующие на `0.5s`, `1.0s`, ...; сохранение options не ждёт operator
  mint/PATCH/preload. Cold startup сохраняет полный jitter для burst control.
- **Independent review triage (2026-07-16):** первый review PR #71 сообщил
  семь Important lifecycle/race гипотез без Critical. После проверки с
  владельцем retained только два соразмерных исправления: unload ждёт running
  reconcile и снимает pending preload даже при cancellation ambiguity; entity
  proactive timer пропускает background-eligible streams, чтобы manager preload
  не выдавал себя за external viewer и не синхронизировал все камеры в 28:30
  burst. Per-camera lock/attach lease, main-off polling, removed-camera union и
  joined-reason upgrade отклонены как ненаблюдавшаяся сложность/overhead;
  удаление по одному пропавшему coordinator snapshot дополнительно опасно при
  временно неполном operator response.
- **Startup-grid production finding (2026-07-16):** при открытии трёх enabled
  hidden лифтов во время завершения setup два `ha_open` получили стабильный
  RTSP name без operator mint/PATCH и завершились 404; третий успел создать
  stream, получил upstream EOF и оставил HA-side `Lavf62.3.100` consumer после
  закрытия UI. Причины разделены и закрыты минимально: on-demand допускается до
  `manager.start`, background hidden остаётся gated; proxied recovery больше не
  вызывает `HA Stream.update_source()` с тем же URL и не может пересечься с
  idle stop через HA `_fast_restart_once`.
- **Startup-grid live verification (2026-07-16, `3a3ad02`):** после deployment
  ранние explicit lift-camera opens создают go2rtc streams и воспроизводятся;
  после закрытия HA UI лишний non-preload consumer не остаётся. Long-idle,
  scheduled 28:30 refresh и go2rtc-restart acceptance остаются отдельными
  незакрытыми сценариями.
- **Automated evidence in branch:**
  - `test_config_flow_keep_warm.py` — defaults/dependency/persistence;
  - `test_go2rtc_client.py` / `test_go2rtc_upsert.py` — PATCH-only source,
    dedicated preload API, producer sanitization + no streams PUT;
  - `test_stream_manager.py`, `test_stream_manager_reconcile.py`,
    `test_stream_manager_scheduler.py`, `test_stream_manager_lifecycle.py` —
    mint/PATCH/preload ordering, dedup/policy/cadence/retry, inactive-producer
    re-arm, restart, preload-first cleanup и unload; pre-visibility hidden gate
    доказывает zero background mint/PATCH/preload и сохраняет user-shown
    override; explicit HA-open до и после startup доказывает lazy mint/PATCH
    без preload при выключенной background publication;
    unload interleavings покрывают running reconcile и cancellation во время
    preload request;
    in-place options tests доказывают no reload/preload churn, main on/off,
    short interactive ramp при сохранённом cold-start jitter, transport
    fallback и concurrent late-mint/PATCH guards;
  - `test_sensor_rtsp_urls.py` — preloaded+active+fresh и no-secret attrs;
  - local gates: 131 focused, 151 related regressions, 549 full suite passed.
- **Production acceptance (repeat merge-blocking):** пять затронутых камер
  получают active preload и открываются externally после idle без HA-open;
  active consumer переживает PATCH; go2rtc restart → restore ≤60s;
  disabled/hidden cleanup policy; concurrent reasons → one mint/PATCH/preload;
  policy toggles не reload-ят integration и не обнуляют existing eligible
  producers; option-off удаляет idle registrations, unload снимает background
  consumers.
  Точный checklist —
  [`features/go2rtc-stream-manager/design.md`](../features/go2rtc-stream-manager/design.md).
- **Security boundary:** source URL не хранится в manager state;
  diagnostic RTSP URL без credentials; errors/logs содержат только
  sanitized category/type.
- **Related:** A-71 остаётся production-proven active-consumer
  recovery; A-82 закрывается в ветке; A-83 intentionally deferred;
  A-84 требует live config-persistence evidence.

### A-73. config_flow + `async_migrate_entry` без тестов (Bronze IQS gate)

- **Status:** ✅ **RESOLVED** — merged в master, commit `3a60b15`
  (`tests/test_config_flow.py` — 3 ветки auth + go2rtc + abort/reauth;
  `tests/test_init.py` — миграции v1→2→3). Bronze config-flow gate закрыт.
  (ID ранее жил только в `summary.md` — формализован в audit 2026-07-07.)
- **Severity:** P1 — заявленный `quality_scale: "bronze"` формально **не
  defensible**; регрессии в 3-веточном flow и в миграциях ловятся только руками.
- **Area:** `config_flow.py` (user / contract / sms / password / advanced +
  go2rtc-меню + options), `__init__.py` `async_migrate_entry` v1→2→3.
- **Evidence (по коду):** в `tests/` **нет** `test_config_flow.py` и **нет**
  теста config-entry миграции. Есть только `test_options_flow_clear_creds.py`
  (узкий кусок options-flow) и `test_entity_migration.py` (про entity-registry
  `unique_id`, **не** про `async_migrate_entry`). Исходный scaffold-stub удалён
  (A-07). Детальный план — [`testing/strategy.md`](../testing/strategy.md) §1-3.
- **Impact:** HA Integration Quality Scale Bronze требует config-flow
  test-coverage → без этих тестов Bronze нельзя защитить на review.
- **Recommended fix:** `test_config_flow.py` (happy path всех 3 веток + abort
  `already_configured` / `reauth`) + `test_init.py` (миграции v1→2→3) по
  `testing/strategy.md`.
- **First step:** `test_config_flow` happy path phone+SMS + abort
  `already_configured` (минимальный Bronze-defensible набор).

### A-74. `helpers.py` crypto без golden vectors (тихий breakage auth)

- **Status:** ✅ **RESOLVED** — merged в master, commit `362237b`
  (`tests/test_helpers.py` — golden vectors для hash_password /
  hash_password_timestamp + list-utils). (ID ранее жил только в `summary.md` —
  формализован в audit 2026-07-07.)
- **Severity:** P1 — правка формулы или смена схемы бэкендом молча ломает login,
  CI это не поймает.
- **Area:** `helpers.py` — `hash_password` (SHA1 → base64),
  `hash_password_timestamp` (захардкоженные `prefix="DigitalHomeNTKpassword"` +
  `secret` + MD5 hex).
- **Evidence (по коду):** `test_helpers.py` **не существует**. Функции —
  reverse-engineered формат оператора; порядок конкатенации и prefix/secret
  load-bearing (см. `helpers.py:35-47`).
- **Impact:** нет регрессионного guard на auth-крипту — любой breakage тихий.
- **Recommended fix:** `test_helpers.py` с **golden vectors** (зафиксированные
  пары вход→ожидаемый хеш, снятые с эталона) для обеих hash-функций +
  `find` / `contains` / `dedupe_by_id` / `append_unique`.
- **First step:** снять 2-3 golden-пары для `hash_password` /
  `hash_password_timestamp` и закрепить параметризованным тестом.

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
| ✅ A-56 + ✅ A-57 + ✅ A-61; A-59/A-62 + REST-history remainder A-58 | Итерация 3 (Silver feature gaps) |
| 🟡 A-63 (Won't fix — incompatible с HA Stream lifecycle) + ✅ A-64 (PR #43) + ✅ A-65 (PR #49) + ✅ A-66 (PR #46) | Итерация 3 (Silver — runtime polish из реальных логов 2026-05-26) |
| A-67 (P2 cold-start warmup, TBD) + ✅ A-68 (PR #51 — dedup concurrent stream_source) | Итерация 3 (новые findings из лога 2026-05-27, отдельные PR) |
| ✅ A-71 (long-open video freeze ~30 мин — auto-recovery, ADR-0009) | Итерация 3 (design tradeoff: mirror vs HA-UX) |
| ✅ A-58 + ✅ A-54 (doorbell event via FCM в master, ADR-0011) + 🟡 A-80 (FCM «серая зона» — known risk), A-47 (P3/skip), A-50 | Итерация 4 (real-time event delivery — реализован FCM-канал вызова) |
| ✅ A-81 (register-on-ring ADR-0012 + downlink AudioBridge + call_camera.py, master/PR #69) — закрывает практическую часть A-49 (`sipdevices` используется) | Итерация 4 (two-way audio: приём вызова + downlink-вывод + экран вызова) |
| ✅ A-85 (uplink-микрофон ADR-0013: HA WS-binary #1, дрейф-фикс rtp.py, Lovelace-карта; live-прод 2026-06-24, master/PR #69) — завершает two-way audio (говорить гостю) | Итерация 4 (two-way audio: uplink-микрофон; #2/#3/#4 эмпирически отвергнуты) |
| 🟢 A-82 (resolved-in-branch) + 🔴 A-83 (A-71 triggers intentionally remain in camera) + 🟡 A-84 (PATCH-only source mitigation, live persistence check open) + 🟡 A-96 (preload revision automated, repeat live scenarios open) | external RTSP stream-manager track, ADR-0014; merge blocked by repeat production acceptance |
| ✅ A-73 (config_flow/миграции — тесты, `3a60b15`) + ✅ A-74 (helpers golden vectors, `362237b`) + 🟡 A-21 (ClientTimeout, `3885bb0`; retry — follow-up) | Итерация 3 (test-debt + reliability; closed 2026-07-07) |
| ✅ A-87 (ring/idle watchdog, PR #68) + ✅ A-88 (video anti-churn) + ✅ A-90 (FCM-ended guard), merged PR #69 | Итерация 4 (UI + надёжность видео/жизненного цикла вызова) |
| ✅ A-89 (смена звонящего домофона во время held) + ✅ A-91 (штатная pre-answer SIP-модель подтверждена PCAP), merged PR #69 | Итерация 4 (мульти-вызов + production diagnostics) |
| A-92 (typed diagnostics для HTML service-pipe/VPN block; нужен runtime HAR) | backlog (P2 reliability; не блокирует happy path 9.9.0) |
| A-50 + остаток A-58 + A-59 | mobile-app parity: durable history/archive + Media Source |
| A-93 | mobile-app parity: guest invitation response action (HAR gate) |
| A-94 | mobile-app parity: access keys (enabled-account HAR gate) |
| A-95 | mobile-app parity: private-camera settings (hardware HAR gate) |
| A-27..A-36, A-39..A-41, A-53 | по мере touch / документирование |
| A-42, A-46 | информация (не задача) |

## Next reading

- For security details: `security.md`
- For testing: `testing/strategy.md`
- For HA-compat: `ha-compatibility.md`
- For implementation order: `roadmap.md`
- For gate criteria: `quality-gates.md`
