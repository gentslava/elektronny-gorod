Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-05-22

Source files:
- глобальные skills плагина `agent-skills:*`
- `.claude/commands/**`

Related docs:
- `multi-agent-workflow.md`
- `prompt-library.md`
- `mcp-tools.md`

Used by agents:
- Любой агент при выборе skill для задачи

Quality gates:
- AUDIT_DONE

---

# Skills

В Claude Code / Codex / Cursor «skill» — это переиспользуемая процедура (набор инструкций + ожидаемый output), которая применяется к конкретной задаче. Skills бывают:

- **Глобальные** (из плагинов) — установлены на уровне пользователя.
- **Локальные** (свои) — описаны в `.claude/commands/*.md` или вызываются по контексту.

## Глобальные skills, релевантные этому проекту

| Skill | Когда применять | Почему |
|---|---|---|
| `agent-skills:security-and-hardening` | работа с `http.py`, `config_flow.py:logging`, `helpers.py`, новый `diagnostics.py` | P0 утечки — критический риск проекта |
| `agent-skills:test-driven-development` | переписывание тестов config-flow / coordinator / api | сейчас 0% coverage |
| `agent-skills:code-review-and-quality` | перед коммитом в entity / coordinator | пять осей review |
| `agent-skills:debugging-and-error-recovery` | падающий тест, странное runtime-поведение | systematic debugging |
| `agent-skills:incremental-implementation` | переход на `CoordinatorEntity` (3 платформы) | тонкие vertical slices |
| `agent-skills:spec-driven-development` | новые features (reconfigure flow, repairs) | spec до кода |
| `agent-skills:source-driven-development` | при работе с HA API, в котором есть сомнения | сверка с official docs |
| `agent-skills:context-engineering` | при потере фокуса агентом | curated context |
| `agent-skills:planning-and-task-breakdown` | большие задачи (Bronze→Silver) | разбивка на verifiable шаги |
| `agent-skills:git-workflow-and-versioning` | при подготовке PR | atomic commits |
| `agent-skills:documentation-and-adrs` | принятие архитектурного решения | ADR-шаблон |
| `agent-skills:shipping-and-launch` | подготовка к релизу | pre-launch checklist |

## Локальные skills (этого проекта)

Реализованы как `.claude/commands/*.md`. Запускаются slash-командой в Claude Code.

| Команда | Цель | Файл |
|---|---|---|
| `/audit` | полный аудит по методологии этого репозитория | `.claude/commands/audit.md` |
| `/test-config-flow` | сгенерировать или дополнить тесты config_flow | `.claude/commands/test-config-flow.md` |
| `/security-check` | проверка кода на утечки токенов и headers | `.claude/commands/security-check.md` |
| `/docs-update` | обновить AIDD-документы после правок в коде | `.claude/commands/docs-update.md` |
| `/release-check` | пройти pre-release checklist | `.claude/commands/release-check.md` |

## Когда какой skill использовать

Если задача попадает в одну из колонок ниже — применить соответствующий skill **до** начала работы:

| Тип задачи | Skill |
|---|---|
| Bug fix с очевидным root cause | `agent-skills:debugging-and-error-recovery` |
| Bug fix без понятного root cause | `agent-skills:systematic-debugging` |
| Новый feature | `agent-skills:spec-driven-development` → `incremental-implementation` |
| Рефакторинг | `agent-skills:code-simplification` |
| Изменение API entity | `agent-skills:api-and-interface-design` |
| Security-чувствительный код | `agent-skills:security-and-hardening` |
| Тесты | `agent-skills:test-driven-development` |
| Performance | `agent-skills:performance-optimization` |
| Code review | `agent-skills:code-review-and-quality` |
| Подготовка релиза | `agent-skills:shipping-and-launch` |

## Правила использования skills

1. **Skill — это workflow, а не пожелание.** Если применяешь `security-and-hardening`, проходи все шаги, не сокращай.
2. **Не подменять skill самостоятельным решением.** Если skill говорит «верификация обязательна» — верифицировать.
3. **Skill активируется до начала работы, не после.** Сначала skill (контекст процесса), потом код.
4. **Параллельные skills допустимы.** Например, security + testing для одной задачи — обе релевантны.

## Создание новых локальных skills

Когда добавлять `.claude/commands/<name>.md`:

- Повторяющаяся процедура (≥ 3 раза).
- Чёткие inputs / outputs.
- Имеет связь с quality gate.

Шаблон команды — см. [`templates/`](templates/) (будет добавлен в Full AIDD).

## Next reading

- For commands: `../../.claude/commands/`
- For agents: `../../.claude/agents/`
- For prompts: `prompt-library.md`
- For MCP: `mcp-tools.md`
