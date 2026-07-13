---
name: "source-command-release-check"
description: "Pre-release checklist для elektronny-gorod. Проверить готовность к публикации."
---

# source-command-release-check

Use this skill when the user asks to run the migrated source command `release-check`.

## Command Template

Ты — DevOps / Release Agent. Активируй skill `agent-skills:shipping-and-launch`.

## Pre-release checklist

Проверь поочерёдно каждый пункт. Любой ❌ блокирует релиз.

### 0. Reconciliation findings↔git (ADR-0010, обязателен)

- [ ] `bash .Codex/hooks/check-audit-reconciliation.sh` — зелёный:
  - каждый `✅ RESOLVED` finding имеет commit в `git log master`;
  - нет `🟢 resolved-in-branch` findings, заявленных как готовые к релизу
    (они **блокируют** релиз до merge);
  - контракты (`AGENTS.md`/`AGENTS.md`/`workflow.md`) без stale-маркеров.

### 1. Quality gates

- [ ] `TESTS_PASS` — `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный.
- [ ] `SECURITY_OK` — все P0 из `docs/audit/security.md` закрыты:
  ```bash
  grep -rE 'LOGGER\..*(token|password|sms|headers|entry\.data)' \
      custom_components/elektronny_gorod/
  # ⇒ должно быть пусто (если есть — это P0 utечка, не релизить)
  ```
  И `diagnostics.py` существует с `TO_REDACT` (S-08/S-16).
- [ ] `REVIEW_OK` — PR review пройден (5 осей).
- [ ] `DOCS_UPDATED` — maintenance rules применены (обе оси, ADR-0010).
- [ ] `AUDIT_DONE` — `docs/audit/project-audit.md` актуален.
- [ ] **quality_scale ≤ gate-confirmed (D-05)** — `manifest:quality_scale`
  не выше реально подтверждённого гейтами уровня. Bronze ⇒ config_flow-тесты
  существуют. Несоответствие без записанного waiver = blocker.

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

Зелёный hassfest + HACS check на текущем HEAD:
```bash
gh run list --branch master --limit 5
```

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
- НЕ делать force-push.
- НЕ скрывать blockers — лучше отложить релиз.
