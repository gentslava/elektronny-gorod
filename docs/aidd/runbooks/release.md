# Runbook: Release

Как выпустить новую версию проекта.

## Виды релизов

| Тип | Версия | Когда |
|---|---|---|
| **major** | `X.0.0` | breaking changes (config flow VERSION, удаление платформы) |
| **minor** | `X.Y.0` | новые фичи, не-breaking |
| **patch** | `X.Y.Z` | bug fixes, security fixes (hotfix) |

SemVer. Версия живёт в `manifest.json`, обновляется автоматически workflow при создании GitHub Release.

## Pre-release checklist

Перед созданием release tag убедитесь:

- [ ] `pytest tests/ -v` зелёный (когда тесты появятся).
- [ ] `hassfest` зелёный (CI всегда проверяет).
- [ ] `HACS validate` зелёный.
- [ ] Все P0 из [`audit/security.md`](../../audit/security.md) закрыты.
- [ ] Все обязательные [`quality-gates`](../quality-gates.md) зелёные:
  - TESTS_PASS, SECURITY_OK, REVIEW_OK, DOCS_UPDATED, AUDIT_DONE.
- [ ] CHANGELOG entry готов (когда CHANGELOG.md появится — A-35).
- [ ] README обновлён (если есть user-facing изменения).
- [ ] Documentation в `docs/` синхронизирована (maintenance rules).

## Шаги релиза

### Стандартный flow

1. Создать GitHub Release с тегом `vX.Y.Z` через GitHub UI (или `gh release create`):
   ```bash
   gh release create v3.1.0 \
       --title "v3.1.0 — Coordinator pattern" \
       --notes-file CHANGELOG_v3.1.0.md
   ```
2. Workflow [`release.yaml`](../../../.github/workflows/release.yaml) автоматически:
   - обновит `manifest.json` с новой версией;
   - запакует в `elektronny_gorod.zip`;
   - прикрепит zip к release;
   - сделает auto-commit обновлённого `manifest.json` в `master`.
3. HACS подхватит автоматически.

### Hotfix flow

Для security-фиксов (P0 уровень) — ускоренный путь:

1. Создать ветку `hotfix/security-redact-tokens` от `master`.
2. Применить минимальный набор security-фиксов:
   - см. [`audit/security.md`](../../audit/security.md) S-01..S-05;
   - см. [`docs/decisions/0004-token-redaction.md`](../../decisions/0004-token-redaction.md).
3. Тесты + security gate.
4. PR в `master` → review → merge.
5. Создать Release (patch bump).
6. В release notes — **в начале** упомянуть:
   - что было опасно;
   - что пользователю делать (перевыпустить токены, если делились логами).

## Release notes — формат

```markdown
## Что нового

- ...
- ...

## Исправлено

- ...

## Security ⚠️ (если применимо)

Описание утечки/риска + рекомендация перевыпуска токенов.

## Breaking changes (если применимо)

- ...

## Известные проблемы

- ...

## Полный changelog

GitHub auto-generated changelog или вручную.
```

## PR pre-release

Workflow [`prerelease.yaml`](../../../.github/workflows/prerelease.yaml) выкатывает pre-release zip для **каждого** открытого PR с тегом `pr-N`. Используется для тестирования PR пользователями.

Пользователь устанавливает через HACS «Custom repository» → URL PR → ставит `pr-N` версию.

## Rollback

Если релиз сломан:

1. **Не** удалять GitHub Release (это нарушит downloads счётчик у пользователей).
2. Помечать релиз как deprecated в release notes.
3. Выпустить hotfix patch с фиксом.
4. В release notes hotfix-а — **в начале** «не используйте версию X.Y.Z, она содержит баг ...».

## Quality gate

`READY_FOR_RELEASE` — все обязательные gates зелёные + manual checklist выше.

## Next reading

- [`../quality-gates.md`](../quality-gates.md)
- [`../../audit/security.md`](../../audit/security.md)
- [`troubleshooting.md`](troubleshooting.md) — если пользователи жалуются после релиза
