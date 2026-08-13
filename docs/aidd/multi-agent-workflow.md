Status: Active Owner: Lead Architect Agent Last reviewed: 2026-08-11 (default subagent execution, independent review and ADR-0015 publication/evidence ownership clarified after A-97)

Source files:
- `.claude/agents/**`
- `.codex/agents/**`
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

Кто за что отвечает и как они взаимодействуют. У проекта **один codeowner**, но инструмент может запускать несколько изолированных subagents. Переключение skills/modes внутри одного implementer-контекста остаётся self-review и не создаёт независимого reviewer-а.

## Принцип

Один человек + agentic tool = команда ролей. Каждая роль имеет узкие boundaries, чёткие inputs/outputs и привязана к quality gate. Переключение роли внутри того же implementer-контекста подходит для self-review, но **не считается независимым review**. Когда subagents доступны, reviewer запускается с отдельным контекстом; иначе `REVIEW_OK` требует human reviewer.

## Default execution policy

- Нетривиальный утверждённый план выполняется subagent-driven, если платформа предоставляет subagents. Inline — только explicit user choice или техническая недоступность subagents.
- После рекомендации короткое подтверждение «го» / «да» / «начинай» принимает рекомендованный режим; оркестратор не переинтерпретирует его как inline.
- До начала implementation план фиксирует approval revision, concrete ownership slices и reviewer matrix.
- После implementation + tests/security prechecks/docs/history cleanup замораживается clean committed candidate. Обязательны independent `code-reviewer`; `ha-expert` для HA lifecycle/Repairs/config/entity, `security-auditor` для auth/token/FCM и `qa-engineer` для tests/fixtures/test plan.
- Reviewers работают read-only по одному exact base/head/tree candidate. Implementer исправляет findings, повторяет затронутые gates, замораживает новый candidate и получает новую tuple-bound аттестацию каждого обязательного reviewer-а; unchanged scope допускает delta-review.
- После approvals Validator публикует ordinary PR, переносит provisional transcript в durable candidate-bound PR comment и ждёт `CI_GREEN` до merge.

## Candidate freeze

Evidence для `CANDIDATE_FROZEN`:

```bash
git status --short
git merge-base <target-ref> HEAD
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
```

Первый вывод пуст; остальные три значения записываются в review evidence. Любой содержательный commit после verdict инвалидирует все обязательные candidate approvals. SHA здесь — immutable evidence конкретного review (ADR-0015), не live-state документа. После нового candidate каждый обязательный reviewer выдаёт новый tuple-bound verdict; unchanged scope можно подтвердить короткой delta-attestation. Конкретный инструмент подставляет целевую ветку и обязательный command wrapper, если он задан локальным окружением.

Обычный push/PR выполняется после локальных reviews. Узкое исключение для human review — явно разрешённая review-only branch/draft PR с незакрытым `REVIEW_OK`, запретом merge/release и последующим тем же freeze/re-review циклом. Уже открытый PR восстанавливается через этот flow, а не получает self-approval постфактум. После ordinary push Validator публикует review evidence для текущего tuple в PR comment. Это канонический журнал до merge; session transcript до публикации — только provisional evidence. Новый candidate требует нового comment и CI run (ADR-0015).

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
| Когда | любая работа с `manifest.json`, `config_flow.py`, entity, coordinator, Repairs/issue registry, FCM lifecycle, IQS |
| Обязательное чтение | `../architecture/ha-compatibility.md`, `../architecture/quality-scale.md`, `source-base.md` (HA-секция) |
| Outputs | `ha-compatibility.md`, `quality-scale.md`, HA-разделы в `project-audit.md` |
| Gate | `AUDIT_DONE` |
| Subagent file | `.claude/agents/ha-expert.md` |
| Final review mode | read-only по base/head/tree; fixes возвращаются implementer-у |

### 4. Security & Privacy Agent

| Поле | Значение |
|---|---|
| Когда | работа с `http.py`, `config_flow.py:logging`, `helpers.py:hash_password`, `diagnostics.py`, `fcm.py`, credentials/tokens/headers |
| Обязательное чтение | `../audit/security.md`, `../audit/project-audit.md` |
| Outputs | `../audit/security.md`, security-разделы в `project-audit.md` |
| Gate | `SECURITY_OK` |
| Subagent file | `.claude/agents/security-auditor.md` |
| Final review mode | read-only по base/head/tree; implementation mode может использовать разрешённые writes |

### 5. QA / Testing Agent

| Поле | Значение |
|---|---|
| Когда | написание / запуск тестов, обновление test plan |
| Обязательное чтение | `../testing/strategy.md`, `quality-gates.md` (gate TESTS_PASS) |
| Outputs | новые тесты в `tests/`, обновления `strategy.md` |
| Gate | `TESTS_PASS` |
| Subagent file | `.claude/agents/qa-engineer.md` |
| Final review mode | read-only по base/head/tree; проверка acceptance и test anti-patterns |

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
| Outputs | агрегированный validation report; после push — durable PR comment текущего tuple |
| Gate | проверяет все gates, закрывает `REVIEW_EVIDENCE_PUBLISHED` и `CI_GREEN` |

Validator — обязанность root/lead orchestrator во всех поддерживаемых инструментах; отдельный adapter не требуется. Он собирает identities/verdicts, не подменяя независимых reviewers, и публикует evidence после обычного push.

### 9. Git Historian Agent

| Поле | Значение |
|---|---|
| Когда | после implementation/docs и до candidate freeze; при hotfix/WIP/diag history |
| Обязательное чтение | `.claude/rules/git-history.md`, ADR-0015, `quality-gates.md` |
| Outputs | history audit, backup-ref evidence при rewrite, exact final tree |
| Gate | `HISTORY_CLEAN` |
| Subagent files | `.claude/agents/git-historian.md`, `.codex/agents/git-historian.toml` |

Если отдельная роль недоступна, те же проверки выполняет Validator/root. Любой history rewrite инвалидирует candidate и все прежние approvals.

### 10. Reverse Engineer Agent

| Поле | Значение |
|---|---|
| Когда | сбор / анализ HAR, обновление `api-reference.md`, diff между версиями приложения |
| Обязательное чтение | [ADR-0006](../decisions/0006-mirror-app-behavior.md), [ADR-0007](../decisions/0007-stateful-emulator-baseline.md), `../architecture/api-reference.md`, `runbooks/har-collection.md`, `../../research/scripts/README.md` |
| Outputs | `../../research/api/*.har` (local-only), обновление `../architecture/api-reference.md` |
| Gate | (нет своего, hand-off в lead-architect / ha-expert при необходимости правок кода) |
| Subagent file | `.claude/agents/reverse-engineer.md` |
| Slash command | `/capture-har <scenario>` |
| Tools restriction | НЕ может писать в `custom_components/`, `tests/`, `manifest.json`, `.github/`, `docs/audit/`, accepted ADR |

### 11. Code Reviewer Agent

| Поле | Значение |
|---|---|
| Когда | после tests/security prechecks/docs/history cleanup и candidate freeze; обязательно перед обычным push / ready-for-review PR / merge нетривиального изменения |
| Обязательное чтение | `../../conventions.md`, `../audit/project-audit.md`, `../audit/security.md`, `../decisions/*.md`, `../../.claude/rules/*` |
| Outputs | review report по [`templates/review-report.template.md`](templates/review-report.template.md) |
| Gate | `REVIEW_OK` |
| Subagent file | `.claude/agents/code-reviewer.md` |
| Tools restriction | **read-only** — не пишет код сам |
| Skills | `agent-skills:code-review-and-quality` (обязательно), `agent-skills:security-and-hardening` |

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
   - помечает A-01..A-04 как remediation-in-review в audit/project-audit.md
   - обновляет audit/security.md
   - hand-off → Validator Agent
   ↓
Validator Agent:
   - проверяет: grep на логи токенов → 0
   - проверяет: тесты зелёные
   - проверяет: docs синхронизированы
   - проверяет: history clean
   - фиксирует clean committed base/head/tree candidate
   - hand-off → независимые Code/Security/QA reviewers
   ↓
Independent reviewers:
   - проверяют один base/head/tree read-only
   - findings → implementer → affected gates → новый freeze
   - каждый обязательный reviewer переиздаёт verdict для нового tuple
   - approve → REVIEW_OK + SECURITY_OK
   ↓
Validator/root:
   - выполняет ordinary push/PR
   - публикует tuple-bound evidence comment
   - ждёт CI_GREEN текущего head
   ↓
Merge owner:
   - после всех gates разрешает merge
   - только после merge переводит findings в RESOLVED
```

## Параллелизация

Когда задачи независимы — запускать агентов параллельно (Claude Code: `Agent` tool с multiple invocations в одном сообщении).

Примеры параллельных задач:
- Security audit + QA audit (читают разные части кода).
- Documentation review + Architecture review (один читает docs, другой читает код).
- Reading config_flow.py + reading coordinator.py (Explore agents).
- Финальные code / HA / security / QA reviews одного frozen base/head/tree candidate.

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

Если изменение тривиально (опечатка, форматирование, механическая правка одного документа), не привлекать всю «команду» — одного агента достаточно. Multi-agent обязателен для risk-bearing изменений production behavior/lifecycle, security/privacy, persistent data, HA/public contracts, CI/release и связанных миграций источников правды (ADR-0015).

## Next reading

- For agent files: `../../.claude/agents/`
- For commands: `../../.claude/commands/`
- For prompts: `prompt-library.md`
- For skills: `skills.md`
- For gates: `quality-gates.md`
- For workflow: `../../workflow.md`
