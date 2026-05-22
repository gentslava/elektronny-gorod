---
description: Pre-release checklist для elektronny-gorod. Проверить готовность к публикации.
allowed-tools: Read, Grep, Glob, Bash
---

Ты — DevOps / Release Agent. Активируй skill `agent-skills:shipping-and-launch`.

## Pre-release checklist

Проверь поочерёдно каждый пункт. Любой ❌ блокирует релиз.

### 1. Quality gates

- [ ] `TESTS_PASS` — `pytest tests/ -v` зелёный (если тесты уже переписаны).
- [ ] `SECURITY_OK` — все P0 из `docs/audit/security.md` закрыты:
  ```bash
  grep -rE 'LOGGER\..*(token|password|sms|headers|entry\.data)' \
      custom_components/elektronny_gorod/
  # ⇒ должно быть пусто (если есть — это P0 utечка, не релизить)
  ```
- [ ] `REVIEW_OK` — PR review пройден (5 осей).
- [ ] `DOCS_UPDATED` — maintenance rules применены.
- [ ] `AUDIT_DONE` — `docs/audit/project-audit.md` актуален.

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

Если этот release меняет `VERSION` в `config_flow.py`:
- [ ] есть соответствующая ветка в `async_migrate_entry`.
- [ ] тест миграции (когда тесты будут).

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
