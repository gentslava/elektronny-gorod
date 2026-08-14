Status: Active Owner: Documentation / AIDD Agent Last reviewed: 2026-08-14 (local command procedures consolidated under `.agents/commands`)

Source files:
- доступные global/plugin skills текущего tool
- `.agents/commands/**`
- `.agents/skills/source-command-*/SKILL.md`

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
- **Локальные** (свои) — описаны в `.agents/commands/*.md` и открываются через tool-specific adapters.

## Глобальные skills, релевантные этому проекту

| Skill | Когда применять | Почему |
|---|---|---|
| `security-and-hardening` | работа с `http.py`, `config_flow.py:logging`, `helpers.py`, `diagnostics.py`, `fcm.py`, credentials/tokens | P0 утечки и log-amplification — критический риск проекта |
| `test-driven-development` | любое изменение поведения или bug-fix в config-flow / coordinator / api / FCM | regression сначала воспроизводится тестом; live baseline — в testing strategy |
| `code-review-and-quality` | независимым reviewer-ом clean committed candidate после tests/security prechecks/docs/history cleanup | пять осей review; self-review не закрывает gate; fixes создают новый candidate |
| `debugging-and-error-recovery` | падающий тест, странное runtime-поведение | systematic debugging |
| `incremental-implementation` | переход на `CoordinatorEntity` (3 платформы) | тонкие vertical slices |
| `spec-driven-development` | новые features (reconfigure flow, repairs) | spec до кода |
| `source-driven-development` | при работе с HA API, в котором есть сомнения | сверка с official docs |
| `context-engineering` | при потере фокуса агентом | curated context |
| `planning-and-task-breakdown` | большие задачи (Bronze→Silver) | разбивка на verifiable шаги |
| `git-workflow-and-versioning` | при подготовке PR | atomic commits |
| `documentation-and-adrs` | принятие архитектурного решения | ADR-шаблон |
| `shipping-and-launch` | подготовка к релизу | pre-launch checklist |

## Локальные skills (этого проекта)

Реализованы один раз в `.agents/commands/*.md`. Claude открывает их slash-командами из `.claude/commands/`, Codex — matching skills из `.agents/skills/source-command-*`.

| Команда | Цель | Файл |
|---|---|---|
| `/audit` | полный аудит по методологии этого репозитория | `.agents/commands/audit.md` |
| `/capture-har` | собрать HAR целевого сценария | `.agents/commands/capture-har.md` |
| `/test-config-flow` | сгенерировать или дополнить тесты config_flow | `.agents/commands/test-config-flow.md` |
| `/security-check` | проверка кода на утечки токенов и headers | `.agents/commands/security-check.md` |
| `/docs-update` | обновить AIDD-документы после правок в коде | `.agents/commands/docs-update.md` |
| `/git-cleanup` | проверить и безопасно очистить историю | `.agents/commands/git-cleanup.md` |
| `/release-check` | пройти pre-release checklist | `.agents/commands/release-check.md` |

## Когда какой skill использовать

Если задача попадает в одну из колонок ниже — применить соответствующий skill **до** начала работы:

| Тип задачи | Skill |
|---|---|
| Bug fix с очевидным root cause | `debugging-and-error-recovery` |
| Bug fix без понятного root cause | `systematic-debugging` |
| Новый feature | `spec-driven-development` → `incremental-implementation` |
| Рефакторинг | `code-simplification` |
| Изменение API entity | `api-and-interface-design` |
| Security-чувствительный код | `security-and-hardening` |
| Тесты | `test-driven-development` |
| Performance | `performance-optimization` |
| Code review | `code-review-and-quality` |
| Подготовка релиза | `shipping-and-launch` |

## Правила использования skills

1. **Skill — это workflow, а не пожелание.** Если применяешь `security-and-hardening`, проходи все шаги, не сокращай.
2. **Не подменять skill самостоятельным решением.** Если skill говорит «верификация обязательна» — верифицировать.
3. **Skill активируется до начала работы, не после.** Сначала skill (контекст процесса), потом код.
4. **Параллельные skills допустимы.** Например, security + testing для одной задачи — обе релевантны.

## Создание новых локальных skills

Когда добавлять `.agents/commands/<name>.md` и короткие tool adapters:

- Повторяющаяся процедура (≥ 3 раза).
- Чёткие inputs / outputs.
- Имеет связь с quality gate.

Шаблон команды — см. [`templates/`](templates/) (будет добавлен в Full AIDD).

## Next reading

- For commands: `../../.agents/commands/`
- For agents: `../../.agents/roles/`
- For prompts: `prompt-library.md`
- For MCP: `mcp-tools.md`
