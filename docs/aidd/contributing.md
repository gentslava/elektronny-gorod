Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-05-22

Source files:
- весь репозиторий (это процессный документ)

Related docs:
- `../../AGENTS.md`
- `../../CLAUDE.md`
- `../../conventions.md`
- `../../workflow.md`
- `quality-gates.md`
- `../audit/project-audit.md`

Used by agents:
- Любой AI-агент при работе над задачей

Quality gates:
- AUDIT_DONE

---

# Contributing through AI agents

Как корректно вносить вклад в проект с помощью AI-агентов (Claude Code, OpenAI Codex, Cursor, Aider, Copilot и др.). Если вы человек — большая часть всё равно применима.

## Перед началом работы

1. **Прочитать** [`../../AGENTS.md`](../../AGENTS.md) и [`../index.md`](../index.md).
2. **Понять контекст** проекта через [`../summary.md`](../summary.md).
3. **Проверить**, нет ли существующей задачи в [`../roadmap.md`](../roadmap.md) или соответствия в [`../audit/project-audit.md`](../audit/project-audit.md).
4. **Идентифицировать** quality gate, который должен пройти ваш PR (см. [`quality-gates.md`](quality-gates.md)).

## Workflow (краткое)

Полный процесс — в [`../../workflow.md`](../../workflow.md). Минимум:

```text
idea → spec (для нетривиального) → research → plan → implementation → tests → docs → review → release
```

## Правила для AI-агента

### 1. Surface assumptions

Прежде чем писать код, явно перечислить:

```
ASSUMPTIONS:
1. Изменение касается только <модуля>.
2. Тесты для этого слоя ещё не существуют.
3. Breaking change для существующих entries не предполагается.
→ Подтвердите или поправьте, прежде чем продолжу.
```

### 2. Манагить confusion активно

При противоречиях между документацией и кодом:
- **STOP.** Не угадывать.
- Назвать конкретное противоречие.
- Спросить, какой источник правды.
- Зафиксировать резолюцию в [`../project/source-of-truth.md`](../project/source-of-truth.md).

### 3. Push back when warranted

Если предложенный подход имеет очевидную проблему — указать её прямо, не соглашаться формально. Лучше:

> «Этот fix замаскирует баг A-06. Корректнее исправить ключ `ID` → `id`, чем добавлять try/except.»

чем:

> «Конечно, добавлю try/except!»

### 4. Enforce simplicity

- Можно ли это в меньше строк?
- Платят ли абстракции за свою сложность?
- Не делать «попутный рефакторинг» в одном PR с фиксом.

### 5. Scope discipline

Запрещено:
- Удалять комментарии, которые не понимаете.
- «Чистить» код, не относящийся к задаче.
- Рефакторить соседние модули как побочный эффект.
- Удалять «казалось бы неиспользуемое» без явного approval.
- Добавлять фичи «потому что выглядит полезно».

### 6. Verify, don't assume

- Тесты должны быть запущены и зелёные.
- Hassfest должен пройти.
- Diff должен быть прочитан **самим агентом** до коммита.
- Грep на «не логирую ли я токены» — обязателен после правок в `http.py` / `config_flow.py`.

## Boundaries (повтор)

### Always (без подтверждения)

- Чтение любых файлов проекта.
- Read-only Bash-команды.
- Создание/обновление AIDD-документов в `docs/**`.
- Предложение изменений с evidence.

### Ask first

- Любые правки в `custom_components/elektronny_gorod/**`.
- `manifest.json`, `hacs.json`, `requirements`, `version`.
- Config-flow steps, entity unique_id, device_info.
- CI workflow.
- Удаление файлов.
- Публичная документация (README, info.md).

### Never

- Логировать токены / пароли / SMS / headers с Bearer.
- Force-push на master.
- `--no-verify` для bypass хуков.
- Менять config-entry `VERSION` без migration step.
- «Исправлять» тесты так, чтобы они зелёные при сломанном коде.

## Структура изменений

### Commit-сообщения

Conventional Commits:

```
feat: add reconfigure flow step
fix: remove access_token from debug logs
refactor: extract _collect_cameras_for_place
docs: update HA min version in hacs.json
test: add config_flow happy path coverage
chore: bump manifest version
```

Тело — «почему», а не «что». Diff показывает «что».

### PR-описание

```markdown
## What
1-2 строки — что изменили.

## Why
Ссылка на задачу из `docs/roadmap.md` (например A-06) или новый issue.

## Evidence
- Что проверили: `pytest tests/test_xxx.py -v` зелёный.
- Hassfest: ✓.
- Grep на логирование токенов: clean.

## Risks / breaking
Если применимо.

## Docs updated
- [ ] `docs/audit/project-audit.md` (если закрыли пункт)
- [ ] `docs/architecture/overview.md` (если меняется flow)
- [ ] `docs/architecture/ha-compatibility.md` (если касается HA-rules)
- [ ] `docs/testing/strategy.md` (если меняются ожидания)
```

### Размер PR

- **One task — one PR.** Не смешивать security-fix с рефакторингом.
- < 400 строк diff желательно. Если больше — обоснование в описании.

## Когда писать ADR

ADR (Architecture Decision Record) для изменений, которые сложно откатить:

- Смена паттерна (например, переход на `CoordinatorEntity`).
- Breaking change в config-flow.
- Изменение domain / minimum HA version.
- Стратегические security-решения (redaction strategy).
- Изменение пакетной структуры.

ADR-шаблон (создаётся в Итерации 3): `docs/decisions/NNNN-title.md` со следующими полями:
- Status (proposed / accepted / rejected / deprecated / superseded by ...).
- Context.
- Decision.
- Consequences (positive / negative / neutral).
- Date.

## Какие skills использовать

Полный гайд — в [`skills.md`](skills.md). Для быстрой ориентации:

| Skill | Когда |
|---|---|
| `agent-skills:security-and-hardening` | работа с `http.py`, `config_flow.py:logging`, `helpers.py`, новые diagnostics |
| `agent-skills:test-driven-development` | переписывание тестов config-flow, новые тесты coordinator/api |
| `agent-skills:code-review-and-quality` | перед коммитами, затрагивающими entity / coordinator |
| `agent-skills:incremental-implementation` | большие изменения (CoordinatorEntity-перевод, новые platforms) |
| `agent-skills:spec-driven-development` | новые features (например, reconfigure flow) |
| `agent-skills:debugging-and-error-recovery` | при странном поведении в runtime / падающих тестах |

## Какие агенты Claude Code использовать

В этом проекте определены 5 ролей. Полный гайд — [`multi-agent-workflow.md`](multi-agent-workflow.md). Кратко:

| Subagent | Когда вызывать |
|---|---|
| `lead-architect` | начало сессии, координация, обновление audit/summary/roadmap |
| `ha-expert` | manifest, config_flow, coordinator, entity, IQS |
| `security-auditor` | http.py, config_flow.py логирование, helpers.py, diagnostics |
| `qa-engineer` | новые тесты, изменения test plan |
| `docs-keeper` | синхронизация docs после правок кода |

## Slash-команды

В `.claude/commands/`:

- `/audit` — полный аудит (Lead Architect + параллельные subagents)
- `/security-check` — поиск утечек секретов
- `/test-config-flow` — переписать или дополнить тесты config_flow
- `/docs-update` — синхронизация docs с кодом
- `/release-check` — pre-release checklist

## Quality gates

Перед merge — все обязательные gates зелёные. Список — в [`quality-gates.md`](quality-gates.md).

## Что делать, если…

| Ситуация | Действие |
|---|---|
| Тест падает | Не «исправлять» тест. Найти root cause через `agent-skills:systematic-debugging`. |
| `hassfest` падает | Прочитать сообщение, поправить manifest. Не подавлять. |
| Конфликт с master при rebase | Решать вручную; никаких `git checkout master --theirs` для config_flow или crypto. |
| Не знаю, какой fix корректный | Сначала ADR / spec; обсудить с owner. |
| Security incident (нашёл утечку) | Немедленно — issue в `docs/audit/security.md` + hotfix-релиз. |
| Нужно изменить публичный API entity | Breaking change → MAJOR bump + миграция + раздел в CHANGELOG. |

## Что нельзя забыть

- Documentation update — **часть** definition of done, не отдельный PR.
- Maintenance rules в [`../project/project-map.md#maintenance-rules`](../project/project-map.md#maintenance-rules) — обязательны.
- Связь PR ↔ audit ID (A-NN) — обязательна.
- `LOGGER.exception()` вместо `LOGGER.error(f"...{e}")` — обязательно.

## Next reading

- For workflow: `../../workflow.md`
- For conventions: `../../conventions.md`
- For gates: `quality-gates.md`
- For findings: `../audit/project-audit.md`
- For testing approach: `../testing/strategy.md`
