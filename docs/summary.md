Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-07-16 (external RTSP preload revision, PATCH-only live
failure, 549-test evidence and repeat acceptance synchronized)

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

- **Платформы:** `camera`, `lock`, `sensor`, `binary_sensor`, `switch`, `event`;
  realtime FCM/SIP-контроллер и Lovelace-карта вызова.
- **Дистрибуция:** HACS (`hacs.json`, GitHub Releases zip).
- **API:** `myhome.proptech.ru` (закрытое API мобильного приложения «Мой дом», эмуляция Android-клиента).
- **Опция:** прокси видео через [go2rtc](https://github.com/AlexxIT/go2rtc)
  и default-off публикация enabled камер по stable external RTSP
  (A-96/ADR-0014); go2rtc API/RTSP Basic Auth поддерживается.
- **Версия:** см. [`manifest.json`](../custom_components/elektronny_gorod/manifest.json).
- **Codeowner:** [@gentslava](https://github.com/gentslava).
- **PR pre-release:** workflow [`prerelease.yaml`](../.github/workflows/prerelease.yaml) выкатывает pre-release zip для каждого открытого PR.

## Состояние (на 2026-07-16)

| Аспект | Статус |
|---|---|
| Работает у пользователей | ✅ да (релизится через HACS) |
| HA hassfest CI | ✅ зелёный |
| HACS validation CI | ✅ зелёный |
| pytest CI | ✅ есть (`python-tests.yaml`, matrix HA 2024.10 + 2026.5) |
| Реальные тесты | ✅ 549 backend + 62 frontend тестов зелёные локально; TypeScript check и production build зелёные |
| Integration Quality Scale | ✅ Bronze defensible: config_flow + миграции покрыты тестами (A-73 закрыт, `3a60b15`) |
| Безопасность (token redaction) | ✅ P0-утечки S-01..S-06 закрыты (verified по коду) |
| Документация для пользователя | ✅ RU/EN README и release notes 4.0.0 описывают FCM/SIP, экран вызова, durable history и opt-in внешний RTSP; добавлены runtime screenshots |
| AIDD документация для агентов | ✅ синхронизирована с mobile-app/API reconciliation 2026-07-15 |

## Главные сильные стороны

- Полноценный 3-веточный config_flow: phone+SMS / phone+password / advanced (access_token).
- Корректные миграции `async_migrate_entry` v1→2→3.
- Опциональная интеграция go2rtc с real-валидацией; operator-camera source
  writes консолидированы в PATCH-only client/manager, initial keep-warm
  активирует dedicated preload consumer.
- Reauth по совпадению `account+subscriber+name`.
- Локализация ru/en.
- Автоматизированный release workflow (zip + автокоммит версии).

## Что сделано (история итераций 1-4)

- **Итерация 1 (hotfix security):** закрыты все P0-утечки токенов — redaction через `_logging.py`/`redact()` (A-01..A-04, S-01..S-06), shared `ClientSession` (A-05), bug `c.get("ID")` (A-06).
- **Итерация 2 (Bronze):** coordinator + `update_interval` (A-08), `CoordinatorEntity` на всех 5 платформах (A-09), стабильный `unique_id` (A-12), sensor MONETARY/RUB (A-14), `async_unsubscribe` (A-16), manifest `bronze`/`hub` (A-34), pytest CI workflow (A-24).
- **Итерация 3 (Silver feature gaps + runtime polish):** DND switches (A-56), balance attrs + binary_sensor (A-57), double-HTTP fix (A-61), visibility/reload cascade (A-64), log throttling (A-65), go2rtc lifecycle (A-66), concurrent stream dedup (A-68), camera auto-recovery для long-open freeze ~30 мин (A-71, ADR-0009).
- **Итерация 4 (realtime intercom):** FCM doorbell event, SIP two-way audio
  (ADR-0012/0013), экран и карточка вызова, uplink-микрофон, video anti-churn,
  смена звонящего во время held и точное зеркало stock pre-answer
  `REGISTER → INVITE → 100 Trying` (A-81/A-85/A-88/A-89/A-90/A-91, PR #69).
- **Итерация 5 (durable history):** polling с per-source silent baseline,
  restart dedup, config-entry-scoped dispatcher, opt-in camera motion,
  place-scoped EventEntity, авторизованный browse старых вызовов и
  `custom:eg-event-history-card` для нескольких мест/аккаунтов (A-50/A-58,
  PR #70).
- **External RTSP track:** PATCH-only registration провалилась live на пяти
  lazy streams. Revised per-entry manager делает initial mint→PATCH→preload,
  проверяет stream/preload/active producer, сохраняет 28:30 non-disruptive
  PATCH и снимает preloads при cleanup/unload. Pre-mint publication gate не
  даёт excluded hidden cameras кратковременно попадать в go2rtc и убирает их
  setup-time operator requests. Publication checkbox changes применяются к
  живому manager без config-entry reload и массового producer churn; ручное
  включение запускает missing cameras коротким 0.5s ramp вместо jitter до 60s.
  Background gate не мешает явному открытию enabled hidden camera в HA даже
  во время setup: она лениво регистрируется без preload. Для proxy recovery
  manager обновляет upstream PATCH-ем, не вызывая `Stream.update_source()` с
  тем же стабильным URL и не оставляя orphan HA worker. Stop дожидается running
  reconcile и снимает pending preload; manager-eligible streams не дублируют
  28:30 entity proactive timer (A-82/A-96, ADR-0014).
  Повторный production checklist ещё не закрыт, поэтому release status пока не
  заявляется; реализация уже находится в master через PR #71.

## Главные риски (на 2026-07-16)

> Все исторические P0 token-leaks **закрыты** (verified по коду). Текущие
> открытые риски — reliability + test-debt, не утечки секретов.

### P1 — важные

1. 🟡 **`ClientTimeout` на operator API — timeout закрыт, retry остаётся.** `http.py` теперь шлёт явный `ClientTimeout` (REST 30с / binary 60с, connect 10с) — commit `3885bb0`. Осталось: retry/backoff для идемпотентных GET (follow-up, POST/login/open_lock не идемпотентны — ADR-0006). (A-21 / S-09)
2. ✅ **config_flow + миграции v1→2→3 — покрыты тестами** (`3a60b15`): `test_config_flow.py` (3 ветки auth + go2rtc + abort/reauth) + `test_init.py` (миграции). Bronze config-flow gate закрыт. (A-73)
3. ✅ **`helpers.py` crypto — golden vectors добавлены** (`362237b`, `test_helpers.py`): регрессия ловит тихий breakage формулы. (A-74)
4. **Native reauth / reconfigure flow отсутствуют** (A-25/A-26 — Silver/Gold) — остаётся открытым.
5. 🟡 **External RTSP after idle (A-96)** — preload revision и 549-test suite
   готовы в feature-ветке, но пять проблемных камер, `>1h idle → external
   player`, restart, consumer-preservation и cleanup должны быть повторно
   записаны на live deployment.

✅ Закрыто в 3.3.0: `diagnostics.py` с redaction (A-23 / S-08; S-16 mitigated) —
SECURITY_OK разблокирован.

### P2 — желательно

- go2rtc persistent-config bloat частично mitigated PATCH-only path,
  но требует live persistence check (A-84).
- `api.py` — `e.args[0]` antipattern + широкий `except Exception` (A-19/A-20).
- HTML service-pipe/VPN block пока превращается в generic `ClientError` и
  может выглядеть как пустой список камер (A-92; нужен воспроизводимый HAR).
- Cold-start go2rtc warmup (A-67), lock fake-state cosmetic-cycle (A-15 — `asyncio.sleep` уже убран).

### Mobile-app parity backlog

AVD/HAR/APK analysis оформлен в отдельный
[`feature package`](features/mobile-app-parity/README.md). Durable event history
реализована в PR #70; в backlog остаются archive/Media Source (A-50/A-59),
response action гостевого приглашения (A-93), ключи доступа (A-94) и настройки
личных камер (A-95). Guest/key/camera write paths сохраняют обязательный HAR/
hardware gate. Guest links, key codes and signed media URLs не допускаются в
entity state, recorder, diagnostics или логи.

Полный список — в [`audit/project-audit.md`](audit/project-audit.md).

## Первое, что нужно сделать

Оставшийся reliability / quality-долг (по убыванию ценности):

1. Пройти оставшиеся revised live external-RTSP scenarios A-96 и зафиксировать
   evidence в существующем feature design до публикации 4.0.0.
2. Retry/backoff helper для идемпотентных operator GET (5xx / connection errors) — остаток A-21.
3. Узкие исключения в `api.py` вместо `e.args[0]`/`except Exception` (A-19/A-20).
4. Native reauth / reconfigure flow (A-25/A-26 — Silver).

Feature backlog независим от reliability queue; порядок зафиксирован в
[`mobile-app-parity/tasklist.md`](features/mobile-app-parity/tasklist.md):
history/archive → guest invite → enabled-account keys → private-camera hardware.

✅ Сделано в этом цикле: `http.py` ClientTimeout (A-21 timeout, `3885bb0`), `test_config_flow.py` + `test_init.py` (A-73, `3a60b15`), `test_helpers.py` golden vectors (A-74, `362237b`). `diagnostics.py` (A-23) закрыт ещё в 3.3.0.

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
