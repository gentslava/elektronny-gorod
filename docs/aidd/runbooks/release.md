Status: Active Owner: DevOps / Release Agent Last reviewed: 2026-08-14 (release command linked to canonical `.agents/commands` procedure)

Source files:
- `.github/workflows/release.yaml`
- `.github/workflows/prerelease.yaml`
- `.github/workflows/prerelease-publish.yaml`
- `.github/workflows/prerelease-cleanup.yaml`
- `custom_components/elektronny_gorod/manifest.json`

Related docs:
- `../quality-gates.md`
- `../../../.agents/commands/release-check.md`

Used by agents:
- Release Agent, Validator, maintainer

Quality gates:
- READY_FOR_RELEASE
- REVIEW_OK
- SECURITY_OK

---

# Runbook: Release

Как выпустить новую версию проекта.

## Виды релизов

| Тип | Версия | Когда |
|---|---|---|
| **major** | `X.0.0` | breaking changes или явно зафиксированный крупный продуктовый рубеж; breaking перечисляются отдельно |
| **minor** | `X.Y.0` | новые фичи, не-breaking |
| **patch** | `X.Y.Z` | bug fixes, security fixes (hotfix) |

SemVer. Версия живёт в `manifest.json`, обновляется автоматически workflow при создании GitHub Release.

## Pre-release checklist

Перед созданием release tag убедитесь:

- [ ] `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный.
- [ ] `cd frontend && npm test && npm run typecheck && npm run build` зелёный; собранный bundle не создаёт незакоммиченный diff.
- [ ] `cd frontend && npm audit --omit=dev` без high/critical findings.
- [ ] `cd website && npm test && npm run typecheck && npm run build` зелёный, `npm audit --omit=dev` без high/critical findings. Прогон нужен **на каждом релизе**, а не только при правках `website/**`: версия и минимальная HA подставляются в разметку при сборке из `manifest.json` и `hacs.json`, поэтому подъём версии меняет сайт, не трогая его исходники.
- [ ] Файл `docs/releases/<version>.md` написан — на него ведёт ссылка на сайте, собранная из версии манифеста.
- [ ] `hassfest` зелёный (CI всегда проверяет).
- [ ] `HACS validate` зелёный.
- [ ] Все Critical/Important findings обязательных reviews закрыты.
- [ ] Все обязательные [`quality-gates`](../quality-gates.md) зелёные:
  - TESTS_PASS, SECURITY_PRECHECK_OK, DOCS_UPDATED, HISTORY_CLEAN;
  - CANDIDATE_FROZEN и candidate-bound REVIEW_OK/SECURITY_OK одного tuple;
  - REVIEW_EVIDENCE_PUBLISHED, CI_GREEN, AUDIT_DONE и READY_FOR_RELEASE.
- [ ] CHANGELOG entry и release notes готовы.
- [ ] README обновлён (если есть user-facing изменения).
- [ ] Documentation в `docs/` синхронизирована (maintenance rules).

## Шаги релиза

### Стандартный flow

1. Убедиться, что `master` чистый, синхронизирован с `origin/master`, и зафиксировать release HEAD. Workflow собирает архив именно из `master`, поэтому до завершения job ветку не менять.
2. Создать GitHub Release с тегом `X.Y.Z` **без префикса `v`** через GitHub UI (или `gh release create`). Tag name напрямую записывается в `manifest.json`, поэтому `v4.0.0` недопустим:
   ```bash
   gh release create 4.0.0 \
       --title "v4.0.0 — Домофон действительно стал частью умного дома" \
       --notes-file docs/releases/4.0.0.md
   ```
3. Workflow [`release.yaml`](../../../.github/workflows/release.yaml) автоматически:
   - обновит `manifest.json` с новой версией;
   - запакует в `elektronny_gorod.zip`;
   - прикрепит zip к release;
   - сделает auto-commit обновлённого `manifest.json` в `master`.
4. Дождаться зелёного `Release` job и проверить:
   - asset `elektronny_gorod.zip` появился в release;
   - `manifest.json:version` равен tag;
   - auto-commit GitHub Actions появился в `master`;
   - HACS/hassfest/python-tests на новом HEAD зелёные.
5. Дождаться зелёного workflow `Deploy website` и проверить на опубликованном сайте номер версии и ссылку на release notes. Деплой нужен на каждом релизе: без пересборки сайт продолжит показывать прошлую версию, хотя в исходниках её нет.
6. HACS подхватит release автоматически.

### Hotfix flow

Для security-фиксов (P0 уровень) — ускоренный путь:

1. Создать ветку `hotfix/security-redact-tokens` от `master`.
2. Применить минимальный набор security-фиксов:
   - см. [`audit/security.md`](../../audit/security.md) S-01..S-05;
   - см. [`docs/decisions/0004-token-redaction.md`](../../decisions/0004-token-redaction.md).
3. Тесты + security precheck + docs/history → clean committed freeze.
4. Независимые candidate-bound code/security reviews → PR в `master` → merge.
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

Пререлиз выкатывается в два этапа. [`prerelease.yaml`](../../../.github/workflows/prerelease.yaml) собирает zip в артефакт для **не-draft** PR, меняющих `custom_components/**`; [`prerelease-publish.yaml`](../../../.github/workflows/prerelease-publish.yaml) на событии `workflow_run` публикует его как pre-release с тегом `pr-N`. Разделение вынужденное: для PR из форка GitHub выдаёт read-only токен, и создать релиз из прогона на коде PR невозможно. Отдельного опт-ина для форков нет: GitHub не запускает прогоны внешних контрибьюторов без одобрения мейнтейнера, и требует его заново на каждый push, поэтому без одобрения сборка просто не доходит до успешного завершения и публикация не стартует. Blocked review-only draft пользовательскую сборку не публикует. Прогон публикации в PR checks не виден — смотреть во вкладке Actions.

Одобряя прогон fork-PR, помните, что тем самым вы соглашаетесь раздать эту сборку пользователям HACS с включённым show beta, а не только увидеть результаты тестов — кнопка одобрения общая для всех workflow. Особенно осторожно с PR, который правит `.github/**`: такой PR получает право выполнять произвольные шаги сборки. Отозвать одобрение прогона нельзя, поэтому публикация необратима: если сборку надо убрать, закройте PR (сработает cleanup) либо удалите релиз вручную — `gh release delete pr-N --cleanup-tag`. Отдельно: релиз перед публикацией удаляется и создаётся заново (иначе тег `pr-N` навсегда остался бы на первом собранном коммите), поэтому при сбое на шаге создания PR временно остаётся вообще без пререлиза — лечится повторным запуском сборки.

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
