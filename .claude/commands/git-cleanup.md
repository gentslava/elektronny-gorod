---
description: Запустить git-historian для аудита и чистки git истории текущей feature-ветки перед merge.
---

Цель: схлопнуть «иттерационные» коммиты (hotfix-цепочки, DIAG-логи, typo-
правки) в логичные substantive единицы. После — клонированная история выглядит
так, как будто человек писал её сразу набело.

## Шаги

1. Прочитай [`.claude/agents/git-historian.md`](../agents/git-historian.md) —
   контракт агента.
2. Прочитай [`.claude/rules/git-history.md`](../rules/git-history.md) —
   критерии gate `HISTORY_CLEAN`.
3. Запусти subagent через `subagent_type=git-historian` с задачей:
   - проанализировать текущую ветку `git log --oneline master..HEAD`,
   - предложить план rebase (squash / fixup / reword / drop),
   - **спросить подтверждение** у user'а перед выполнением (не делать rebase
     автоматически без явного approval),
   - после rebase — verify diff vs master + force-push (если ветка пушена).

## Что обязательно сделать перед rebase

- ✅ Создать backup-ветку: `git branch backup/<branch>-$(date +%Y-%m-%d)`.
- ✅ Убедиться что в ветку не пушены чужие коммиты после твоего последнего pull.
- ✅ Все локальные изменения закоммичены или stashed.

## Что НЕЛЬЗЯ

- 🔴 Force-push в `master` / `main` / `dev`.
- 🔴 Менять author/email коммитов.
- 🔴 Изменять коммиты в master.
- 🔴 `--no-verify` / `--no-gpg-sign`.

## Output

После выполнения — отчёт по шаблону из git-historian:
- Before: N коммитов
- Plan table
- Verification (backup branch, diff idempotent)
- Push status

## Связь

- [`.claude/agents/git-historian.md`](../agents/git-historian.md)
- [`.claude/rules/git-history.md`](../rules/git-history.md)
- [`docs/aidd/quality-gates.md`](../../docs/aidd/quality-gates.md) — `HISTORY_CLEAN`.
