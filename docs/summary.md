Status: Active Owner: Lead Architect Agent Last reviewed: 2026-11-27 (backlog reconciled with master d4e0512)

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

- **Платформы:** `camera`, `lock`, `sensor`, `binary_sensor`, `switch`, `event`; realtime FCM/SIP-контроллер и Lovelace-карта вызова.
- **Дистрибуция:** HACS (`hacs.json`, GitHub Releases zip).
- **API:** `myhome.proptech.ru` (закрытое API мобильного приложения «Мой дом», эмуляция Android-клиента).
- **Опция:** прокси видео через [go2rtc](https://github.com/AlexxIT/go2rtc) и default-off публикация enabled камер по stable external RTSP (A-96/ADR-0014); go2rtc API/RTSP Basic Auth поддерживается.
- **Версия:** см. [`manifest.json`](../custom_components/elektronny_gorod/manifest.json).
- **Codeowner:** [@gentslava](https://github.com/gentslava).
- **PR pre-release:** [`prerelease.yaml`](../.github/workflows/prerelease.yaml) собирает zip в артефакт, [`prerelease-publish.yaml`](../.github/workflows/prerelease-publish.yaml) публикует его как pre-release `pr-N`. Внешний fork-PR требует одобрения запуска. Публикация выполняется отдельным workflow из основного репозитория.

## Состояние (на 2026-08-14)

| Аспект | Статус |
|---|---|
| Работает у пользователей | ✅ да (релизится через HACS) |
| HA hassfest CI | ✅ зелёный |
| HACS validation CI | ✅ зелёный |
| pytest CI | ✅ есть; точная matrix задаётся [`python-tests.yaml`](../.github/workflows/python-tests.yaml) |
| Реальные тесты | ✅ pytest CI и локальный gate настроены; актуальные команды, состав и инварианты — в [`testing/strategy.md`](testing/strategy.md), числа — в CI |
| Integration Quality Scale | ✅ Silver заявлен: каждый модуль выше порога покрытия CI (95%), нативная переавторизация, внятный отказ действий, `parallel-updates`, документация параметров и удаления |
| Безопасность (token redaction) | ✅ P0-утечки S-01..S-06 закрыты (verified по коду) |
| Документация для пользователя | ✅ RU/EN README, HACS info и опубликованные release notes 4.0.1 дают обязательную информацию по FCM hotfix; обзор 4.0.0 сохраняет экран вызова, durable history и opt-in внешний RTSP |
| AIDD документация для агентов | ✅ process/source-of-truth контракты синхронизированы; candidate-bound review lifecycle подтверждён release PR #80 и A-97 закрыт; актуальные findings — в [`project-audit.md`](audit/project-audit.md) |

Этот обзор фиксирует возможности и риски, но не владеет живым количеством тестов. Состав suite и инварианты описывает [`testing/strategy.md`](testing/strategy.md), текущие числа даёт CI; evidence закрытых findings хранится в [`project-audit.md`](audit/project-audit.md).

## Главные сильные стороны

- Полноценный 3-веточный config_flow: phone+SMS / phone+password / advanced (access_token).
- Корректные миграции `async_migrate_entry` v1→2→3.
- Опциональная интеграция go2rtc с real-валидацией; operator-camera source writes консолидированы в PATCH-only client/manager, initial keep-warm активирует dedicated preload consumer.
- Reauth по совпадению `account+subscriber+name`.
- Локализация ru/en.
- Автоматизированный release workflow (zip + автокоммит версии).

## Что сделано (история итераций 1-4)

- **Итерация 1 (hotfix security):** закрыты все P0-утечки токенов — redaction через `_logging.py`/`redact()` (A-01..A-04, S-01..S-06), shared `ClientSession` (A-05), bug `c.get("ID")` (A-06).
- **Итерация 2 (Bronze):** coordinator + `update_interval` (A-08), `CoordinatorEntity` на всех 5 платформах (A-09), стабильный `unique_id` (A-12), sensor MONETARY/RUB (A-14), `async_unsubscribe` (A-16), manifest `bronze`/`hub` (A-34), pytest CI workflow (A-24).
- **Итерация 3 (Silver feature gaps + runtime polish):** DND switches (A-56), balance attrs + binary_sensor (A-57), double-HTTP fix (A-61), visibility/reload cascade (A-64), log throttling (A-65), go2rtc lifecycle (A-66), concurrent stream dedup (A-68), camera auto-recovery для long-open freeze ~30 мин (A-71, ADR-0009).
- **Итерация 4 (realtime intercom):** FCM doorbell event, SIP two-way audio (ADR-0012/0013), экран и карточка вызова, uplink-микрофон, video anti-churn, смена звонящего во время held и точное зеркало stock pre-answer `REGISTER → INVITE → 100 Trying` (A-81/A-85/A-88/A-89/A-90/A-91, PR #69).
- **Итерация 5 (durable history):** polling с per-source silent baseline, restart dedup, config-entry-scoped dispatcher, opt-in camera motion, place-scoped EventEntity, авторизованный browse старых вызовов и `custom:eg-event-history-card` для нескольких мест/аккаунтов (A-50/A-58, PR #70).
- **FCM reliability hotfix (4.0.1):** production-формат `Crypto-Key: dh=…; p256ecdsa=…` нормализуется до чтения зависимостью; конечный dependency fuse исключает горячий цикл на мёртвом socket, а per-entry circuit breaker ограничивает повторные подключения и публикует Repairs (A-80/A-86, PR #78).
- **External RTSP track:** PATCH-only registration провалилась live на пяти lazy streams. Revised per-entry manager делает initial mint→PATCH→preload, проверяет stream/preload/active producer, сохраняет 28:30 non-disruptive PATCH и снимает preloads при cleanup/unload. Pre-mint publication gate не даёт excluded hidden cameras кратковременно попадать в go2rtc и убирает их setup-time operator requests. Publication checkbox changes применяются к живому manager без config-entry reload и массового producer churn; ручное включение запускает missing cameras коротким 0.5s ramp вместо jitter до 60s. Background gate не мешает явному открытию enabled hidden camera в HA даже во время setup: она лениво регистрируется без preload. Для proxy recovery manager обновляет upstream PATCH-ем, не вызывая `Stream.update_source()` с тем же стабильным URL и не оставляя orphan HA worker. Stop дожидается running reconcile и снимает pending preload; manager-eligible streams не дублируют 28:30 entity proactive timer (A-82/A-96, ADR-0014). Повторный production checklist и релиз 4.0.0 завершены 2026-07-16.

## Актуальная очередь

По итогам сверки `master` и [аудита](audit/project-audit.md) известных открытых P0 нет. Исторические исправления и принятые ограничения описаны в [аудите безопасности](audit/security.md).

1. **P1 · A-126 / S-30.** Маскировать URL go2rtc в diagnostics. Секрет подтвердили в синтетической выгрузке из `data` и `options`.
2. **P1 · A-122.** Освобождать SIP/RTP и аудиомост при отмене `answer`. После отмены следующий вызов должен подключаться без перезапуска HA.
3. **P2 · A-121.** Сбрасывать сенсор вытесненной панели при звонке с другой панели. Повторный звонок первой должен снова дать переход в `ringing`.
4. **A-116.** Сохранять пользовательский выбор видимости при отказе `/settings/screens` на старте. Обновлять реестр, когда пришёл достоверный ответ.
5. **A-21 / S-10.** Оценить короткий retry/backoff для выбранных идемпотентных чтений. Ограничить бюджет и сохранить штатную обработку 401/403; таймауты уже есть.

## Проверки на установке и в GitHub

- **A-120.** Проверить отбой звонка при открытии двери и действии «Отклонить» на реальной панели. Код в `master`.
- **A-124.** Проверить первый кадр идущей записи в медиабраузере на реальном потоке оператора. Старт через HA Media Source подтверждён на синтетическом FLV.
- **A-118 и A-84.** Для временного доступа требуется аккаунт с `TEMP_PASS`; для go2rtc — проверка сохранённого конфига после нескольких обновлений URL и рестарта.
- **A-125.** Обнаружение камер уже проверено автором #97 на бете. Фикс входит в следующий стабильный релиз.

## Отложенные задачи

- **A-22 / S-07.** Native reauth уже работает. Автообновление токена зависит от подтверждения момента refresh в официальном приложении.
- **A-19/A-20/A-55, A-26, A-83.** HTTP-исключения и освобождение ответа SMS, reconfigure и рефакторинг восстановления потока остаются техническим долгом.
- **A-94/A-95.** Ключи доступа и настройки личных камер зависят от подтверждения API на подходящем аккаунте или устройстве. План в [mobile-app parity](features/mobile-app-parity/tasklist.md).

## AIDD-структура

Развёрнут **Full AIDD**: canonical `.agents/*` + thin Claude/Codex/Cursor/Copilot adapters + `docs/` + ADR + templates + runbooks. Подробности — в [`index.md`](index.md).

```
AGENTS.md / conventions.md / workflow.md              ← корневые контракты
.agents/                                              ← canonical roles/rules/commands/hooks
.claude/ .codex/ .cursor/                             ← tool-specific adapters
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
