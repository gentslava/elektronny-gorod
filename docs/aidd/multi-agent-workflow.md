Status: Active
Owner: Lead Architect Agent
Last reviewed: 2026-05-22

Source files:
- `.claude/agents/**`
- `quality-gates.md`

Related docs:
- `../index.md`
- `quality-gates.md`
- `prompt-library.md`
- `skills.md`
- `../../workflow.md`

Used by agents:
- Lead Architect (оркестратор)
- любой агент при понимании своей роли

Quality gates:
- AUDIT_DONE
- PLAN_APPROVED

---

# Multi-agent workflow

Кто за что отвечает и как они взаимодействуют. У проекта **один codeowner**, поэтому «многоагентность» — это виртуальное переключение ролей одним AI-инструментом (Claude Code subagents, Codex skills, Cursor modes).

## Принцип

Один человек + один AI-агент = команда ролей. Каждая роль имеет узкие boundaries, чёткие inputs/outputs и привязана к quality gate.

## Роли

### 1. Lead Architect Agent

| Поле | Значение |
|---|---|
| Когда активируется | в начале проекта, после major change, перед релизом |
| Обязательное чтение | `../index.md`, `../summary.md`, `../audit/project-audit.md`, `../roadmap.md` |
| Outputs | финальная сводка, обновлённый `summary.md`, обновлённый `audit/project-audit.md` |
| Gate | `AUDIT_DONE`, `READY_FOR_RELEASE` |
| Subagent file | `.claude/agents/lead-architect.md` |

### 2. Project Cartographer Agent

| Поле | Значение |
|---|---|
| Когда | при добавлении нового модуля / реорганизации |
| Обязательное чтение | весь репозиторий (файловый scan) |
| Outputs | `../project/project-map.md`, `../project/source-of-truth.md` |
| Gate | `PROJECT_MAP_READY`, `SOURCE_OF_TRUTH_READY` |

### 3. Home Assistant Expert Agent

| Поле | Значение |
|---|---|
| Когда | любая работа с `manifest.json`, `config_flow.py`, entity, coordinator, IQS |
| Обязательное чтение | `../architecture/ha-compatibility.md`, `../architecture/quality-scale.md`, `source-base.md` (HA-секция) |
| Outputs | `ha-compatibility.md`, `quality-scale.md`, HA-разделы в `project-audit.md` |
| Gate | `AUDIT_DONE` |
| Subagent file | `.claude/agents/ha-expert.md` |

### 4. Security & Privacy Agent

| Поле | Значение |
|---|---|
| Когда | работа с `http.py`, `config_flow.py:logging`, `helpers.py:hash_password`, `diagnostics.py` |
| Обязательное чтение | `../audit/security.md`, `../audit/project-audit.md` |
| Outputs | `../audit/security.md`, security-разделы в `project-audit.md` |
| Gate | `SECURITY_OK` |
| Subagent file | `.claude/agents/security-auditor.md` |
| Tools restriction | read-only по умолчанию; правки только в указанных файлах |

### 5. QA / Testing Agent

| Поле | Значение |
|---|---|
| Когда | написание / запуск тестов, обновление test plan |
| Обязательное чтение | `../testing/strategy.md`, `quality-gates.md` (gate TESTS_PASS) |
| Outputs | новые тесты в `tests/`, обновления `strategy.md` |
| Gate | `TESTS_PASS` |
| Subagent file | `.claude/agents/qa-engineer.md` |

### 6. Documentation / AIDD Agent

| Поле | Значение |
|---|---|
| Когда | любое изменение кода требует обновления docs (maintenance rules) |
| Обязательное чтение | `../project/project-map.md#maintenance-rules`, `../../workflow.md` |
| Outputs | обновлённые docs/* |
| Gate | `DOCS_UPDATED` |
| Subagent file | `.claude/agents/docs-keeper.md` |

### 7. DevOps / Release Agent

| Поле | Значение |
|---|---|
| Когда | работа с `.github/workflows/`, релизы, CHANGELOG |
| Обязательное чтение | `../../workflow.md` (раздел Release), `runbooks/release.md` |
| Outputs | CI workflow, release notes |
| Gate | `READY_FOR_RELEASE` |

### 8. Validator Agent

| Поле | Значение |
|---|---|
| Когда | перед merge / релизом |
| Обязательное чтение | весь PR-diff, `quality-gates.md` |
| Outputs | validation report (как комментарий к PR) |
| Gate | проверяет все gates |

### 9. Reverse Engineer Agent

| Поле | Значение |
|---|---|
| Когда | сбор / анализ HAR, обновление `api-reference.md`, diff между версиями приложения |
| Обязательное чтение | [ADR-0006](../decisions/0006-mirror-app-behavior.md), [ADR-0007](../decisions/0007-stateful-emulator-baseline.md), `../architecture/api-reference.md`, `runbooks/har-collection.md`, `../../research/scripts/README.md` |
| Outputs | `../../research/api/*.har` (local-only), обновление `../architecture/api-reference.md` |
| Gate | (нет своего, hand-off в lead-architect / ha-expert при необходимости правок кода) |
| Subagent file | `.claude/agents/reverse-engineer.md` |
| Slash command | `/capture-har <scenario>` |
| Tools restriction | НЕ может писать в `custom_components/`, `tests/`, `manifest.json`, `.github/`, `docs/audit/`, accepted ADR |

## Hand-off pattern

```text
User: «Нашёл утечку токена в логах. Поправь.»
   ↓
Lead Architect:
   - читает summary.md, audit
   - определяет: задача = S-01..S-04 из audit/security.md
   - hand-off → Security & Privacy Agent
   ↓
Security & Privacy Agent:
   - читает audit/security.md
   - применяет skill agent-skills:security-and-hardening
   - вносит правки в http.py, config_flow.py
   - hand-off → QA Agent (нужны тесты на отсутствие логов)
   ↓
QA Agent:
   - дописывает test_logging_no_tokens.py
   - hand-off → Documentation Agent
   ↓
Documentation Agent:
   - помечает A-01..A-04 как resolved в audit/project-audit.md
   - обновляет audit/security.md
   - hand-off → Validator Agent
   ↓
Validator Agent:
   - проверяет: grep на логи токенов → 0
   - проверяет: тесты зелёные
   - проверяет: docs синхронизированы
   - approve → Release
```

## Параллелизация

Когда задачи независимы — запускать агентов параллельно (Claude Code: `Agent` tool с multiple invocations в одном сообщении).

Примеры параллельных задач:
- Security audit + QA audit (читают разные части кода).
- Documentation review + Architecture review (один читает docs, другой читает код).
- Reading config_flow.py + reading coordinator.py (Explore agents).

Когда **нельзя** параллелить:
- Implementation + review одного и того же файла.
- ADR + последующая правка кода по этому ADR.

## Boundaries (повтор)

См. [`../../AGENTS.md#safety-rules--boundaries`](../../AGENTS.md). У каждого агента те же базовые правила, плюс role-specific через `.claude/agents/<role>.md` frontmatter (`tools:` whitelist).

## Output format для каждого агента

Любой агент при завершении задачи:

```md
## Done
- что сделано (1-3 пункта).

## Evidence
- ссылки на файлы, тесты, команды.

## Gates passed
- список Gate-ID.

## Next
- что должно произойти дальше (hand-off / завершение).
```

## Когда роль не нужна

Если изменение тривиально (опечатка, обновление README), не привлекать всю «команду» — одного агента достаточно. Multi-agent — для **нетривиальных** PR.

## Next reading

- For agent files: `../../.claude/agents/`
- For commands: `../../.claude/commands/`
- For prompts: `prompt-library.md`
- For skills: `skills.md`
- For gates: `quality-gates.md`
- For workflow: `../../workflow.md`
