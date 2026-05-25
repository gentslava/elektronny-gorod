Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-22

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

## Итерация 2 — Bronze quality scale (≈ 3-5 дней)

**Цель:** довести интеграцию до Bronze. См. [`architecture/quality-scale.md#bronze`](architecture/quality-scale.md).

**Acceptance:**
- `pytest tests/ -v` зелёный в CI;
- `manifest.json` содержит `quality_scale: "bronze"` и `integration_type: "hub"`;
- entity имеют `_attr_has_entity_name = True` и стабильный `unique_id`;
- coordinator имеет `update_interval` и обновляет данные.

### Tasks

- [ ] **A-08** Задать `update_interval=timedelta(minutes=5)` в `ElektronnyGorodUpdateCoordinator`; в `_async_update_data` обновлять баланс + список мест; вернуть `data: dict`.
- [ ] **A-09** Перевести Sensor / Lock / Camera на `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]` + `_handle_coordinator_update`.
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
- [ ] **CI-1** Создать `.github/workflows/python-tests.yaml`.
- [x] **A-34** ✅ slice 3c — `quality_scale: "bronze"`, `integration_type: "hub"` в `manifest.json`.
- [ ] **A-35** Создать `CHANGELOG.md`.
- [ ] **A-36** Создать `CONTRIBUTING.md` со ссылкой на `aidd/contributing.md`.
- [ ] **A-27..A-29** Поправить README (битая ссылка, `electronic_city → elektronny_gorod`, badge HA-версии).
- [ ] **ADR-0002** «coordinator pattern: переход на CoordinatorEntity + update_interval».
- [ ] **ADR-0004** «token redaction strategy».

**Quality gates passed:** `TESTS_PASS`, `SECURITY_OK`, `REVIEW_OK`, `DOCS_UPDATED`. Integration Quality Scale: Bronze.

## Итерация 3 — Silver + Full AIDD (≈ 5-7 дней)

**Цель:** Silver Quality Scale + расширенная агентская инфраструктура.

**Acceptance:**
- Silver criteria по [`architecture/quality-scale.md#silver`](architecture/quality-scale.md);
- coverage ≥ 80% по модулям;
- agent-skills hooks работают.

### Tasks

#### HA features

- [ ] **A-22** Поведение при 401: сначала собрать HAR-сессию со сценарием истечения access_token, затем реализовать **точно как в приложении** (см. [ADR-0006](decisions/0006-mirror-app-behavior.md)). До получения HAR — оставить текущее graceful поведение (UpdateFailed → пользователь делает reauth через UI).
- [ ] **A-25** Native reauth flow (`async_step_reauth_confirm`).
- [ ] **A-26** Reconfigure flow (`async_step_reconfigure`).
- [ ] **A-37** `parallel_updates = 1` (или другое значение) на entity-классах.
- [ ] **A-38** Обработка unavailable / log-when-unavailable.
- [ ] **A-15** Решить судьбу `fake_timer_lock` в `lock.py` — либо удалить, либо переписать `lock` → `button`. Требует ADR-0005.
- [ ] Repairs flow для edge-cases (заблокированный аккаунт, истёкший договор).

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

## Итерация 4 — Real-time + push (≈ research-фаза, неопределённо)

**Цель:** реализовать приём событий домофона в real-time (звонок → автоматизация HA).

**Принцип:** строго следуем [ADR-0006](decisions/0006-mirror-app-behavior.md) — никаких догадок без подтверждения через HAR.

### Research-фаза (обязательна до spec)

- [ ] **HAR-1** Собрать HAR со сценарием активного WebSocket-соединения + реальный звонок в домофон. Зафиксировать содержимое STOMP-фреймов.
- [ ] **HAR-2** Capture SIP-трафика (через mitmproxy в TCP-mode или Wireshark) во время реального звонка. Зафиксировать INVITE / RTP flow.
- [ ] **HAR-3** Capture поведения приложения «в фоне» (нажал home, ждал ~5 минут, входящее событие). Какие каналы реально доставляют?
- [ ] Анализ — три канала (STOMP / SIP / FCM): что чем доставляется, какие фолбэки, какая latency.

### Возможные direction (зависят от research)

- [ ] **A-47** STOMP-клиент в `coordinator` (если WS несёт релевантные события):
  - WebSocket subscriber поверх существующего `aiohttp` (либо `aiohttp.ClientWebSocketResponse`).
  - SUBSCRIBE на нужные destinations (зависит от research).
  - На приходящий MESSAGE — `async_dispatcher_send` → HA-entity / `event`.
- [ ] **A-49** SIP-клиент (если SIP несёт INVITE для звонков):
  - Прототип через PJSIP / Linphone CLI.
  - Регистрация SIP UAC с credentials из `sipdevices`.
  - На INVITE — `event` в HA + потенциально доступ к RTP audio (long-term).
- [ ] **A-50** Camera events polling — независимая фича, не требует real-time:
  - `GET /api/mh-camera-personal/.../cameras/{id}/events` периодически.
  - `event` entity на каждую запись.

### Ожидаемые исходы

- Лучше всего: один STOMP-клиент закрывает 80% сценариев. Лёгкий wins для HA-автоматизаций.
- Хуже всего: события размазаны по 3 каналам, нужны все три → сложность поддержки растёт. В этом случае — выбрать самый стабильный канал и документировать ограничения.

**Quality gates passed:** READY_FOR_RELEASE + Silver IQS + работающая push-фича.

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
