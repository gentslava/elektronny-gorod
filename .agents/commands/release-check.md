---
description: Pre-release checklist для elektronny-gorod. Проверить готовность к публикации.
kind: canonical-agent-command
---

Ты — DevOps / Release Agent. Если доступен, активируй skill `shipping-and-launch`.

**Last reviewed:** 2026-08-11 (ADR-0015 candidate, evidence and CI enforcement)

## Pre-release checklist

Проверь поочерёдно каждый пункт. Любой ❌ блокирует релиз.

### 0. Reconciliation findings↔git (ADR-0010, обязателен)

- [ ] `bash .agents/hooks/check-audit-reconciliation.sh` — зелёный:
  - каждый `✅ RESOLVED` finding имеет commit в `git log master`;
  - нет `🟢 resolved-in-branch` findings, заявленных как готовые к релизу (они **блокируют** релиз до merge);
  - контракты (`AGENTS.md`/`CLAUDE.md`/`workflow.md`) без stale-маркеров.

### 1. Quality gates

- [ ] `TESTS_PASS` — `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный.
- [ ] `SECURITY_PRECHECK_OK` был закрыт до candidate freeze: secret/redaction checks зелёные, известных Critical/Important security findings не осталось.
- [ ] `DOCS_UPDATED` — maintenance rules применены (обе оси, ADR-0010).
- [ ] `HISTORY_CLEAN` был завершён до freeze; после review не было rebase/squash/history rewrite.
- [ ] `CANDIDATE_FROZEN` — PR evidence содержит пустой `git status --short`, merge-base SHA, head SHA и tree SHA clean committed candidate.
- [ ] `REVIEW_OK` — каждый обязательный reviewer:
  - явно указал identity и `Participated in implementation: no`;
  - работал read-only;
  - указал identity, один и тот же base/head/tree и scoped verdict;
  - закрыл все Critical/Important findings на текущем candidate.
- [ ] Routing matrix полная: code-reviewer обязателен; HA/security/QA/docs-AIDD reviewers присутствуют по затронутым областям.
- [ ] `SECURITY_OK` закрыт **post-freeze** независимым security review того же candidate для auth/token/credentials/logs/FCM/privacy diff:
  ```bash
  bash .agents/hooks/check-secret-logs.sh
  # ⇒ Secret log scan passed (иной результат — blocker, не релизить)
  ```
  И `diagnostics.py` существует с `TO_REDACT` (S-08/S-16).
- [ ] После последнего approval не было содержательного commit. Если head/tree менялся, есть новый freeze и новые candidate-bound attestations **каждого** обязательного reviewer; повторный analysis мог быть delta-scoped.
- [ ] Review evidence хранится вне candidate tree. Если evidence было добавлено commit-ом, этот новый candidate заново прошёл всю обязательную matrix.
- [ ] `REVIEW_EVIDENCE_PUBLISHED` — PR содержит durable validation comment для текущего base/head/tree с local gates и всеми reviewer verdicts.
- [ ] `CI_GREEN` — Python Tests, hassfest и HACS зелёные на текущем head; PR Pre-Release зелёный либо корректно skipped как неприменимый. Публикацию пререлиза (`prerelease-publish.yaml`, событие `workflow_run`) в PR checks не видно — проверять отдельно в Actions.
- [ ] PR не является blocked review-only draft; обычный push/ready-for-review PR произошёл после approval либо recovery flow полностью завершён.
- [ ] `AUDIT_DONE` — `docs/audit/project-audit.md` актуален.
- [ ] **quality_scale ≤ gate-confirmed (D-05)** — `manifest:quality_scale` не выше реально подтверждённого гейтами уровня. Bronze ⇒ config_flow-тесты существуют. Несоответствие без записанного waiver = blocker.

### 2. Manifest / HACS

- [ ] `manifest.json` валиден:
  ```bash
  python3 -m json.tool custom_components/elektronny_gorod/manifest.json > /dev/null
  ```
- [ ] `hacs.json` валиден:
  ```bash
  python3 -m json.tool hacs.json > /dev/null
  ```
- [ ] `manifest.json:domain` совпадает с папкой `custom_components/elektronny_gorod/`.

### 3. CI

Привяжи PR к frozen candidate и дождись всех checks именно этого SHA:
```bash
CANDIDATE_SHA=$(git rev-parse HEAD)
PR_HEAD_SHA=$(gh pr view --json headRefOid --jq .headRefOid)
test "$PR_HEAD_SHA" = "$CANDIDATE_SHA"
gh pr checks --watch
```

В итоговом отчёте отдельно подтвердить оба Python Tests jobs, hassfest, HACS и применимый PR Pre-Release вместе с его стадией публикации. SHA mismatch, pending, failure или cancelled не закрывают `CI_GREEN`.

### 4. Migration

Если этот release меняет `VERSION` config-entry:
- [ ] есть соответствующая ветка в `async_migrate_entry` (`__init__.py`).
- [ ] есть regression test для каждого затронутого migration path.

### 5. Breaking changes

- [ ] Если есть — описаны в CHANGELOG / release notes.
- [ ] User action описан (что пользователю делать).

### 6. Security

- [ ] Если фикс затрагивал tokens — release notes содержит **upfront** предупреждение и рекомендацию reauth.
- [ ] Diagnostics `TO_REDACT` актуальный.

### 7. README / docs

- [ ] User-facing изменения отражены в README.
- [ ] AIDD docs синхронизированы.

### 8. Release notes

- [ ] Готовы.
- [ ] Содержат: «Что нового», «Исправлено», «Security» (если применимо), «Breaking» (если применимо).

## Output

```md
## Release readiness
- ✅ <количество> / ❌ <количество>

## Blockers
- ... (если есть)

## Recommendation
- proceed / fix blockers first

## Suggested CHANGELOG
- (черновик entry)
```

## Constraints

- 🔴 НЕ делать `git tag` / `gh release create` без явного approval owner.
- 🔴 Critical/Important review findings нельзя deferred'ить или закрывать waiver-ом.
- 🔴 Self-review implementer-а не закрывает `REVIEW_OK` / `SECURITY_OK`.
- НЕ делать force-push.
- НЕ скрывать blockers — лучше отложить релиз.
