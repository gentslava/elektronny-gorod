Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-07-16 (external RTSP stream-manager implementation and
live acceptance gate added; A-82/A-84 status reconciled)

Source files:
- `audit/project-audit.md` (источник find-ов)
- `audit/security.md`
- `architecture/quality-scale.md`

Related docs:
- `audit/project-audit.md`
- `architecture/quality-scale.md`
- `testing/strategy.md`
- `aidd/quality-gates.md`

Used by agents:
- Lead Architect, разработчик, Validator

Quality gates:
- PLAN_APPROVED

---

# Roadmap — план на 3 итерации

Каждая задача в roadmap **ссылается на находку из аудита**. Без evidence — не roadmap, а вишлист.

## Итерация 1 — Hotfix P0 + AIDD MVP (≈ 1-2 дня)

**Цель:** убрать утечки токенов из логов, исправить тихий баг, заложить AIDD-документацию.

**Acceptance:** quality gate `SECURITY_OK` для P0 закрыт; `AUDIT_DONE` зелёный; AIDD-структура существует и связана.

### Tasks

- [ ] **A-01** Удалить `LOGGER.debug("Access token is %s", self.access_token)` — [`config_flow.py:77`](../custom_components/elektronny_gorod/config_flow.py#L77).
- [ ] **A-02** В [`http.py:11-13`](../custom_components/elektronny_gorod/http.py#L11-L13) создать `_redact_headers()` и не логировать `data` для auth endpoints.
- [ ] **A-03** В [`http.py:22-25`](../custom_components/elektronny_gorod/http.py#L22-L25) ввести redaction body для auth-paths.
- [ ] **A-04** Заменить `entry.data` → `entry.entry_id` в [`config_flow.py:283, 291`](../custom_components/elektronny_gorod/config_flow.py#L283).
- [ ] **A-05** Перевести [`http.py`](../custom_components/elektronny_gorod/http.py) на `async_get_clientsession(hass)`; прокинуть `hass` через `ElektronnyGorodAPI` и `ElektronnyGorodUpdateCoordinator`.
- [ ] **A-06** Исправить `c.get("ID")` → `c.get("id")` в [`coordinator.py:182`](../custom_components/elektronny_gorod/coordinator.py#L182).
- [ ] **A-07** Удалить `tests/test_config_flow.py` (или пометить `@pytest.mark.skip("rewrite per docs/testing/strategy.md")`).
- [ ] **A-43** Поднять `import base64` в top of file в [`camera.py`](../custom_components/elektronny_gorod/camera.py); рассмотреть `aiohttp.BasicAuth`.
- [ ] **A-45** Добавить `go2rtc_username`/`go2rtc_password` в `TO_REDACT` (создаётся вместе с `diagnostics.py` в Итерации 2; в Итерации 1 — минимум зафиксировать в S-16 + не логировать).
- [ ] **AIDD-1** Full AIDD заложен (сделано в текущем цикле работы).
- [ ] **ADR-0001** записать «принятие AIDD».
- [ ] **Release** hotfix (patch-релиз) с changelog `security: redact tokens in logs`.

**Quality gates passed:** `SECURITY_OK` (P0 cleared), `AUDIT_DONE`, `DOCS_UPDATED`.

## Итерация 2 — Bronze quality scale ✅ COMPLETED

**Цель:** довести интеграцию до Bronze. См. [`architecture/quality-scale.md#bronze`](architecture/quality-scale.md).

**Статус:** Bronze IQS shipped. Все обязательные критерии Bronze закрыты;
pytest CI matrix также работает на минимальной и текущей HA-версиях.

**Acceptance — met:**
- `manifest.json` содержит `quality_scale: "bronze"` и `integration_type: "hub"` ✓ (A-34);
- entity имеют `_attr_has_entity_name = True` и стабильный `unique_id` ✓ (A-12, A-13);
- coordinator имеет `update_interval` и обновляет данные ✓ (A-08, A-09);
- `pytest tests/` зелёный локально (411 tests pass) ✓;
- CI workflow `.github/workflows/python-tests.yaml` создан и зелёный ✓.

### Tasks (closed)

- [x] **A-08** ✅ — `update_interval=timedelta(minutes=5)` + `_async_update_data` возвращает dict.
- [x] **A-09** ✅ — Sensor / Lock / Camera переведены на `CoordinatorEntity` + `_handle_coordinator_update`. Старые `async_update` удалены.
- [x] **A-12** ✅ — stable `unique_id` Camera/Lock + миграция legacy через `entity_registry.async_migrate_entries`.
- [x] **A-13** ✅ — `_attr_has_entity_name = True` + `_attr_translation_key="balance"` (sensor); Camera/Lock — имя в `device_info.name`. Раздел `entity` добавлен в `strings.json` + переводы.
- [x] **A-14** ✅ — Sensor баланса: `device_class=MONETARY`, `state_class=TOTAL`, `unit="RUB"` (ISO 4217; константа `CURRENCY_RUBLE` удалена из `homeassistant.const` в свежих HA).
- [x] **A-16** ✅ — `coordinator.async_unsubscribe()` зарегистрирован через `entry.async_on_unload` в `async_setup_entry`.
- [x] **A-17** ✅ — `_collect_cameras_for_place` + `_collect_locks_for_place` helpers извлечены. (Оставшийся duplicate fan-out на per-place уровне — см. A-61.)
- [x] **A-18** ✅ — `query_sections` удалён из coordinator.
- [x] **A-34** ✅ — `quality_scale: "bronze"`, `integration_type: "hub"` в `manifest.json`.
- [x] **A-44** ✅ — `async_update` камеры удалён вместе с переходом на `CoordinatorEntity` (stream URL лениво в `stream_source()`).
- [x] **Tests baseline** ✅ — `tests/test_logging_redact.py`, `tests/test_http.py`, `tests/test_entity_migration.py`, `tests/test_visibility.py`, `tests/test_visibility_real.py` + `conftest.py` фикс + `pytest.ini`. Локально 67 tests pass.
- [x] **PR #35 extras** ✅ — Visibility sync через `hidden_by` ↔ `/settings/screens` + one-time migration `visibility_migration_v2` (см. A-60). Bearer-omission на pre-auth endpoints (см. A-22 partial).

### Tasks (deferred → Итерация 3)

- [x] **A-10** ✅ Реальный polling включён (`update_interval=5 min`),
  `iot_class: cloud_polling` соответствует поведению; ADR-0003.
- [x] **A-11** ✅ Поднят `hacs.json:homeassistant` до `2024.10.4` — первая stable HA с `LockState` enum, который импортирует `lock.py`. Та же версия пинится как min в CI matrix (см. python-tests.yaml).
- [x] **A-12** ✅ slice 3c — stable `unique_id` Camera/Lock + миграция legacy через `entity_registry.async_migrate_entries`.
- [x] **A-13** ✅ slice 3c — `_attr_has_entity_name = True` + `_attr_translation_key="balance"` (sensor); Camera/Lock — имя в `device_info.name`. Раздел `entity` добавлен в `strings.json` + переводы.
- [x] **A-14** ✅ slice 3c — Sensor баланса: `device_class=MONETARY`, `state_class=TOTAL`, `unit="RUB"`.
- [x] **A-16** ✅ slice 3a — `coordinator.async_unsubscribe()` зарегистрирован через `entry.async_on_unload` в `async_setup_entry`.
- [x] **A-17** ✅ Извлечены `_collect_cameras_for_place` / `_collect_locks_for_place`.
- [x] **A-18** ✅ Неиспользуемый `query_sections` удалён из coordinator.
- [ ] **A-19** Сузить `except Exception` в `api.py` до `ClientResponseError`/`ClientError`/`asyncio.TimeoutError`; не использовать `e.args[0]`.
- [ ] **A-20** Заменить `raise ClientError(response)` на корректное `ClientResponseError`.
- [ ] **A-21** 🟡 Timeout закрыт (REST 30с / binary 60с / connect 10с);
  остаётся retry/backoff только для идемпотентных GET.
- [x] **A-23 + A-45** ✅ `diagnostics.py` redacts secrets/PII;
  `TO_REDACT` покрывает `SENSITIVE_KEYS`, включая go2rtc credentials.
- [x] **A-44** ✅ Legacy `async_update` камеры удалён при переходе на CoordinatorEntity.
- [x] **Tests-1..N** ✅ Реальные config-flow/init/migration/coordinator/API/SIP/
  frontend тесты добавлены; release-candidate suite — 392 backend + 48 frontend.
- [x] **CI-1** ✅ Создан `.github/workflows/python-tests.yaml` с matrix по двум HA-версиям (min 2024.10.4 + current 2026.5.4), pip-cache и coverage artifact.
- [x] **A-34** ✅ slice 3c — `quality_scale: "bronze"`, `integration_type: "hub"` в `manifest.json`.
- [x] **A-35** ✅ `CHANGELOG.md` ведётся и подготовлен к 4.0.0.
- [ ] **A-36** Создать `CONTRIBUTING.md` со ссылкой на `aidd/contributing.md`.
- [x] **A-27..A-29** ✅ README links/install path и badge минимальной HA синхронизированы.
- [x] **ADR-0002** ✅ CoordinatorEntity + update_interval — `accepted`.
- [ ] **ADR-0004** «token redaction strategy» — proposed, требуется promote → accepted.

**Quality gates achieved:** `SECURITY_OK`, `REVIEW_OK`, `DOCS_UPDATED`. Integration Quality Scale: **Bronze**. `TESTS_PASS` — локально зелёный, CI follow-up в Итерации 3.

## Итерация 3 — Silver + Full AIDD (≈ 5-7 дней)

**Цель:** Silver Quality Scale + расширенная агентская инфраструктура + закрытие feature gaps, открытых HAR-research циклом.

**Acceptance:**
- Silver criteria по [`architecture/quality-scale.md#silver`](architecture/quality-scale.md);
- coverage ≥ 80% по модулям;
- agent-skills hooks работают.

### Tasks

#### HA features

- [ ] **A-15** Решить судьбу `fake_timer_lock` в `lock.py` — либо удалить, либо переписать `lock` → `button`. Требует ADR-0005.
- [ ] **A-22** (остаток) Поведение при 401: pre-auth Bearer-omission уже сделан (PR #35); осталось — собрать HAR со сценарием истечения access_token, затем реализовать `/auth/.../refresh` **точно как в приложении** (см. [ADR-0006](decisions/0006-mirror-app-behavior.md)). До получения HAR — текущее graceful поведение (UpdateFailed → reauth через UI).
- [ ] **A-25** Native reauth flow (`async_step_reauth_confirm`).
- [ ] **A-26** Reconfigure flow (`async_step_reconfigure`).
- [ ] **A-37** `parallel_updates = 1` (или другое значение) на entity-классах.
- [ ] **A-38** Обработка unavailable / log-when-unavailable.
- [ ] Repairs flow для edge-cases (заблокированный аккаунт, истёкший договор).

#### Silver feature gaps (HAR-research findings)

- [x] **A-56** ✅ DND switches: master + 2 dependent через `/settings/do_not_disturb` (`switch.py`, PR #38).
- [x] **A-57** ✅ Finance: account-blocked + days-to-block entities; payment amount/date/link remain safe balance attributes (PR #39; browser navigation is not a HA Button use-case).
- [x] **A-58 realtime** ✅ Doorbell event delivery implemented through FCM (ADR-0011); REST polling is not the realtime source.
- [x] **A-58 history remainder** ✅ Реализовано в `feat/durable-event-history`: page-0 silent baseline per source, bounded ID dedup across restart, config-entry-scoped dispatch и отдельный unload-safe poll lifecycle.
- [ ] **A-59** Video retention helper — `is_within_retention(camera_type, ts)`, проверка перед video URL request. Закрывает ложные 500 для лифт/публичных камер.
- [x] **A-61** ✅ Двойной HTTP устранён: `screens` + `access_controls` prefetch per place (commit `71eb4dd`).
- [ ] **A-62** FAVORITES section в `_extract_hidden_ids` — расширить парсинг с учётом mixed-typed items. Fallback OK, не блокер.

#### Mobile app parity 9.9.0

Единый PRD/research/plan/tasklist:
[`features/mobile-app-parity/`](features/mobile-app-parity/README.md).
Static-only write paths не переходят в код без decrypted HAR (ADR-0006).

- [x] **A-50 + A-58 remainder** ✅ Access-call и verified camera-motion events
  реализованы в `feat/durable-event-history` с baseline/dedup и PII-safe DTO;
  camera-motion polling начинается только после включения entity.
- [ ] **A-59 / Slice 2** Archive Media Source, retention mapping и on-demand
  signed URL resolution.
- [ ] **A-93** Guest invitation: NTK `app=2`, response-only admin action; live
  link never persists. Sanitized success/401 fixtures captured; implementation
  waits only for Slice 3 approval and admin/security review.
- [ ] **A-94** Access keys: read-only inventory first, notification switch only
  after enabled-account HAR; key code is never HA state/ID.
- [ ] **A-95** Private-camera settings: feature-gated sensitivity/volume first;
  record/mirror/PTZ after hardware HAR confirms enums/actions.

#### Production-log polish (A-63..A-66 — отдельные PR)

> Findings собраны из production-лога (см. audit §A-63..A-66).

- [x] ~~**A-63**~~ → **Won't fix** (PR #46 final). Оригинальная идея skip
  `stream_source()` для hidden cameras фундаментально несовместима с HA
  Stream lifecycle. Эксперимент в 3 PR (#44 X / #45 Y / #46 Z) подтвердил.
  Skip оставлен только в `async_camera_image` (snapshot). Лишние HTTP к
  operator приемлемы (поведение 3.1.0, без rate-limit). См. audit A-63.
- [x] **A-64** ✅ Reload cascade + user override (PR #43). Migration flag
  в `entry.data`, sync через `entity.options[DOMAIN]` track per-entity
  user_shown override.
- [x] **A-66** ✅ Historical HA Stream stale-source recovery (PR #46),
  позже расширено A-71. В stream-manager ветке camera больше не
  владеет write boundary; recovery делегирует PATCH-only manager'у.
- [x] **A-65** ✅ Log throttling от broken cameras (PR #49). Per-entity
  `_consecutive_empty_count` counter в `ElektronnyGorodCamera`. 1й fail
  → WARNING, 2й+ подряд → DEBUG. Counter сбрасывается на первый success.

#### Production-log polish (2026-05-27 — новые findings)

> Логи 2026-05-27 показали 2 новых проблемы после deployment A-64/A-66.

- [x] **A-68** ✅ **P2 defensive** Concurrent `stream_source()` dedup
  (PR #51). In-flight future-pattern в `Camera.stream_source` — concurrent
  callers wait first future вместо параллельного fetch. N concurrent
  callers → 1 HTTP + 1 PUT + 1 `Stream.update_source()` restart. **Scope
  clarification**: defensive cleanup для concurrent-thrash (Frigate /
  WebRTC probe / Lovelace card в параллель). **Не фикс** «мигание видео
  после cold start» — у него отдельный root cause (production-тест
  2026-05-27 подтвердил: с A-68 мигание остаётся). Investigation
  flicker'а перенесена в отдельный track (требует browser-side runtime
  diagnostic: Network m3u8/m4s + Console MediaSource events).
- [ ] **A-67** P2 Cold-start go2rtc warmup — **attempted, didn't help**.
  Эксперимент в 3 итерациях (A-67 PUT-only pre-warm / A-71 active probe
  via `/api/frame.jpeg` / A-72 `/api/preload` через go2rtc-research): все
  проверены runtime'ом на production-сервере, ни один не убрал видимое
  мигание видео. Hypothesis «ffmpeg cold-start race» оказалась неверной
  (нужна другая diagnostic-сессия). Закрыт без PR'а.

#### External RTSP after idle (A-82/A-84/A-96, ADR-0014)

- [x] **Revised automated implementation** — live run опроверг PATCH-only
  registration: пять lazy streams возвращали 404/EOF. Per-entry manager теперь
  выполняет initial mint→PATCH→preload, сохраняет non-disruptive 28:30 PATCH,
  проверяет stream/preload/active producer раз в минуту, снимает preload перед
  consumer-aware cleanup; option-off startup удаляет preload и idle stream,
  сохраняя active viewer. Diagnostic sensor требует
  preloaded+active+fresh; source writes остаются PATCH-only.
- [x] **Hidden publication pre-mint gate** — live options reload показал
  transient hidden names и более долгую initialization: setup-time
  `stream_source()` успевал сделать operator mint/PATCH до visibility sync.
  Background-excluded hidden cameras теперь делают zero mint/PATCH/preload;
  API-hidden startup hint не перекрывает persistent user-shown override.
  Explicit HA-open enabled hidden camera во время или после startup лениво
  делает mint/PATCH без preload и работает на время активного viewer.
- [x] **Policy update without producer churn** — publication checkboxes больше
  не вызывают full config-entry reload. Existing eligible preloads и HA
  consumers сохраняются; excluded cleanup и newly eligible scheduling делает
  текущий manager. Live follow-up убрал ошибочный cold-start jitter из ручного
  включения: первая missing camera запускается сразу, следующие через 0.5s;
  transport/auth changes сохраняют normal reload fallback.
- [x] **Independent review lifecycle triage** — stop ждёт running reconcile и
  снимает pending preload после cancellation ambiguity; entity proactive timer
  не превращает preload consumers в синхронный 28:30 burst. Теоретические
  per-camera locks/attach lease/main-off polling/removed-snapshot cleanup не
  приняты без production evidence и дополнительной фоновой сети.
- [x] **Startup-grid production follow-up** — live на `3a3ad02`: explicit
  hidden HA-open во время setup выполняет mint/PATCH вместо возврата
  незарегистрированного RTSP name; background gate сохранён. Proxied EOF recovery больше не вызывает
  `Stream.update_source()` с тем же URL и не оставляет worker через
  fast-restart/idle-stop race.
- [x] **A-82** 🟢 resolved-in-branch: `camera.py` больше не владеет
  go2rtc HTTP transport/writes; merge reconciliation открыт.
- [ ] **A-84** 🟡 PATCH-only mitigation готова; после live cycles
  проверить, что repeated PATCH не раздувает persistent go2rtc YAML.
- [ ] **A-96 repeat production acceptance (merge gate)** — пять проблемных
  streams получают active preload и переживают idle без HA-open; active
  consumer переживает refresh; restart restore ≤60s; disabled/hidden cleanup;
  concurrent reasons dedup; option-off удаляет idle registrations, unload
  снимает background consumers; main/hidden toggle не reload-ит integration,
  не обнуляет existing eligible producers и никогда даже кратковременно не
  добавляет excluded hidden names фоновым path; explicit hidden HA-open во
  время и после setup работает без persistent preload и cleanup-ится после
  viewer; закрытие HA UI не оставляет orphan consumer после EOF recovery.
- [ ] После девяти live scenarios записать evidence в существующем feature
  design, merge replacement branch и только потом close/supersede PR #61.

#### Code quality

- [ ] **A-30** `extra_state_attributes` — snake_case ключи.
- [ ] **A-31** UTC в `time.py`.
- [ ] **A-32** Заменить f-string в `LOGGER.*` на `%`-форматирование во всех местах.
- [ ] **A-33** Magic strings → const.
- [ ] **A-39** Избавиться от reinvented `find/contains/append_unique` в helpers.
- [ ] **A-40** Удалить мёртвый `ANDROID_DEVICES_CSV` или включить.

#### AIDD Full

- [ ] Создать `.claude/agents/` (3 роли: HA-expert, security, QA).
- [ ] Создать `.claude/commands/` (audit, test-config-flow, release-check).
- [ ] Создать `.claude/rules/` (no-secret-logs, coordinator-pattern, test-coverage).
- [ ] Создать `.claude/hooks/pre-commit-redaction-check.sh`.
- [ ] Создать `docs/decisions/` (ADR-0001..0004).
- [ ] Создать `docs/features/<feature-id>/` templates.
- [ ] Создать `docs/aidd/mcp-tools.md` — карта инструментов и permissions.
- [ ] Создать `docs/aidd/prompts.md` — prompt library.

#### Гэпы с приложением (на основе первого HAR-разбора)

- [ ] **A-48** Snapshot домофона: `GET /rest/v1/places/{p}/accesscontrols/{ac}/snapshots` — добавить отдельный snapshot для домофонов (не только для камер).
- [ ] **A-51** Bootstrap config: `POST .../device-installations` — динамические URLs вместо hardcoded `BASE_API_URL`.
- [ ] **A-52** Header `traceparent` — генерировать per-request для соответствия паттерну приложения.

**Quality gates passed:** `READY_FOR_RELEASE` + Silver IQS.

## Итерация 4 — Real-time events ✅ doorbell-вызов реализован (FCM)

**Результат research-фазы:** канал доставки события «вызов с домофона»
определён **экспериментально** (`research/intercom-call-probe/FINDINGS.md` —
live-проверка 3 каналов на прод-аккаунте) — это **FCM data-push**. Решение
зафиксировано в **[ADR-0011](decisions/0011-doorbell-fcm-channel.md)** (заменил
гипотетический ADR-0009-event-delivery для этого use-case). Реализовано:
`event`-сущность `EventDeviceClass.DOORBELL` + `fcm.py` (`DoorbellFcmListener`)
+ push-регистрация в `api.py` (см. [audit A-54 / A-58](audit/project-audit.md),
реализация находится в master). Известный риск «серой зоны»
приватных API Google — [A-80](audit/project-audit.md), под graceful degradation.

**Принцип:** строго следуем [ADR-0006](decisions/0006-mirror-app-behavior.md)
— никаких выводов без HAR/APK evidence. Канал вызова доказан экспериментом.

**Двусторонний звук (разговор по домофону)** — ✅ реализован: приём + downlink
(A-81, ADR-0012) + uplink-микрофон (A-85, ADR-0013, HA WS-binary #1, live-прод
2026-06-24). Реализация находится в master после PR #69. PRD —
`research/intercom-call-probe/PRD-two-way-audio.md`.

### Что НЕ решено (открытые research-вопросы)

**Real push** через FCM не отброшен — требует исследования:

- **`google-services.json`** внутри APK содержит Firebase config
  (`project_id`, `app_id`, `api_key`, `sender_id`). Декомпиляция APK
  (apktool/jadx) — стандартная процедура, не требует обфускации-bypass.
- **Mimicry**: технически возможно зарегистрировать HA-instance как
  «FCM client» приложения «Мой Дом», получая push **напрямую**.
  Реализация: Python библиотеки типа `firebase_messaging` / `aiohttp`
  + STOMP-emulation Google CCS protocol. Существуют open-source
  imp'ы для подобных задач (например, Eufy, Olarm, и другие
  HACS-интеграции делают именно так).
- **HA Companion bridge**: HA Companion уже регистрирует FCM-token,
  но в **другом** Firebase project (HA-вшем). Backend оператора шлёт
  push в **свой** project → routing невозможен без mimicry.
- **Sub-second latency** — если research подтвердит технически
  возможным — это **существенно** лучше polling (15-30s).

### Research tasks — ✅ выполнены экспериментом `intercom-call-probe`

- [x] **R-1 APK Firebase config extraction**: публичный Firebase-конфиг
  приложения извлечён (project / app_id / sender / api_key / package —
  значения в [`const.py`](../custom_components/elektronny_gorod/const.py) `FCM_*`).
  Это **не секреты** (одинаковы у всех пользователей, защита — package + SHA-1
  restriction) → лежат в `const.py`, как `BASE_API_URL` (см. ADR-0011 §Decision).
- [x] **R-2 FCM mimicry feasibility**: подтверждено рабочим — `firebase-messaging`
  (checkin → register → MTalk-сокет) принимает push **без Android-устройства**.
- [x] **R-3 Test push delivery**: на прод-аккаунте — 3 реальных звонка приняты
  без сбоев, payload `CALL_INCOMING` / `CALL_END_ANSWERED_MOBILE` (sub-second).
- [x] **R-4 Legal review**: «серая зона» (приватные API Google + ToS) —
  принято как known risk с graceful degradation (A-80, ADR-0011 §Consequences).
- [x] **R-5 Backup plan (polling)**: `/rest/v1/events/search` остаётся
  возможным fallback/backfill, но для realtime-вызова **не нужен** — FCM
  sub-second лучше polling 15-30s.

### Реализовано

- [x] **ADR-0011** — Realtime-канал события вызова: приём FCM in-HA (accepted).
- [x] **A-58 / A-54** — `event`-сущность + `fcm.py` + push-регистрация в master.
- [x] **A-50** ✅ Camera motion event-stream реализован в
  `feat/durable-event-history` как disabled-by-default entity; archive playback
  остаётся Slice 2.

### Реализовано в master (A-81, ADR-0012)

- [x] **A-81 приём вызова по SIP** — `sip/` пакет (14 модулей), сервисы `answer`/`hangup`,
  модель **register-on-ring** (ADR-0012): mint → REGISTER → held-INVITE → 100 Trying →
  по «Ответить» `200 OK` → RTP-latching. Сброс с панели → SIP `CANCEL` → мгновенный dismiss.
- [x] **Downlink-аудио (слышать гостя)** — `sip/bridge.py` `AudioBridge`:
  G.711-кадры → ffmpeg → mpegts/aac → HTTP-сервер → go2rtc → HA-native WebRTC.
- [x] **Показ экрана вызова** — `call_camera.py` `ElektronnyGorodCallCamera`:
  camera-сущность `camera.intercom_call` с видео домофона + звуком гостя инлайн через
  HA-native WebRTC (4G ok, go2rtc в LAN). `stream_source()` собирает свежий `eg_intercom_call`.

### Реализовано в master (A-85 — uplink-микрофон, ADR-0013)

- [x] **A-85 Uplink (микрофон → домофон)** — механизм **#1 (HA WebSocket binary-audio,
  ADR-0013)**: своя Lovelace-карта `getUserMedia` → Int16 PCM по авторизованному
  HA-WebSocket (`elektronny_gorod/intercom_uplink`) → `DoorbellCallController.feed_uplink`
  → `UplinkSink` (resample 8к → G.711) → `SipManager.uplink_provider` →
  дрейф-компенсированный RTP-uplink в домофон. **Без go2rtc/TURN/новых зависимостей**
  (`audioop-lts` уже есть). Дрейф-фикс `sip/rtp.py:run_uplink` (наивный
  `asyncio.sleep(0.02)` копил ~12% дрейфа → drop-кадры). **Live-прод 2026-06-24**
  (микрофон браузера дошёл до домофона). Файлы: `uplink_ws.py`, `sip/uplink.py`,
  `www/eg-intercom-mic-card.js`.
- [x] **Варианты #2/#3/#4 эмпирически отвергнуты** (не догадки): #2 go2rtc WHIP-pull
  (нужен стрим-таргет/yaml + TURN на 4G), #3 go2rtc exec-backchannel
  (`exec:#backchannel=1` заблокирован через REST на Frigate-go2rtc + upstream-баги +
  TURN), #4 aiortc (конфликт `av<17` vs HA `av==17.0.1`, нет колёс armv7l).
  Подробности — [ADR-0013](decisions/0013-uplink-mic-transport.md) + research
  FINDINGS §D-audio-variants.

### Экран вызова: UI + видео-надёжность + мульти-вызов (PR #68 + PR #69 merged)

- [x] **feat/intercom-call-ui (merged PR #68):** карточка `eg-intercom-call-card`
  (UI + i18n ru/en по `hass.locale.language`), mic-фикс (auto-start every call +
  разный текст баннера), call-camera fixes — снапшот + `available`-only-during-call
  (2a), не отдавать мёртвый URL (2b), state-write на смену фазы (регресс 2a),
  cross-call guard (чужой `ended` не рвёт активный вызов), anti-delay warm-up стрима
  на answer, ring/idle watchdog (A-87). Три исходных UI-замечания закрыты (слайдер /
  микрофон / видео рендерится).

- [x] **Фаза A — видео anti-churn ([A-88](audit/project-audit.md), merged PR #69).**
  Видео вызова = copy с общей forpost-камеры
  (SIP несёт только аудио); при нескольких клиентах (ноут+телефон, ringing+вызов)
  пересборка одноразового operator-URL рвёт общий продюсер → у части клиентов
  видео пусто + задержка + вечные 404 после звонка. Фикс: сборка стрима **один
  раз на звонок**, все клиенты делят один продюсер, только PATCH (не PUT),
  teardown стрима+worker на завершении. Осталась эксплуатационная проверка двумя клиентами.
- [x] **Фаза B — мульти-вызов ([A-89](audit/project-audit.md), merged PR #69).**
  Смена **звонящего домофона**: новый `ring` во время held (не
  answered) снимает старый held и переключается на новый (не одновременные
  разговоры). Различать holding vs in_call в ring-guard.

### Будущие фичи (вне scope v1)

- [ ] **Slice 2b (uplink polish)** — явная `stop`-команда (slot-leak handler при
  многократном toggle, S-UP-02), hands-free (непрерывный поток, джиттер-буфер,
  UX mic-toggle).
- [ ] **Дом.ру-вариант** события вызова — Huawei Push / HMS (другой канал).

### Не блокирующие основной scope

- **A-47** STOMP — остаётся **P3 / skip**. Backend feature-flag null для
  ЭГ абонентов. Реализация только если backend когда-нибудь включит
  STOMP для нашей аудитории — пересмотр.
- **A-49** SIP — остаётся **P3 future**. Только для full intercom-call
  feature (RTP audio в HA) — отдельная итерация.

### Ожидаемые исходы research

| Outcome | Latency | Сложность реализации | Зависимости |
|---|---|---|---|
| FCM mimicry работает | sub-second | средне-высоко | Python firebase lib, APK config |
| FCM mimicry не работает | — | — | fallback → polling |
| Polling-only | 15-30s | низко | aiohttp (уже есть) |

**Quality gates passed (итерация):** `READY_FOR_RELEASE` + Silver IQS +
working real-time event entity (path TBD после ADR).

## Принципы

1. **Не «улучшать всё сразу».** Один PR — одна задача с конкретным acceptance.
2. **Каждая задача ссылается на находку.** Если не можешь найти A-NN в [`audit/project-audit.md`](audit/project-audit.md) — задача не готова к работе.
3. **ADR — для решений, которые сложно откатить.** Не для каждого фикса.
4. **Test-first** для нового кода. Реальные тесты, не stub-ы.
5. **Security gate всегда обязателен** для diff, который трогает `http.py`, `config_flow.py:logging`, `helpers.py`.

## Зависимости между задачами

```text
A-05 (shared ClientSession)
  └── требует hass прокинут через API/coordinator
       └── A-08 (update_interval) и A-09 (CoordinatorEntity) станут проще

A-09 (CoordinatorEntity)
  └── требует A-08 (update_interval) — иначе entity не получают тиков

A-22 (auto-refresh)
  └── требует A-05 (shared session) и A-19 (узкие exceptions)

A-25 (native reauth) и A-26 (reconfigure)
  └── требуют пересборку config_flow.py — параллельно не делать с A-08

Tests
  └── требуют A-07 (удаление stub) до начала
```

## Sequence: ADR хронология

| ADR # | Тема | Когда |
|---|---|---|
| 0001 | Принятие AIDD MVP | конец Итерации 1 |
| 0002 | Переход на CoordinatorEntity + update_interval | начало Итерации 2 |
| 0003 | Стратегия `iot_class` и polling | начало Итерации 2 |
| 0004 | Token redaction strategy | начало Итерации 1 (post-factum для уже сделанных правок) |
| 0005 | Lock vs Button для домофона | Итерация 3 |
| 0006 | Mirror application behavior | accepted |
| 0007 | Stateful emulator baseline | accepted |
| 0008 | Shared aiohttp ClientSession | Итерация 2 |
| 0009 | Camera stream auto-recovery (operator session TTL) | accepted (3.3.0) |
| 0010 | AIDD state-management + reconciliation findings↔git | accepted (3.3.0) |
| 0011 | Realtime-канал события вызова: приём FCM in-HA | accepted (Итерация 4) |
| 0012 | Register-on-ring (held-short-window) для приёма вызова | accepted (feat/intercom-two-way-audio) |
| 0013 | Транспорт uplink-микрофона — HA WebSocket binary-audio (#1) | accepted (feat/intercom-uplink-mic) |

## Risks

| Риск | Mitigation |
|---|---|
| Серверное API оператора может молча сломаться | golden vectors в test_helpers; smoke-тест на dev-машине |
| `pytest-homeassistant-custom-component` несовместим с min HA | matrix в python-tests.yaml |
| Breaking changes в config-flow ломают существующие entries | миграции; reauth-flow покрывает большинство кейсов |
| Lock → Button breaking change | оставить старый lock.py через несколько релизов как deprecated |

## Next reading

- For findings: `audit/project-audit.md`
- For security details: `audit/security.md`
- For QS targets: `architecture/quality-scale.md`
- For test plan: `testing/strategy.md`
- For workflow: `../workflow.md`
- For gates: `aidd/quality-gates.md`
