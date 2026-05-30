# ADR-0010: AIDD state-management и reconciliation findings↔git

- **Status:** accepted
- **Date:** 2026-05-30
- **Owner:** [@gentslava](https://github.com/gentslava) + Lead Architect Agent
- **Supersedes:** — (дополняет [ADR-0001](0001-aidd-adoption.md), не отменяет)

## Context

Meta-аудит AIDD-процесса 2026-05-30 (на материале findings прошлого
аудита) выявил **системный дрейф документации** — ровно тот провал, риск
которого [ADR-0001](0001-aidd-adoption.md) **предсказал** в разделе
Negative («Maintenance rules легко проигнорировать без CI-проверки») и
обещал закрыть в Mitigation («Итерация 3: pre-commit hook на
synchronization»). Mitigation **не был реализован**. Результат —
наблюдаемые дефекты (D-01..D-06):

- **D-01.** Entry-point контракты (`AGENTS.md`, `CLAUDE.md`, `workflow.md`),
  которые агент читает **первыми**, описывали уже исправленный код как
  сломанный: «pytest отсутствует / тест — stub», «coordinator без
  update_interval», «http per-request ClientSession», «lock fake-таймер»,
  «hooks не настроены». Свежий агент по контракту «чинит» починенное.
- **D-02.** Статус findings не сверялся с git. `A-71` помечен
  `RESOLVED PR #57`, но его **нет в master** (только в feature-ветке).
  `A-61/A-64/A-65` помечены `PR TBD`, хотя **уже в master**.
  Аудит-лог — главная память проекта — недостоверен в обе стороны.
- **D-03.** «Текущее состояние» дублировалось в 4 доках (`summary.md`,
  `quality-gates.md` state-таблица, `AGENTS.md` inline-аннотации,
  `security.md` threat-model) — каждая копия гнила независимо (DRY-нарушение
  на уровне docs).
- **D-04.** `maintenance-rules` однонаправлены (`код-файл → docs`); нет
  триггера `finding→RESOLVED ⇒ обновить summary/AGENTS/CHANGELOG`. Файлы,
  гниющие сильнее всего, не покрыты правилами.
- **D-05.** Гейты документированы, но не блокируют: `manifest` выставлен
  `quality_scale: bronze` при ложном Pass-критерии `TESTS_PASS`
  (config_flow без тестов), без записанного waiver.
- **D-06.** `docs-keeper` ручной, не подключён к hook; синк полагается на
  память агента.

Корневая причина — **document-centric snapshot model**: состояние
зафиксировано снимками (frontmatter `Last reviewed`, inline-статусы,
state-таблицы) в множестве мест. Снимки рассинхронизируются по определению.

## Decision

Перейти от snapshot-модели к **single-source-of-truth + reconciliation**:

### 1. Единый источник состояния (лечит D-03)

- **Канонический источник «что сделано / что открыто»** — `docs/audit/project-audit.md`
  (findings со `Status:`) + git master. Точка зрения «за 2 минуты» —
  `docs/summary.md` (таблица «Состояние» + блок «Главные риски»).
- **Все прочие доки ссылаются, не копируют.** Из `quality-gates.md`
  удаляется таблица «Реальное состояние сейчас». Из `AGENTS.md` —
  inline-`🔴`-аннотации в `Project structure` (структура описывает
  **назначение** файлов, не их текущее качество).

### 2. Reconciliation findings↔git (лечит D-02)

- Finding можно пометить `✅ RESOLVED` **только** если фикс **в master**
  (есть commit SHA в `git log master`). Иначе — статус
  `🟢 resolved-in-branch (pending merge <ref>)`.
- `/audit` и `/release-check` получают обязательный reconciliation-шаг:
  для каждого `RESOLVED`/`resolved-in-branch` finding проверить наличие
  его commit в master. Автоматизировано скриптом
  `.claude/hooks/check-audit-reconciliation.sh`.

### 3. Двунаправленные maintenance-rules (лечит D-04)

- В `project-map.md`, `workflow.md` (§9), `docs-keeper.md` добавляется
  ось **«событие состояния → docs»** (а не только «код-файл → docs»):

  | Событие | Обновить |
  |---|---|
  | finding → `RESOLVED`/`resolved-in-branch` | `summary.md` (риски), `CHANGELOG`, structure-аннотации `AGENTS.md` если упоминался |
  | разрешён known антипаттерн в коде | `AGENTS.md` `Project structure` (снять `🔴`) |
  | изменён CI / тест-состояние | `summary.md` «Состояние», `quality-gates.md` (ссылка, не копия) |
  | правка `AGENTS.md`/`CLAUDE.md` self-описания (стек, hooks, setup) | взаимная сверка обоих + `contributing.md` |

### 4. Блокирующие гейты (лечит D-05)

- `manifest.json:quality_scale` **не поднимать выше** уровня,
  подтверждённого соответствующими гейтами (Bronze требует реального
  `config-flow-test-coverage`). Несоответствие = открытый finding.
- Пропуск любого обязательного гейта — только с **записанным waiver**
  (строка в `project-audit.md` / PR body: «gate X skipped, owner: <...>,
  причина: <...>»). «Потом починим» запрещено (повтор `quality-gates.md`
  §Принцип, теперь enforced в `release-check`).

### 5. Hook-enforced drift-check (лечит D-06, выполняет обещание ADR-0001)

- `.claude/hooks/check-audit-reconciliation.sh` — проверяет:
  (a) каждый `RESOLVED` finding имеет commit в master;
  (b) контракты не содержат known-stale маркеров (grep на «pytest
  отсутствует», «без update_interval», «per-request ClientSession»,
  «hooks не настроены» при опровергающем коде).
- Вызывается из `/release-check` (обязателен для `READY_FOR_RELEASE`) и
  доступен вручную. Опционально — wired как `PreToolUse(git commit)` /
  `Stop` hook в `settings.json` (не блокирующий по умолчанию, чтобы не
  мешать WIP-коммитам в ветке).

## Consequences

### Positive

- Контракты перестают дезинформировать агентов (D-01).
- Аудит-лог достоверен: `RESOLVED` ⇒ доказуемо в master (D-02).
- Состояние живёт в одном месте — меньше точек гниения (D-03).
- Синк срабатывает на событиях состояния, а не только на правке файлов (D-04).
- `quality_scale` отражает реальность; пропуски гейтов прослеживаемы (D-05).
- Обещание ADR-0001 (CI-проверка синка) наконец выполнено (D-06).

### Negative

- Reconciliation-шаг удлиняет `/audit` и `/release-check`.
- Лишний скрипт-хук в поддержке.
- Статус `resolved-in-branch` добавляет промежуточное состояние (но это
  **честнее**, чем бинарный RESOLVED/OPEN).

### Mitigation

- Reconciliation автоматизирован одним grep-скриптом — секунды.
- Хук не блокирует WIP по умолчанию; жёсткая проверка — только на release.

## Alternatives considered

1. **Просто пропатчить устаревший текст** (вариант «только D-01»).
   Отклонено: лечит симптом, не механизм — дрейф вернётся через 1-2
   итерации (ровно как после ADR-0001).
2. **Авто-генерация state-доков из git/findings** (скрипт, рендерящий
   `summary.md`). Отклонено пока: переусложнение для one-codeowner проекта;
   single-source + reconciliation даёт 80% пользы за 20% работы.
3. **Снести state-таблицы вообще, оставить только git.** Отклонено:
   «2-минутный обзор» для нового агента ценен; сохраняем его в **одном**
   месте (`summary.md`).

## Supersedes / Superseded by

— Дополняет ADR-0001 (реализует его невыполненную Mitigation).

## Notes

Этот ADR — про **процесс**, не про код интеграции. Он не меняет
`custom_components/**`. Проверка эффективности: при следующем `/audit`
дрейф contracts↔code должен быть нулевым, а каждый `RESOLVED` —
сверяемым с master.
</content>
</invoke>
