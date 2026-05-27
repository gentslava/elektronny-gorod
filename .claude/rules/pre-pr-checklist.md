# Rule: Pre-PR checklist (AIDD lifecycle enforcement)

**Применимо к:** все feature/fix PR в этом проекте, перед `gh pr create` или
первым `git push` feature-ветки.

## Правило

🔴 **Запрещено `git push` или `gh pr create`** для feature/fix-ветки **до
прохождения** этого чек-листа. Skill `using-agent-skills` определяет AIDD
lifecycle, этот rule делает его **enforce'нутым** в проекте.

Минимальный pre-PR sequence (соблюдать **порядок**):

```
implementation → tests (TDD) → review → fixes → docs → commit → push → PR
                                ↑       ↑         ↑
                              ОБЯЗАТЕЛЬНО ДО PUSH (не после)
```

## Обязательные шаги

### 0. (Для bug-fix PR) `diagnose-before-fix` — root cause confirmed

**Применяется к:** PR типа `fix(*)` для production-bug (найдено в
production-логах, observed user-pain, runtime issue). См.
[`diagnose-before-fix.md`](diagnose-before-fix.md) для full spec.

🔴 **Запрещено писать fix-код без runtime-evidence root cause.** В PR
body / audit finding должно быть:
- **Hypothesis** — формальная formulation «A → B → C → symptom».
- **Diagnostic evidence** — log excerpt с timestamps + caller chain
  (`traceback.extract_stack()` для lifecycle/async/concurrency bugs)
  + state snapshot external services (go2rtc `/api/streams`, HTTP curl).
- **Active diagnostic step done** — patch с trace logging, runtime
  probe, controlled reproduce. **Не просто «читал лог»**.
- **Root cause явно записан** — «Causal chain: ... → observed symptom».

**Skip allowed:** trivial typo/copy-paste fix, cosmetic/docs PR,
revert (diagnostic был у оригинала).

### 1. `incremental-implementation` + `test-driven-development`

- Тесты для нового behavior **зелёные** локально (`PYTHONPATH=. .venv/bin/pytest tests/ -q`).
- Никаких `@pytest.mark.skip` без причины в комментарии.
- Если фича без тестов — явное обоснование в commit body («тесты в следующем slice [link]»).

### 2. `code-review-and-quality` через subagent

Запустить **до первого push** ветки:

```
Agent(
    description="5-axis code review",
    subagent_type="code-reviewer",
    prompt="Review для PR <branch>: <тема>. Файлы: <list>. Контекст: <бизнес-причина>."
)
```

Применить минимум **P0/P1** findings (P2/P3 — по обстоятельствам).
Если есть **P0 (security/data-loss)** — НЕ push, fix первым.

### 3. `documentation-and-adrs` — sync

Перед push проверить, что новая фича/изменение **отражены** в:

| Файл | Когда обновлять |
|---|---|
| `CHANGELOG.md` `[Unreleased]` | **Всегда** для feat/fix/breaking |
| `docs/audit/project-audit.md` | Новые A-NN findings; закрытие A-NN (status → resolved) |
| `docs/roadmap.md` | Iteration progress / переоценка задач |
| `docs/project/project-map.md` | Новые/удалённые файлы в `custom_components/` или `tests/` |
| `docs/architecture/api-reference.md` | Новые endpoint вызовы (если ещё не задокументированы из research) |
| `docs/architecture/overview.md` | Архитектурные изменения flow / dependencies |
| `docs/decisions/NNNN-*.md` | **Только** если решение архитектурное и сложно откатить (см. ADR template) |
| `docs/architecture/ha-compatibility.md` / `quality-scale.md` | Изменения min HA version, IQS уровня |

Если **много** файлов sync'ится — рассмотреть **отдельный docs-PR** (по аналогии с PR #36 audit+roadmap+project-map после 3.1.0).

### 4. `git-workflow-and-versioning` — audit через subagent

```
Agent(
    description="Git history audit",
    subagent_type="git-historian",
    prompt="Audit PR <branch>: ... HISTORY_CLEAN gate."
)
```

Соблюсти `HISTORY_CLEAN` (см. [`.claude/rules/git-history.md`](git-history.md)):
- Conventional commits.
- Каждый коммит — substantive (не «починка предыдущего»).
- Net-zero pairs (typo+revert, DIAG+remove) — squash или drop.
- Audit ID в commit body.
- Backup-ветка для destructive operations.

### 5. Push + PR

Только сейчас:
- `git push -u origin <branch>`
- `gh pr create --base master ...` с full description (Summary, Files, Test plan, Breaking change).

## Quality gate `PRE_PR_READY`

Считается зелёным если:

0. ✅ (Для bug-fix PR) `ROOT_CAUSE_CONFIRMED` — runtime diagnostic evidence в PR / audit; явно записана causal chain. См. [`diagnose-before-fix.md`](diagnose-before-fix.md).
1. ✅ Tests pass.
2. ✅ Code-reviewer запущен, P0/P1 findings либо применены, либо обоснованы как deferred (с audit-record).
3. ✅ Docs sync (CHANGELOG минимум, прочее по необходимости).
4. ✅ Git-historian audit `HISTORY_CLEAN` passes.
5. ✅ PR description полная (Summary + Files + Test plan).

## Anti-patterns (не делать)

- 🔴 **Fix-by-guess**: hypothesis-driven coding без runtime evidence. Lessons learned: A-66 эксперимент (3 параллельных PR X/Y/Z + закрытые #52/#53 = 5 PR, из которых 4 закрыты без merge) — потеря ~4 часов на «угадывание» вместо 5-минутного `traceback.extract_stack()` patch. См. [`diagnose-before-fix.md`](diagnose-before-fix.md).
- 🔴 **Push first, review later**: создавать PR, потом запускать code-reviewer, потом fixить review fixes отдельным commit'ом. Это плодит шум в истории.
- 🔴 **Docs after merge**: «обновлю audit/CHANGELOG после merge» — это **никогда не происходит** в реальности. Docs должны быть в **том же** PR что фича.
- 🔴 **Skip review для «маленьких» фич**: формально маленькие фичи всё равно могут иметь architectural concerns, security gaps. Subagent занимает 30-90s, экономия от skip — иллюзорна.
- 🔴 **Review только своего кода**: code-reviewer — **независимая** оценка. Если ты сам автор — ты предвзят, нужен внешний взгляд (даже если это другой агент).

## Когда исключения допустимы

- **Pure typo/docs PR** (изменение только `*.md`): review можно skip, но `docs-keeper` audit полезен. Git-historian не нужен.
- **Pure dependency bump** (`hacs.json`, `manifest.json` version): review can be lite.
- **Revert PR**: review был на оригинальном PR; на revert — минимум.

Для всех остальных — full checklist.

## Связь

- [Skill `using-agent-skills`](../../docs/aidd/) — определяет AIDD lifecycle (глобальный)
- [Skill `code-review-and-quality`](../../docs/aidd/) — методология 5-axis review
- [`.claude/rules/git-history.md`](git-history.md) — `HISTORY_CLEAN` gate
- [`.claude/agents/code-reviewer.md`](../agents/code-reviewer.md) — agent spec
- [`.claude/agents/git-historian.md`](../agents/git-historian.md) — agent spec
- [`.claude/agents/docs-keeper.md`](../agents/docs-keeper.md) — agent spec
- [`docs/aidd/quality-gates.md`](../../docs/aidd/quality-gates.md) — `PRE_PR_READY` определение
