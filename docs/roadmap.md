Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-25

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
осталась одна follow-up задача — CI workflow для pytest (Tests-1).

**Acceptance — met:**
- `manifest.json` содержит `quality_scale: "bronze"` и `integration_type: "hub"` ✓ (A-34);
- entity имеют `_attr_has_entity_name = True` и стабильный `unique_id` ✓ (A-12, A-13);
- coordinator имеет `update_interval` и обновляет данные ✓ (A-08, A-09);
- `pytest tests/` зелёный локально (67 tests pass) ✓ — CI workflow `.github/workflows/python-tests.yaml`
  всё ещё **не создан**, это Tests-1 follow-up (см. A-24).

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

- [ ] **A-10** Решить `iot_class`: либо включён реальный polling — оставить `cloud_polling`; либо сменить класс. Зафиксировать в ADR-0003.
- [x] **A-11** ✅ Поднят `hacs.json:homeassistant` до `2024.10.4` — первая stable HA с `LockState` enum, который импортирует `lock.py`. Та же версия пинится как min в CI matrix (см. python-tests.yaml).
- [x] **A-12** ✅ slice 3c — stable `unique_id` Camera/Lock + миграция legacy через `entity_registry.async_migrate_entries`.
- [x] **A-13** ✅ slice 3c — `_attr_has_entity_name = True` + `_attr_translation_key="balance"` (sensor); Camera/Lock — имя в `device_info.name`. Раздел `entity` добавлен в `strings.json` + переводы.
- [x] **A-14** ✅ slice 3c — Sensor баланса: `device_class=MONETARY`, `state_class=TOTAL`, `unit=CURRENCY_RUBLE`.
- [x] **A-16** ✅ slice 3a — `coordinator.async_unsubscribe()` зарегистрирован через `entry.async_on_unload` в `async_setup_entry`.
- [ ] **A-17** Извлечь дубликат логики в `_collect_cameras_for_place(place_id)`.
- [ ] **A-18** Удалить или использовать `available_sections`.
- [ ] **A-19** Сузить `except Exception` в `api.py` до `ClientResponseError`/`ClientError`/`asyncio.TimeoutError`; не использовать `e.args[0]`.
- [ ] **A-20** Заменить `raise ClientError(response)` на корректное `ClientResponseError`.
- [ ] **A-21** Добавить `ClientTimeout(total=30)` в HTTP; реализовать простой retry/backoff для 5xx / connection errors.
- [ ] **A-23 + A-45** Создать `diagnostics.py` с redaction (см. [`audit/security.md#S-08`](audit/security.md), [`S-16`](audit/security.md)). В `TO_REDACT` включить также `go2rtc_username`/`go2rtc_password`.
- [ ] **A-44** Убрать дублирующий `get_camera_stream` в `async_update` камеры (закрывается через A-09 CoordinatorEntity).
- [ ] **Tests-1..N** Написать реальные тесты по плану [`testing/strategy.md`](testing/strategy.md): config_flow happy + abort, options_flow, миграции, coordinator, api.
- [x] **CI-1** ✅ Создан `.github/workflows/python-tests.yaml` с matrix по двум HA-версиям (min 2024.10.4 + current 2026.5.4), pip-cache, coverage artifact. Tests-1..N расширят покрытие — см. ниже.
- [x] **A-34** ✅ slice 3c — `quality_scale: "bronze"`, `integration_type: "hub"` в `manifest.json`.
- [ ] **A-35** Создать `CHANGELOG.md`.
- [ ] **A-36** Создать `CONTRIBUTING.md` со ссылкой на `aidd/contributing.md`.
- [ ] **A-27..A-29** Поправить README (битая ссылка, `electronic_city → elektronny_gorod`, badge HA-версии).
- [ ] **ADR-0002** «coordinator pattern: переход на CoordinatorEntity + update_interval» — proposed, требуется promote → accepted.
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

- [ ] **A-56** DND switches (3 entity per place: master + 2 dependent через `/settings/do_not_disturb`). Новая платформа `switch`.
- [ ] **A-57** Sensor balance — extra entities из `/finance` response (binary_sensor.balance_blocked, sensor.days_to_block, sensor.next_payment_amount/date, button.pay).
- [ ] **A-58** `/rest/v1/events/search` polling — основа для real-time event detection без STOMP/FCM. Требует **ADR-0009** (см. ниже). Закрывает основной use-case Итерации 4 более простым способом.
- [ ] **A-59** Video retention helper — `is_within_retention(camera_type, ts)`, проверка перед video URL request. Закрывает ложные 500 для лифт/публичных камер.
- [ ] **A-61** Двойной HTTP в per-place collectors — вынести `screens` + `access_controls` на уровень `_async_update_data`, передавать как параметры. Perf, не функциональная проблема.
- [ ] **A-62** FAVORITES section в `_extract_hidden_ids` — расширить парсинг с учётом mixed-typed items. Fallback OK, не блокер.

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
- [x] **A-66** ✅ go2rtc stale producer URL после long idle (PR #46).
  `Stream.update_source()` после каждого PUT в go2rtc — forces worker
  restart с обновлённым ffmpeg producer. Избегает 10-30s retry-backoff.
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

## Итерация 4 — Real-time events: research-фаза + ADR (≈ research-фаза, неопределённо)

**Цель research-фазы:** определить **лучший** канал доставки событий
домофона в HA (звонок → автоматизация). Решение должно опираться на
факты, не на предположения. ADR — **после** research, не до.

**Принцип:** строго следуем [ADR-0006](decisions/0006-mirror-app-behavior.md)
— никаких выводов без HAR/APK evidence.

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

### Research tasks (до любого implementation)

- [ ] **R-1 APK Firebase config extraction**: распаковать
  `research/apk/myhome-9.7.0-original.apks` → найти
  `assets/google-services.json` или эквивалент. Зафиксировать
  `project_id`, `sender_id`, `app_id`, `api_key`. **Не** публиковать
  в git (приватная инфо оператора, может triggers ToS issue).
- [ ] **R-2 FCM mimicry feasibility**: исследовать open-source
  Python библиотеки (`firebase_messaging`, `aiogoogle` GCM, etc.) —
  можно ли зарегистрировать HA как receiver для arbitrary FCM project?
  Поискать аналогичные HACS-интеграции (Eufy Security, Olarm Pro,
  Tuya, Hikvision push).
- [ ] **R-3 Test push delivery**: на тестовом аккаунте — register
  HA's FCM token через `POST /rest/v1/subscriberNotifications` с
  payload-эмуляцией приложения. Тригернуть звонок в домофон от
  внешнего источника. Проверить — придёт ли push на HA сторону.
- [ ] **R-4 Legal review**: mimicry приложения может нарушать ToS
  оператора. Оценить риск. Если высокий — не идти этим путём,
  fallback на polling.
- [ ] **R-5 Backup plan**: parallel research на polling
  `/rest/v1/events/search` (что уже было предложено в ADR-0009).
  Latency 15-30s, простая реализация. Использовать как **fallback**
  если R-2/R-3 не получится, или как **safe default** для пользователей,
  которые не хотят push-mimicry.

### Только после research

- [ ] **ADR-0009 (rewrite)** — Event delivery strategy. Документ
  **после** R-1..R-5. Возможные исходы: «push-mimicry primary, polling
  fallback» / «polling-only» / «hybrid auto-detect».
- [ ] **A-58** — implementation выбранного решения (form depends on ADR).
- [ ] **A-50** Camera events — поглощается общим event-stream
  (независимо от ADR-0009 outcome).

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
| 0009 | Event delivery strategy (push-mimicry / polling / hybrid) | **required** after R-1..R-5 research, перед A-58 (Итерация 4) |
| 0010 | Visibility sync strategy (hidden_by, two-way) | опц., Итерация 3-4 (post-factum для PR #35) |

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
