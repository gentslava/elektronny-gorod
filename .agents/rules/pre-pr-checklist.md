# Canonical rule: Pre-PR checklist (AIDD lifecycle enforcement)

**Last reviewed:** 2026-08-11 (ADR-0015 candidate, publication and CI enforcement)

**Применимо к:** все нетривиальные feature/fix/process PR в этом проекте, перед обычным `gh pr create` или первым `git push` feature-ветки.

## Правило

🔴 **Запрещено обычное `git push` или `gh pr create`** для feature/fix-ветки **до прохождения** этого чек-листа. Исключение — явно разрешённые владельцем review-only branch / draft PR, когда независимому человеку нужен remote diff: `REVIEW_OK` остаётся красным, merge/release запрещены. Skill `using-agent-skills` определяет AIDD lifecycle, этот rule делает его **enforce'нутым** в проекте.

Минимальный pre-PR sequence (соблюдать **порядок**):

```
implementation + TDD
  → TESTS_PASS + SECURITY_PRECHECK_OK + DOCS_UPDATED + HISTORY_CLEAN
  → clean committed candidate freeze (base/head/tree)
  → independent code/profile reviews, включая SECURITY_OK
  ├─ findings → fixes → gates → new freeze → all required attestations
  └─ approved → ordinary push / PR → evidence comment → CI_GREEN → merge
```

## Обязательные шаги

### 0. (Для bug-fix PR) `diagnose-before-fix` — root cause confirmed

**Применяется к:** PR типа `fix(*)` для production-bug (найдено в production-логах, observed user-pain, runtime issue). См. [`diagnose-before-fix.md`](diagnose-before-fix.md) для full spec.

🔴 **Запрещено писать fix-код без runtime-evidence root cause.** В PR body / audit finding должно быть:
- **Hypothesis** — формальная formulation «A → B → C → symptom».
- **Diagnostic evidence** — log excerpt с timestamps + caller chain (`traceback.extract_stack()` для lifecycle/async/concurrency bugs)
  + state snapshot external services (go2rtc `/api/streams`, HTTP curl).
- **Active diagnostic step done** — patch с trace logging, runtime probe, controlled reproduce. **Не просто «читал лог»**.
- **Root cause явно записан** — «Causal chain: ... → observed symptom».

**Skip allowed:** trivial typo/copy-paste fix, cosmetic/docs PR, revert (diagnostic был у оригинала).

### 1. Implementation: `incremental-implementation` + `test-driven-development`

- Никаких `@pytest.mark.skip` без причины в комментарии.
- Для bug fix сначала добавить regression test, увидеть ожидаемый RED, затем fix.
- Нельзя откладывать тесты текущего acceptance contract на следующий slice.

### 2. Pre-freeze gates

До freeze завершить:

- `TESTS_PASS`: `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный;
- `SECURITY_PRECHECK_OK`: secret/redaction checks зелёные, известных открытых Critical/Important security findings нет; это ещё **не** `SECURITY_OK`;
- `DOCS_UPDATED`: maintenance rules применены, документация входит в candidate;
- `HISTORY_CLEAN`: commit structure/rebase/squash завершены, последующий rewrite истории не запланирован.

Docs sync проверить по таблице:

| Файл | Когда обновлять |
|---|---|
| `CHANGELOG.md` `[Unreleased]` | Candidate-bound user-facing описание входит в PR; release/merged-state только после merge (ADR-0015) |
| `docs/audit/project-audit.md` | Новые A-NN; до merge — `OPEN` / `remediation-in-review` / допустимый `resolved-in-branch` |
| `docs/roadmap.md` | Iteration progress / переоценка задач |
| `docs/project/project-map.md` | Новые/удалённые файлы в `custom_components/` или `tests/` |
| `docs/architecture/api-reference.md` | Новые endpoint вызовы |
| `docs/architecture/overview.md` | Архитектурные изменения flow / dependencies |
| `docs/decisions/NNNN-*.md` | Архитектурное труднообратимое решение; accepted ADR не редактировать |
| `docs/architecture/ha-compatibility.md` / `quality-scale.md` | Изменения min HA version, IQS уровня |

`HISTORY_CLEAN` проверяет Git Historian по `.agents/roles/git-historian.md`; Claude и Codex используют свои адаптеры. Если отдельная роль недоступна — Validator/root. Требования — в `.agents/rules/git-history.md`:

- conventional и logically-grouped commits;
- нет WIP/DIAG/debug/net-zero цепочек;
- audit ID в commit body, когда применимо;
- рабочее дерево готово к финальному commit/freeze.

### 3. Clean committed candidate freeze

Сначала commit всех implementation/tests/docs/history изменений. Затем получить immutable evidence:

```bash
git status --short
git merge-base <target-ref> HEAD
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
```

`git status --short` должен быть пустым. Адаптер выбирает реальный target ref и локально требуемую command-wrapper политику. Один base/head/tree передаётся всем обязательным reviewers вместе с plan/spec revision.

### 4. Independent code/profile reviews

Для нетривиального diff обязательны:

- независимый `code-reviewer` — всегда;
- `ha-expert` — HA/public contract, entity, config flow, lifecycle, Repairs;
- `security-auditor` — auth/token/credentials/logs/FCM/privacy; его post-freeze verdict закрывает `SECURITY_OK`;
- `qa-engineer` — tests/fixtures/test plan и риск regression;
- docs/AIDD reviewer — нетривиальные process/architecture/source-of-truth changes.

Каждый обязательный reviewer:

- не участвовал в implementation проверяемого diff;
- работает read-only;
- указывает identity, base/head/tree, independence и verdict;
- проверяет exact candidate и не закрывает gate self-review-ом.

Critical/Important findings нельзя deferred'ить: implementer исправляет их, повторяет затронутые pre-freeze gates, commit/freeze и получает **новые candidate-bound attestations от каждого обязательного reviewer**. Повторный analysis может быть delta-scoped, но verdict относится к новому base/head/tree. До публикации review evidence остаётся provisional session transcript. Сразу после ordinary push Validator переносит его в durable PR comment для текущего base/head/tree. Если evidence добавили commit-ом, это новый candidate и весь цикл attestation повторяется.

### 5. Ordinary push + PR

Только сейчас:
- `git push -u origin <branch>`
- `gh pr create --base master ...` с full description (Summary, Files, Test plan, Breaking change).

### 6. Publish evidence + `CI_GREEN`

Validator/root публикует PR comment с tuple, plan/spec revision, local gates и всеми reviewer verdicts. Затем проверяет на текущем head SHA Python Tests, hassfest и HACS; PR Pre-Release — когда workflow применим. До `REVIEW_EVIDENCE_PUBLISHED` и `CI_GREEN` merge запрещён. Новый commit запускает freeze/review/evidence/CI заново (ADR-0015).

## Quality gate `PRE_PR_READY`

Считается зелёным если:

0. ✅ (Для bug-fix PR) `ROOT_CAUSE_CONFIRMED` — runtime diagnostic evidence в PR / audit; явно записана causal chain. См. [`diagnose-before-fix.md`](diagnose-before-fix.md).
1. ✅ `TESTS_PASS`, `SECURITY_PRECHECK_OK`, `DOCS_UPDATED`, `HISTORY_CLEAN`.
2. ✅ `CANDIDATE_FROZEN`: clean committed base/head/tree зафиксирован.
3. ✅ Каждый обязательный независимый reviewer выдал candidate-bound verdict.
4. ✅ `REVIEW_OK` и, где требуется, post-freeze `SECURITY_OK`; открытых Critical/Important findings нет.
5. ✅ Черновик PR description полон (Summary + Files + Test plan); после публикации Validator добавляет durable review evidence comment.

## Anti-patterns (не делать)

- 🔴 **Fix-by-guess**: hypothesis-driven coding без runtime evidence. Lessons learned: A-66 эксперимент (3 параллельных PR X/Y/Z + закрытые #52/#53 = 5 PR, из которых 4 закрыты без merge) — потеря ~4 часов на «угадывание» вместо 5-минутного `traceback.extract_stack()` patch. См. [`diagnose-before-fix.md`](diagnose-before-fix.md).
- 🔴 **Push first, review later**: обычный PR до independent review. Remote review допустим только как явно разрешённый blocked review-only draft.
- 🔴 **Review плавающего diff:** verdict без base/head/tree или после изменения candidate не считается.
- 🔴 **Частичный re-review:** после fix получить новый verdict только от одного reviewer-а, оставив остальные attestation на старом tree.
- 🔴 **Deferred candidate docs**: feature/spec/architecture docs и `CHANGELOG [Unreleased]` нельзя откладывать до merge. После merge меняется только честный merged/release status, а не описание уже проверенного behavior.
- 🔴 **Skip review для «маленьких» фич**: размер diff сам по себе не отменяет architectural/security/lifecycle риск.
- 🔴 **Review только своего кода**: code-reviewer — **независимая** оценка. Если ты сам автор — ты предвзят, нужен внешний взгляд (даже если это другой агент).

## Когда исключения допустимы

- **Pure typo/formatting одного документа:** полную матрицу можно skip; это не относится к process/architecture/source-of-truth migrations.
- **Механический metadata bump без contract/dependency change:** review может быть lite после risk classification.
- **Revert PR:** scope review определяется риском возврата, а не размером diff.

Для всех остальных — full checklist.

## Связь

- Skill `using-agent-skills` — определяет AIDD lifecycle (глобальный)
- Skill `code-review-and-quality` — методология 5-axis review
- `.agents/rules/git-history.md` — `HISTORY_CLEAN` gate
- `.agents/roles/code-reviewer.md` — canonical agent spec
- `.agents/roles/git-historian.md` — canonical agent spec
- `.agents/roles/docs-keeper.md` — canonical agent spec
- `docs/aidd/quality-gates.md` — определения gates
- `docs/decisions/0015-independent-review-candidate.md` — immutable candidate contract
