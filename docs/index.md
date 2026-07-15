Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-07-15 (9.9.0 mobile-app parity research package and drift reconciliation)

Source files:
- AIDD-документы в `docs/` (этот каталог и подкаталоги)

Related docs:
- `../AGENTS.md`
- `../CLAUDE.md`
- `../conventions.md`
- `../workflow.md`

Used by agents:
- ВСЕ агенты в качестве точки входа

Quality gates:
- AUDIT_DONE
- DOCS_UPDATED

---

# AIDD INDEX — точка входа

Это карта AIDD-документации для проекта `elektronny-gorod`. Если вы AI-агент — начните здесь.

## Что это за проект, кратко

Home Assistant custom integration `elektronny_gorod` (RU-операторы Электронный город / Дом.ру). Подробности — в [`summary.md`](./summary.md).

## Как читать документацию

### Быстрый путь (15 минут)

1. [`summary.md`](./summary.md) — что это, состояние, главные риски.
2. [`project-map.md`](./project/project-map.md) — карта файлов.
3. [`roadmap.md`](./roadmap.md) — что планируется.

### Глубокий путь (1-2 часа)

1. `summary.md` + `project-map.md` + `source-of-truth.md`.
2. [`architecture/overview.md`](./architecture/overview.md) — модель данных, lifecycle, async-flow.
3. [`ha-compatibility.md`](./architecture/ha-compatibility.md) — чеклисты HA.
4. [`project-audit.md`](./audit/project-audit.md) — все находки с приоритетами.
5. [`security.md`](./audit/security.md) — детали P0 утечек.
6. [`testing/strategy.md`](./testing/strategy.md) — план тестов.
7. [`quality-gates.md`](./aidd/quality-gates.md) — stop-сигналы.
8. [`contributing.md`](./aidd/contributing.md) — как корректно вносить вклад через AI.

### Какой документ нужен под мою задачу

| Задача | Документы (по порядку) |
|---|---|
| Понять проект «с нуля» | `summary.md` → `project/project-map.md` → `architecture/overview.md` |
| Добавить новую entity | `architecture/overview.md` → `architecture/ha-compatibility.md` → `architecture/quality-scale.md` → conventions.md |
| Изменить config flow | `architecture/overview.md` → `architecture/ha-compatibility.md` → `testing/strategy.md` |
| Исправить security issue | `audit/security.md` → `audit/project-audit.md` → `decisions/0004-token-redaction.md` |
| Добавить тест | `testing/strategy.md` → `aidd/runbooks/testing.md` |
| Запланировать релиз | `roadmap.md` → `aidd/quality-gates.md` → `aidd/runbooks/release.md` → `releases/4.0.0.md` |
| Найти, где источник правды | `project/source-of-truth.md` |
| Понять, какой источник использовать для best practices | `aidd/source-base.md` |
| Принять архитектурное решение | `decisions/README.md` → `aidd/templates/adr.template.md` |
| Запустить локально | `aidd/runbooks/local-development.md` |
| Дебажить странное поведение | `aidd/runbooks/debugging.md` |
| Помочь пользователю | `aidd/runbooks/troubleshooting.md` |
| Собрать HAR-трафик приложения | `aidd/runbooks/har-collection.md` + `/capture-har <scenario>` |
| Понять принцип reverse engineering | `decisions/0006-mirror-app-behavior.md`, `decisions/0007-stateful-emulator-baseline.md` |
| Разобрать API из HAR | `architecture/api-reference.md` (через subagent `reverse-engineer`) |
| Спроектировать новую feature | `aidd/runbooks/har-collection.md` → HAR → `aidd/templates/idea.template.md` → `prd.template.md` → `plan.template.md` |
| Реализовать найденные фичи 9.9.0 | `features/mobile-app-parity/README.md` → `research.md` → `plan.md` → `tasklist.md` |
| Использовать готовый prompt | `aidd/prompt-library.md` |
| Выбрать skill для задачи | `aidd/skills.md` |
| Понять роли агентов | `aidd/multi-agent-workflow.md` |
| Понять, какие tools / MCP можно | `aidd/mcp-tools.md` |

## Какой документ читает какой агент

| Агент | Обязательно | По требованию |
|---|---|---|
| Любой агент при старте | `index.md`, `summary.md`, `AGENTS.md` | — |
| HA-expert | `ha-compatibility.md`, `quality-scale.md`, `architecture/overview.md` | `source-base.md` |
| Security | `security.md`, `project-audit.md` (security разделы) | — |
| QA / Testing | `testing/strategy.md`, `quality-gates.md` | — |
| Architecture | `architecture/overview.md`, `source-of-truth.md`, `project-map.md` | `source-base.md` |
| Documentation | весь каталог | — |
| Release / DevOps | `roadmap.md`, `quality-gates.md`, `../workflow.md` | `releases/4.0.0.md` |
| Validator | `project-audit.md`, `source-of-truth.md`, все остальные | — |

## Где не AIDD-документация

- Пользовательская документация: [`../../README.md`](../README.md), [`../../README.en_EN.md`](../README.en_EN.md).
- HACS: [`../../hacs.json`](../hacs.json), [`../../info.md`](../info.md).
- CI: [`../../.github/workflows/`](../.github/workflows/).

## Состояние документов

| Документ | Статус |
|---|---|
| `index.md` | Active |
| `summary.md` | Active |
| `roadmap.md` | Active |
| `project/project-map.md` | Active |
| `project/source-of-truth.md` | Active |
| `architecture/overview.md` | Active |
| `architecture/ha-compatibility.md` | Active |
| `architecture/quality-scale.md` | Active |
| `audit/project-audit.md` | Active |
| `audit/security.md` | Active |
| `testing/strategy.md` | Active |
| `aidd/quality-gates.md` | Active |
| `aidd/source-base.md` | Active |
| `aidd/contributing.md` | Active |
| `aidd/multi-agent-workflow.md` | Active |
| `aidd/skills.md` | Active |
| `aidd/prompt-library.md` | Active |
| `aidd/mcp-tools.md` | Active |
| `decisions/0001..0007` | accepted (0001, 0006, 0007) / proposed (0002..0005) |
| `aidd/templates/*` | шаблоны |
| `aidd/runbooks/*` | руководства (вкл. `har-collection.md`) |
| `features/example/*` | образец |
| `features/mobile-app-parity/*` | active research/PRD/plan: history, archive, guests, keys, camera settings |
| `architecture/api-reference.md` | canonical reverse-engineered API knowledge with HAR/runtime/static evidence tiers |
| `research/api/README.md` | конвенция для HAR-снимков (сама папка — local-only) |
| `research/apk/README.md` | конвенция для APK (сама папка — local-only) |
| `research/scripts/README.md` | pipeline для сбора HAR |

## Next reading

- For project map: `project-map.md`
- For source of truth: `source-of-truth.md`
- For architecture: `architecture/overview.md`
- For HA compat: `ha-compatibility.md`
- For all findings: `project-audit.md`
- For quality gates: `quality-gates.md`
- For roadmap: `roadmap.md`
