---
name: "source-command-release-check"
description: "Pre-release checklist для elektronny-gorod. Проверить готовность к публикации."
---

# source-command-release-check

Use this skill when the user asks to run the migrated source command `release-check`.

## Command Template

Ты — DevOps / Release Agent. Активируй skill `shipping-and-launch`.

## Pre-release checklist

Проверь поочерёдно каждый пункт. Любой ❌ блокирует релиз.

### 0. Reconciliation findings↔git (ADR-0010, обязателен)

- [ ] `bash .codex/hooks/check-audit-reconciliation.sh` — зелёный:
  - каждый `✅ RESOLVED` finding имеет commit в `git log master`;
  - нет `🟢 resolved-in-branch` findings, заявленных как готовые к релизу (они **блокируют** релиз до merge);
  - контракты (`AGENTS.md`/`CLAUDE.md`/`workflow.md`) без stale-маркеров.

### 1. Quality gates

- [ ] `TESTS_PASS` — `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный.
- [ ] `SECURITY_PRECHECK_OK` — локальный secret scanner зелёный и все известные Critical/Important findings устранены до freeze:
  ```bash
  bash .codex/hooks/check-secret-logs.sh
  ```
  И `diagnostics.py` существует с `TO_REDACT` (S-08/S-16).
- [ ] `HISTORY_CLEAN` — substantive history готова до freeze; после review не было rebase/squash/history rewrite.
- [ ] `CANDIDATE_FROZEN` — clean base/head/tree tuple и spec/plan revision зафиксированы.
- [ ] `REVIEW_OK` — каждый обязательный reviewer независим от implementation, работал read-only, указал тот же base/head/tree и закрыл Critical/Important.
- [ ] `SECURITY_OK` — независимый security reviewer одобрил exact tuple, если diff security-sensitive.
- [ ] После изменения candidate каждый обязательный reviewer выдал новый verdict; прежние PR evidence и CI не переиспользуются.
- [ ] `REVIEW_EVIDENCE_PUBLISHED` — PR comment содержит tuple, plan/spec, local gates, reviewer identities/independence/scopes/verdicts.
- [ ] `DOCS_UPDATED` — maintenance rules применены (обе оси, ADR-0010).
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

### 3. Publication evidence и CI

До merge обязательны `REVIEW_EVIDENCE_PUBLISHED` и `CI_GREEN` на текущем HEAD. PR comment должен содержать tuple, reviewer identities/verdicts и local gates. Затем проверить required GitHub checks:
```bash
CANDIDATE_SHA=$(git rev-parse HEAD)
PR_HEAD_SHA=$(gh pr view --json headRefOid --jq .headRefOid)
test "$PR_HEAD_SHA" = "$CANDIDATE_SHA"
gh pr checks --watch
```

В отчёте отдельно подтвердить оба Python Tests jobs, hassfest, HACS и применимый PR Pre-Release. SHA mismatch, pending, failure или cancelled не закрывают `CI_GREEN`.

### 4. Migration

Если этот release меняет `VERSION` config-entry:
- [ ] есть соответствующая ветка в `async_migrate_entry` (`__init__.py`).
- [ ] тест миграции (`async_migrate_entry` v1→2→3 — см. finding A-73).

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
- 🔴 Critical/Important findings нельзя deferred'ить или закрывать waiver-ом.
- 🔴 Self-review implementer-а не закрывает `REVIEW_OK` / `SECURITY_OK`.
- НЕ делать force-push.
- НЕ скрывать blockers — лучше отложить релиз.
