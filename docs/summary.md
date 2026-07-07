Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-07-07 (A-86 → RESOLVED/merged PR #66; A-73/A-74 формализованы в audit; исправлена stale-пометка про A-21)

Source files:
- весь репозиторий — это сжатый обзор

Related docs:
- `index.md`
- `project/project-map.md`
- `audit/project-audit.md`
- `roadmap.md`

Used by agents:
- Любой агент при старте — первое чтение

Quality gates:
- AUDIT_DONE

---

# Summary — быстрый обзор

Двухминутное введение в проект. Все детали — по ссылкам.

## Что это

Home Assistant **custom integration** [`elektronny_gorod`](../custom_components/elektronny_gorod/manifest.json) для российских операторов «Электронный город» (Новотелеком) и «Дом.ру».

- **Платформы:** `camera`, `lock` (домофоны), `sensor` (баланс ЛС).
- **Дистрибуция:** HACS (`hacs.json`, GitHub Releases zip).
- **API:** `myhome.proptech.ru` (закрытое API мобильного приложения «Мой дом», эмуляция Android-клиента).
- **Опция:** прокси видео через [go2rtc](https://github.com/AlexxIT/go2rtc) для получения звука и RTSP, с Basic Auth (username/password) для go2rtc API.
- **Версия:** см. [`manifest.json`](../custom_components/elektronny_gorod/manifest.json).
- **Codeowner:** [@gentslava](https://github.com/gentslava).
- **PR pre-release:** workflow [`prerelease.yaml`](../.github/workflows/prerelease.yaml) выкатывает pre-release zip для каждого открытого PR.

## Состояние (на 2026-05-30)

| Аспект | Статус |
|---|---|
| Работает у пользователей | ✅ да (релизится через HACS) |
| HA hassfest CI | ✅ зелёный |
| HACS validation CI | ✅ зелёный |
| pytest CI | ✅ есть (`python-tests.yaml`, matrix HA 2024.10 + 2026.5) |
| Реальные тесты | ✅ 117 тестов, ~61% coverage (но config_flow/api/helpers — gaps) |
| Integration Quality Scale | 🟡 Bronze заявлен в manifest, но не defensible: нет config_flow-тестов (A-73) |
| Безопасность (token redaction) | ✅ P0-утечки S-01..S-06 закрыты (verified по коду) |
| Документация для пользователя | ⚠️ есть, но с битыми ссылками (A-27/A-28) |
| AIDD документация для агентов | ✅ развёрнута; ⚠️ часть docs отставала, синхронизирована 2026-05-30 |

## Главные сильные стороны

- Полноценный 3-веточный config_flow: phone+SMS / phone+password / advanced (access_token).
- Корректные миграции `async_migrate_entry` v1→2→3.
- Опциональная интеграция go2rtc с real-валидацией (GET /api + PUT /api/streams + DELETE cleanup).
- Reauth по совпадению `account+subscriber+name`.
- Локализация ru/en.
- Автоматизированный release workflow (zip + автокоммит версии).

## Что сделано (история итераций 1-3)

- **Итерация 1 (hotfix security):** закрыты все P0-утечки токенов — redaction через `_logging.py`/`redact()` (A-01..A-04, S-01..S-06), shared `ClientSession` (A-05), bug `c.get("ID")` (A-06).
- **Итерация 2 (Bronze):** coordinator + `update_interval` (A-08), `CoordinatorEntity` на всех 5 платформах (A-09), стабильный `unique_id` (A-12), sensor MONETARY/RUB (A-14), `async_unsubscribe` (A-16), manifest `bronze`/`hub` (A-34), pytest CI workflow (A-24).
- **Итерация 3 (Silver feature gaps + runtime polish):** DND switches (A-56), balance attrs + binary_sensor (A-57), double-HTTP fix (A-61), visibility/reload cascade (A-64), log throttling (A-65), go2rtc lifecycle (A-66), concurrent stream dedup (A-68), camera auto-recovery для long-open freeze ~30 мин (A-71, ADR-0009).

## Главные риски (на 2026-05-30)

> Все исторические P0 token-leaks **закрыты** (verified по коду). Текущие
> открытые риски — reliability + test-debt, не утечки секретов.

### P1 — важные (открыты)

1. **Нет `ClientTimeout` на основном operator API** — [`http.py:111-116`](../custom_components/elektronny_gorod/http.py#L111-L116). Зависший/медленный запрос к `myhome.proptech.ru` тормозит coordinator tick (refresh сериальный, ~6 HTTP на place) и первый `setup` — на время дефолтного aiohttp-таймаута (~5 мин на запрос); явного контроля/ретраев нет. Точечный митигатор есть только для латентно-критичного SIP-mint (`asyncio.timeout(8с)` в `call_controller.py`, см. A-81) — глобальный `ClientTimeout` остаётся открытым. `ha-compatibility.md` при этом **корректно** помечает это `🔴 нет ClientTimeout` (строка 116) — прежняя пометка «ошибочно fixed» была stale. (A-21 / S-09)
2. **config_flow + миграции v1→2→3 без тестов** — `config_flow.py` 15% coverage, `async_migrate_entry` не покрыт. Bronze IQS требует config-flow-test-coverage → заявленный `quality_scale: bronze` пока не defensible. (A-73)
3. **`helpers.py` crypto без golden vectors** — изменение формата бэкенда молча сломает auth. (A-74)
4. **Native reauth / reconfigure flow отсутствуют** (A-25/A-26 — Silver/Gold).

✅ Закрыто в 3.3.0: `diagnostics.py` с redaction (A-23 / S-08; S-16 mitigated) —
SECURITY_OK разблокирован.

### P2 — желательно

- `go2rtc.py` без `ClientTimeout` (A-72).
- `api.py` — `e.args[0]` antipattern + широкий `except Exception` (A-19/A-20).
- Cold-start go2rtc warmup (A-67), lock fake-state cosmetic-cycle (A-15 — `asyncio.sleep` уже убран).

Полный список — в [`audit/project-audit.md`](audit/project-audit.md).

## Первое, что нужно сделать

Reliability-слайс одним PR (отдельно от A-71 camera-работы):

1. `ClientTimeout(total=30)` в [`http.py:110,112`](../custom_components/elektronny_gorod/http.py#L110-L112) + `ClientTimeout(total=10)` в [`go2rtc.py`](../custom_components/elektronny_gorod/go2rtc.py) (A-21/A-72).
2. Создать [`diagnostics.py`](../custom_components/elektronny_gorod/) с `async_redact_data` + `TO_REDACT` (access_token, refresh_token, user_agent, go2rtc_password) — закрывает S-08/S-16, разблокирует SECURITY_OK (A-23).
3. Написать `tests/test_config_flow.py` (happy path + abort `already_configured`) + `tests/test_init_migration.py` (v1→2→3) — Bronze gate (A-73).
4. Узкие исключения в `api.py` вместо `e.args[0]`/`except Exception` (A-19/A-20).

## AIDD-структура

Развёрнут **Full AIDD**: docs/ + `.claude/*` + `.cursor/*` + `.github/copilot-instructions.md` + ADR + templates + runbooks. Подробности — в [`index.md`](index.md).

```
AGENTS.md / CLAUDE.md / conventions.md / workflow.md  ← корневые контракты
docs/
├── index.md                       ← точка входа
├── summary.md                     ← это
├── roadmap.md
├── project/                       ← про проект (карта, источники правды)
├── architecture/                  ← архитектура + HA-чеклист + IQS
├── audit/                         ← все findings + security
├── testing/                       ← test plan
└── aidd/                          ← агентская методология (gates, sources, contributing)
```

## Куда дальше

- Если задача — **понять проект**: [`project/project-map.md`](project/project-map.md) → [`architecture/overview.md`](architecture/overview.md).
- Если задача — **исправить security**: [`audit/security.md`](audit/security.md).
- Если задача — **добавить тесты**: [`testing/strategy.md`](testing/strategy.md).
- Если задача — **планировать**: [`roadmap.md`](roadmap.md).
- Если задача — **внести вклад через AI**: [`aidd/contributing.md`](aidd/contributing.md).

## Next reading

- For full map: `project/project-map.md`
- For architecture: `architecture/overview.md`
- For findings: `audit/project-audit.md`
- For roadmap: `roadmap.md`
- For agent workflow: `../workflow.md`
