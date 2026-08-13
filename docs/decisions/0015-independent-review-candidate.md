# ADR-0015: Неизменяемый candidate и независимый review

- **Status:** accepted
- **Date:** 2026-08-11
- **Owner:** [@gentslava](https://github.com/gentslava) + Lead Architect Agent
- **Supersedes:** ADR-0010 §2–4 в части branch-state, live gate state, review waiver и размещения test baseline

## Context

В PR #78 product fix, process-инфраструктура и несколько последовательных уточнений review workflow оказались в одной ветке. Self-review можно было ошибочно принять за независимый verdict, разные reviewers проверяли разные SHA, а локальные gates смешивались с ещё не существующим remote CI. Точные test counts также копировались между несколькими документами и расходились.

Нужен один cross-tool контракт для человека, Claude и Codex. Он должен однозначно определять утверждение плана, immutable candidate, независимость reviewers, повторную аттестацию после исправлений, публикацию evidence и единственный источник live test baseline.

## Decision

### 1. План фиксирует scope и execution mode

До реализации полный план содержит scope, acceptance criteria, execution mode, implementer ownership и reviewer matrix. `PLAN_APPROVED` хранит approver, дату, revision плана и ссылку на evidence. Короткое «го», «да» или «начинай» закрывает gate только как прямой ответ на уже предъявленный полный план и одновременно принимает явно рекомендованный execution mode.

Независимый review обязателен при изменении production-поведения, lifecycle, security/privacy boundary, persistent data, HA/public contract, CI/release и при нетривиальной миграции нескольких источников правды. Механическая правка одного документа не требует полной reviewer matrix.

### 2. Local gates завершаются до freeze

Порядок до candidate freeze:

```text
implementation + TDD
  → TESTS_PASS
  → SECURITY_PRECHECK_OK
  → DOCS_UPDATED
  → HISTORY_CLEAN
  → clean committed candidate
```

`TESTS_PASS` подтверждает полный локальный pytest и остальные доступные проверки из test plan. Он не зависит от GitHub Actions.

`SECURITY_PRECHECK_OK` — локальные secret/redaction checks и устранение известных Critical/Important security findings. Это не независимый security verdict.

Feature/spec/plan/architecture docs и `CHANGELOG.md` `[Unreleased]` входят в candidate. Они описывают pending behavior и не утверждают его доступность в `master`.

### 3. Candidate имеет точную identity

Candidate определяется четырьмя значениями:

- merge-base SHA;
- head SHA;
- tree SHA;
- пустой `git status --short`.

Все финальные reviewers проверяют один tuple и работают read-only. Review evidence хранится вне candidate tree, поэтому само evidence не меняет SHA.

Любой содержательный commit создаёт новый candidate. Каждый обязательный reviewer выдаёт новый verdict или явную candidate-bound re-attestation на новый tuple. Проверка может быть delta-scoped и переиспользовать object IDs неизменившихся blobs, но итоговый verdict всегда относится ко всему новому candidate.

### 4. Независимые reviews выполняются после freeze

После freeze обязательны `REVIEW_OK` и профильные reviews из утверждённой matrix. Один независимый reviewer может закрыть несколько компетенций, если его квалификация и scope записаны явно.

Для auth/token/credentials/crypto/diagnostics/FCM-sensitive diff отдельный read-only security reviewer закрывает `SECURITY_OK` на exact tuple. Implementer и self-review не могут закрывать независимые gates.

Findings возвращаются implementer-у. После исправления повторяются затронутые local gates, создаётся новый tuple и все обязательные reviewers переиздают candidate-bound verdict или re-attestation.

### 5. Publication, durable evidence и remote CI идут после approvals

После candidate-bound approvals разрешены обычный push и PR. Validator/root сразу публикует в PR durable validation comment:

- base/head/tree candidate;
- plan/spec revision;
- identity, independence, scope и verdict каждого обязательного reviewer;
- результаты local gates.

Этот комментарий закрывает `REVIEW_EVIDENCE_PUBLISHED` и является каноническим off-tree журналом до merge. Новый candidate требует нового комментария; старый остаётся историческим evidence.

`CI_GREEN` подтверждает required GitHub checks на том же head SHA: Python Tests, hassfest и HACS. PR Pre-Release проверяется, когда workflow применим; skipped job не считается failure.

Полный lifecycle:

```text
plan approval
  → implementation + local gates
  → immutable candidate freeze
  → independent candidate-bound reviews
  → ordinary push / PR
  → REVIEW_EVIDENCE_PUBLISHED + CI_GREEN
  → merge
  → merged-state reconciliation / release
```

### 6. Review и publication gates не заменяются waiver-ом

Для нетривиального diff нельзя waive:

- `REVIEW_OK`;
- обязательные профильные reviews, включая `SECURITY_OK`;
- `REVIEW_EVIDENCE_PUBLISHED`;
- `CI_GREEN`.

Владелец может разрешить review-only branch или draft PR, если remote diff нужен внешнему reviewer-у. При этом gates остаются красными, merge и release запрещены.

### 7. Branch-state и test baseline имеют одного владельца

До merge finding остаётся `OPEN`, `REMEDIATION-IN-REVIEW` либо после всех candidate approvals — `resolved-in-branch`. Только после merge разрешены `✅ RESOLVED`, release section вместо `[Unreleased]` и утверждения о доступности в `master`.

Единственный источник текущего aggregate test baseline и состава suite — `docs/testing/strategy.md`.

- `project-audit.md` хранит status и историческое evidence findings, но не второй live baseline;
- `summary.md`, quality gates, project map и agent profiles ссылаются на testing strategy и не копируют меняющийся count;
- изменение CI/test baseline обновляет testing strategy; остальные документы меняются только вместе со своим контрактом или finding.

SHA допустимы в candidate-bound review report, PR evidence и audit reconciliation. Обзорные документы не используют их как копию «текущего HEAD».

### 8. Process remediation отделяется от product fix

AIDD/process remediation оформляется отдельным changeset или отдельным PR, когда это практически возможно. Если incident recovery временно требует одной ветки, process scope всё равно получает отдельные commits и собственный docs/architecture review.

## Consequences

### Positive

- Все approvals относятся к одному неизменяемому candidate.
- Self-review нельзя выдать за независимый gate.
- Локальная проверка не зависит от будущего CI run.
- Review evidence имеет durable cross-tool место и не меняет candidate.
- Test baseline и branch-state больше не размножаются по документации.
- Product fixes и развитие AIDD проще ревьюить независимо.

### Negative

- После содержательного fix нужен новый tuple и re-attestation всех обязательных reviewers.
- Между approval и merge есть явный post-push этап.
- Первый опубликованный PR может временно оставаться blocked.

### Mitigation

- Re-attestation использует object IDs и подробный review только нового delta.
- Один квалифицированный независимый reviewer может закрыть несколько ролей.
- Freeze evidence собирается короткими read-only git-командами.

## Alternatives considered

1. **Всегда запрещать push до review.** Отклонено: внешний reviewer не увидит локальный diff; draft PR безопаснее скрытого обхода.
2. **Оставить self-review fallback.** Отклонено: это исходная причина A-97.
3. **Сохранять approvals старого SHA для незатронутых ролей.** Отклонено: тогда итоговый candidate снова получает approvals от разных tuples.
4. **Хранить review report в репозитории.** Отклонено: evidence commit меняет проверяемый tree и запускает бесконечную re-attestation.
5. **Копировать test count в audit и summary.** Отклонено как источник drift.

## Supersedes / Superseded by

- supersedes: ADR-0010 §2–4 в перечисленных выше частях;
- superseded by: —.

## Notes

- Audit finding: A-97.
- Process contract: `AGENTS.md`, `workflow.md`, `docs/aidd/multi-agent-workflow.md`, `docs/aidd/quality-gates.md`.
- Этот ADR не меняет production-код интеграции.
