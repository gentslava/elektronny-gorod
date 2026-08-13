Status: Active Owner: QA / Testing Agent Last reviewed: 2026-08-14 (FCM/Repairs plus deterministic secret/audit/cross-tool gate regressions; 666-test backend suite synchronized)

Source files:
- `tests/**` (57 test-модулей + `conftest.py`)
- `.github/workflows/python-tests.yaml`
- `pytest.ini`, `requirements_test.txt`
- `custom_components/elektronny_gorod/**`

Related docs:
- `ha-compatibility.md`
- `quality-scale.md`
- `project-audit.md`
- `quality-gates.md`
- `roadmap.md`

Used by agents:
- QA Agent, HA Expert, Validator

Quality gates:
- TESTS_PASS

---

# Testing Strategy

## Текущее состояние

✅ **Suite реально выполняется и покрывает HA lifecycle, entities, FCM/SIP, camera/go2rtc и security regressions.**

| Область | Состояние |
|---|---|
| Локальный suite | **666 passed** (`PYTHONPATH=. .venv/bin/pytest tests/ -q`, 2026-08-14) |
| Test modules | 57 файлов `tests/test_*.py`; общие fixtures в `tests/conftest.py` |
| Frontend | **62 passed**, `tsc --noEmit` и production bundle build |
| Config flow / migrations | Реальные PHC-тесты трёх auth-веток, reauth/abort и v1→v2→v3 (A-73 закрыт) |
| Security / crypto | redaction including production-format config-entry title, diagnostics, HTTP no-leak, golden vectors helpers, deterministic secret-log scanner |
| AIDD gates | Secret scanner; Claude/Codex reconciliation adapters; candidate-SHA CI, stacked target-ref, reviewer parity и portable-plan contracts |
| Realtime intercom | FCM, SIP message/register/protocol/dialog/RTP, controller, audio bridge/uplink |
| Camera / go2rtc | lifecycle, auto-recovery, PATCH-only stream + preload client, manager scheduling/reconcile/dedup, producer health, credential-free diagnostics, call-stream teardown |
| Durable history | exact captured wire contracts, PII-safe DTO, per-source silent baseline, bounded restart dedup, config-entry EventEntity routing, entity authorization и on-demand previous-page browse |
| CI | `python-tests.yaml`: pytest matrix для минимальной и текущей HA-линии + coverage artifact |
| Coverage | Процент намеренно не фиксируется без свежего coverage-run; каноническая команда приведена ниже |

Остающиеся gap-и: нет полностью автоматизированного live-теста против оператора и физического домофона; часть широкого REST API покрыта точечными контрактными тестами. Live/PCAP evidence хранится отдельно в `research/intercom-call-probe/`.

## Фактическая структура по слоям

```
tests/
├── conftest.py                    # PHC fixtures + optional HA-module mocks
├── test_init.py / test_config_flow.py / test_options_flow_clear_creds.py
├── test_http.py / test_api_push.py / test_api_camera.py / test_api_history.py / test_api_sip.py / test_diagnostics.py
├── test_camera_*.py / test_call_camera.py / test_go2rtc_*.py
├── test_stream_manager*.py / test_sensor_rtsp_urls.py / test_config_flow_keep_warm.py
├── test_event.py / test_history.py / test_history_ws.py / test_history_translations.py / test_fcm.py / test_sensor_call_state.py
├── test_sip_*.py / test_uplink_ws.py
├── test_secret_log_gate.py / test_audit_reconciliation_gate.py
├── test_aidd_contracts.py
└── entity, visibility, balance, DND, helpers и migration regressions
```

## Coverage checklist по слоям

Список ниже — поддерживаемый checklist сценариев. Точные имена и фактический inventory всегда берутся из `tests/test_*.py`; новые сетевые контракты должны получать отдельный regression-тест до изменения реализации.

### 1. Config flow (`test_config_flow.py`)

**Минимальный happy path:**

- `test_user_phone_sms_skip_go2rtc` — phone → contract → sms → go2rtc_menu → skip → CREATE_ENTRY.
- `test_user_phone_password` — phone (password=true) → password → go2rtc_menu → skip → CREATE_ENTRY.
- `test_user_access_token_advanced` — advanced mode → access_token → go2rtc_menu → skip → CREATE_ENTRY.
- `test_go2rtc_setup_with_validation` — go2rtc_menu → go2rtc → validate ok → CREATE_ENTRY.

**Error cases:**

- `test_invalid_phone` — пустой phone → errors `invalid_phone`.
- `test_unregistered_phone` — 204 от API → errors `unregistered`.
- `test_invalid_login` — 400 → errors `invalid_login`.
- `test_invalid_password` → errors `invalid_password`.
- `test_invalid_sms_code` → errors `invalid_code`.
- `test_sms_rate_limit` — 429 → errors `limit_exceeded`.
- `test_invalid_contract` — несуществующий subscriber_id.
- `test_go2rtc_unreachable` → errors `go2rtc_unreachable`.
- `test_go2rtc_streams_api_failed` → errors `go2rtc_streams_api_failed`.

**Abort cases:**

- `test_already_configured_by_token` — повтор по access_token → abort `already_configured`.
- `test_reauth_by_account_subscriber` — совпадение account+subscriber+name → обновление data → abort `reauth_successful`.
- `test_missing_phone_abort` — переход в password без phone → abort `missing_phone`.
- `test_missing_contract_abort` → abort `missing_contract`.

### 2. Options flow (`test_options_flow_clear_creds.py`)

- `test_options_enable_go2rtc_valid_url` — happy path.
- `test_options_enable_go2rtc_invalid_url` → errors.
- `test_options_disable_go2rtc` → CREATE_ENTRY (options).

External RTSP options (`test_config_flow_keep_warm.py`): both flags default false; hidden publication depends on the main option; skip/disable normalizes both to false; initial and options flows persist both keys without changing config-entry `VERSION`.

### 3. Init / migrations (`test_init.py`)

- v1 → v3, v2 → v3 и актуальный v3 no-op без потери entry data.
- Failed FCM stop блокирует обычный unload/reload и сохраняет owner.
- Setup-unwind через HA core удаляет owner только после successful stop; failed stop сохраняет его и блокирует replacement на следующей регистрации.
- Surviving owner не заменяется: entry загружается с остальными платформами, FCM остаётся degraded с Repairs и не создаёт HA setup-retry loop.
- FCM claim/start отложены до последнего fallible setup-await.
- Removal после failed unload повторяет stop старого owner; повторный failure сохраняет ownership и возвращает HA `require_restart`.
- Поздний FCM callback после terminal stop не публикует событие звонка.
- Удаление entry очищает только его persistent FCM Repair до best-effort remote cleanup.

### 4. Coordinator (`test_coordinator_no_double_http.py` + entity regressions)

С mocked `ElektronnyGorodAPI`:

- `test_first_refresh_loads_places`.
- `test_get_cameras_info_dedupes_by_id`.
- `test_get_locks_info_handles_no_entrances`.
- `test_get_balances_info_skips_empty_finance`.
- `test_update_balance_state_returns_dict`.
- `test_update_camera_state_finds_by_id` — этот тест **поймает баг** `c.get("ID")` (см. PROJECT_AUDIT P0 #5).
- `test_update_lock_state_handles_missing_access_control`.

### 5. API / HTTP (`test_http.py`, `test_api_push.py`, `test_api_history.py`, `test_api_sip.py`)

С mocked aiohttp responses:

- `test_query_contracts_status_300_returns_contracts`.
- `test_query_contracts_status_200_password_required`.
- `test_query_contracts_status_204_unregistered`.
- `test_query_contracts_status_400_invalid_login`.
- `test_verify_password_success`.
- `test_verify_password_400_invalid`.
- `test_request_sms_code_429_limit_exceeded`.
- `test_verify_sms_code_406_invalid_format`.
- `test_query_profile_401_unauthorized`.
- `test_query_balance_returns_data`.
- History contract: exact `/events/search` POST body/sort encoding and exact forpost camera-event query; typed DTO intentionally excludes backend message and preserves requested camera identity separately from internal `CameraID`.

### 6. Durable history (`test_history.py`, `test_history_ws.py`, `test_event.py`, `test_history_translations.py`)

- Silent first baseline per source, later newest-first overlap and chronological emit; discovering another source does not replay its old rows.
- Per-stream bounded opaque-ID watermark round-trip prevents restart duplicates.
- General/camera failures degrade independently; private camera source excluded; disabled camera-history entities make no camera API request.
- `HistoryManager` persists only ID lists, cancels interval on unload and skips overlapping ticks instead of queueing API cycles.
- Access/camera EventEntity routing uses config-entry-scoped signals, stable IDs, allowlisted state attrs and ru/en translations for every declared event type.
- Browse WebSocket verifies EventEntity read permission, config-entry/source binding, page bounds and exact sanitized previous-page response.
- Frontend model tests exact command shape, untrusted/cross-entity response rejection, overlap dedup, partial-refresh feed preservation, date groups, time formatting and RU/EN labels.

### 7. go2rtc and external RTSP manager

Files: `test_go2rtc_validate.py`, `test_go2rtc_upsert.py`, `test_go2rtc_client.py`, `test_go2rtc_audio.py`, `test_stream_manager.py`, `test_stream_manager_reconcile.py`, `test_stream_manager_scheduler.py`, `test_stream_manager_lifecycle.py`, `test_sensor_rtsp_urls.py`.

- `test_validate_go2rtc_happy_path` — GET 200 + PUT 200 + DELETE cleanup.
- `test_validate_go2rtc_unreachable` — connection error.
- `test_validate_go2rtc_streams_api_failed` — PUT 500.
- `test_normalize_base_url_strips_slash`.
- `test_derive_rtsp_host`.
- Operator-camera source writes remain PATCH-only: errors never fall back to streams PUT. Dedicated preload list/PUT/DELETE stores only stable names; parsed producer snapshots strip the raw source URL.
- Initial operator mint + PATCH + preload is deduplicated across HA-open/ background/recovery reasons and uses HA-managed task lifecycle.
- Active-preload refresh performs mint+PATCH without replacing its consumer; preload failure retries only after minting another one-time URL.
- Publishability/eligibility matrix covers main-off, disabled, hidden and hidden-sub-option. Disabled always wins; hidden policy controls only background publication and preload ownership.
- Before visibility sync, background work for an API-hidden camera performs zero operator mint, go2rtc PATCH and preload calls; a persisted user-shown override remains publishable. Explicit HA-open/recovery for an enabled hidden camera performs lazy mint/PATCH without preload both during setup and after manager startup, even when background publication is off.
- Scheduler covers deterministic cold-start jitter, short 0.5-second interactive policy-on ramp, 28:30 success cadence, 15..300s retry and idempotent stop.
- Reconcile restores missing streams/preloads after go2rtc restart, re-arms an inactive producer within the next minute and removes preload before deciding whether external consumers require deferred stream deletion.
- Config-entry lifecycle proves visibility sync precedes manager start; option-off startup removes preloads and idle streams but preserves active viewers, while unload leaves no task/listener/timer ownership.
- Compatible publication-option saves update the existing manager without config-entry reload, preload disable/enable, PATCH or operator mint. Main off cleans in place, main on schedules missing cameras, and transport/auth changes retain the reload fallback.
- A late background mint cannot PATCH after an option-off policy transition; if PATCH was already running, the existing consumer-aware cleanup path is retained without adding a separate on-demand polling loop.
- Stop waits for a running reconcile and removes a pending preload whose request was cancelled after it may already have reached go2rtc.
- Entity proactive refresh skips background-eligible manager streams so a preload consumer cannot synchronize every camera into a 28:30 burst.
- Diagnostic sensor counts only eligible+present+preloaded+active+fresh streams and excludes operator URL, token, password and authenticated RTSP URL.

Mocked tests prove policy and orchestration, not end-to-end playback. Before merge, run the nine revised live scenarios in [`go2rtc-stream-manager/design.md`](../features/go2rtc-stream-manager/design.md): especially `>1h idle -> external RTSP without HA-open`, active consumer across PATCH and go2rtc restart recovery within 60 seconds.

### 8. Helpers (`test_helpers.py`)

- `test_hash_password_matches_known_vector`.
- `test_hash_password_timestamp_matches_known_vector`.
- `test_find_returns_first_match`.
- `test_dedupe_by_id_keeps_first`.

### 9. Realtime intercom (`test_fcm.py`, `test_sip_*.py`, `test_call_camera.py`)

- FCM parsing и dispatcher lifecycle; bounded watchdog state machine `HEALTHY → SUSPECT → VERIFYING → OPEN → VERIFYING → HEALTHY`.
- Разбор Web Push заголовков `crypto-key`/`encryption`: реальная http_ece-криптография без мока, на форме, снятой с прода (`dh=<87>; p256ecdsa=<87>`). Проверяются обе исторические ошибки — `binascii.Error` без padding и `Invalid EC key.` с ним — и то, что нормализация их снимает. Плюс выбор сегмента по метке независимо от порядка, восстановление метки у значения без неё, правка `app_data` на настоящем protobuf и изоляция патча: соседний клиент того же класса остаётся нетронутым. Тесты с реальной зависимостью берут её в обход `conftest`-мока и скипаются, если её нет.
- Конечный `abort_on_sequential_error_count`: сам факт передачи значения в `FcmPushClientConfig` и полный проход terminated-клиента до OPEN. Отключённый предохранитель делает этот путь недостижимым и подвешивает event loop (#77).
- Capped 15m/1h/6h/24h backoff, quiet OPEN до deadline, persistent Repairs create/retain/delete, multi-entry isolation, removal cleanup и no-secret output.
- Startup/check-in/operator-bind/watchdog/unload races serialized per entry; pre-start clients are discarded without dependency `stop()`, while a failed started-client stop retains ownership and blocks replacement on both ordinary reload and setup-unwind.
- REGISTER profile: FCM `Call-Id`, `Accept: application/sdp`, Contact push-params без лишнего `transport` parameter.
- INVITE pre-answer: немедленный `100 Trying`; `200 OK` только в `accept()`.
- `CANCEL`/`487`, `BYE`, detach/release и malformed-network-input cleanup.
- Call-ID guards, held caller switching, FCM-ended во время живого разговора.
- RTP G.711, AudioBridge downlink, UplinkSink/WebSocket uplink.
- One-build-per-call, concurrent first-open dedup, shared producer и teardown.

## Тестовые зависимости и команды

Конфигурация хранится в `pytest.ini`, зависимости — в `requirements_test.txt` и CI matrix. Канонические локальные команды:

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
PYTHONPATH=. .venv/bin/pytest tests/ \
  --cov=custom_components/elektronny_gorod \
  --cov-report=term-missing -q
```

## CI workflow

Реализован: [`.github/workflows/python-tests.yaml`](../../.github/workflows/python-tests.yaml).

Архитектурные решения, отличные от изначального дизайн-наброска:

- **Matrix-стратегия через `include:`** (не product) — потому что Python и PHC-версии жёстко связаны: PHC 0.13.175 → HA 2024.10.4 → py3.12 (min), PHC 0.13.333 → HA 2026.5.4 → py3.14 (current). Простой `ha-version: [min, stable]` не выражает эту связку.
- **PHC ставится отдельным `pip install` после `requirements_test.txt`** — версия PHC из matrix, не из файла. `requirements_test.txt` держит только `aioresponses` (PHC сам тянет pytest, pytest-cov, coverage).
- **Legacy constraints conditional** для min-job: HA 2024.10 транзитивно использует acme<3, ожидающий `josepy.ComparableX509` (удалён в josepy 2.0), а PHC 0.13.175 ещё не разрешает служебный pycares safe-shutdown thread, появившийся в pycares 4.9. Поэтому min-job ставит `josepy<2` и `pycares<4.9`; для current (HA 2026.5+) шаг пропускается.
- **turbojpeg mock** в `tests/conftest.py` — `pytest-homeassistant-custom-component` не тянет optional HA-extras, нужно для `homeassistant.components.camera.img_util`.
- **Path-filter на push и pull_request** — docs-only коммиты CI не запускают.
- **Coverage artifact** с уникальным именем `coverage-py<v>-phc<v>` (artifact@v4 требует уникальности в matrix).

## Mock-стратегия

| Что мокаем | Чем |
|---|---|
| HTTP-вызовы к API | `aioresponses` или `aiohttp_mock` |
| HA core | `pytest-homeassistant-custom-component` (предоставляет `hass`, `MockConfigEntry`) |
| `async_setup_entry` для config-flow тестов | как в текущем `conftest.py` через patch |
| go2rtc | direct mocked aiohttp context managers for exact method/query/error assertions |
| Время / UUID | `freezegun`, `unittest.mock.patch("uuid.uuid4")` |

## Acceptance Coverage

| Уровень | Минимум |
|---|---|
| Bronze | config_flow happy path + abort already_configured + миграции |
| Silver | + coordinator + api основные endpoints + edge cases |
| Gold | + entity state transitions + repair flow + reconfigure |

## Definition of done для TESTS_PASS gate

- [x] `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный локально: 666 passed (2026-08-14).
- [x] `frontend`: 62 Vitest tests, TypeScript check and production build green.
- [ ] Перед релизом проверить зелёный `.github/workflows/python-tests.yaml` на master.
- [ ] Перед заявлением coverage-процента выполнить свежий coverage-run и сохранить evidence.
- [x] Все миграции v1→2, v2→3, chained покрыты.
- [x] `tests/test_config_flow.py` — реальные PHC-тесты, scaffold-stub отсутствует.
- [x] Изменённый SIP-контракт покрыт на register/protocol/manager/controller слоях.
- [x] External RTSP A-96 принят live; остаточный A-84 config-persistence check остаётся отдельным follow-up и не подменяется mocked suite.

## Risks

| Риск | Mitigation |
|---|---|
| pytest-homeassistant-custom-component требует совместимую версию HA | matrix `phc-version` ↔ `python-version` через `include:` в `python-tests.yaml` |
| reverse-engineered crypto может молча сломаться при изменении API оператора | golden vectors в `test_helpers.py` + integration тест с реальным сервером (опционально, на dev-машине) |
| Mock-объекты «расходятся» с реальным API | периодически (раз в N релизов) запускать «smoke»-сценарий вручную |

## Next reading

- For HA-rules: `ha-compatibility.md`
- For IQS-targets: `quality-scale.md`
- For roadmap: `roadmap.md`
- For gate criteria: `quality-gates.md`
