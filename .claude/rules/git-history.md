# Rule: Чистая git история

**Применимо к:** все feature-ветки перед merge в master.

## Правило

🔴 **Запрещено мерджить в master** feature-ветки, содержащие «иттерационный
мусор»: hotfix-цепочки, DIAG-логи добавлены→удалены, «fix typo», revert
собственных коммитов из той же серии. Перед PR-finalization → squash/rebase
до **достаточного** числа осмысленных коммитов.

⚠️ **Две цели одновременно** (равно важные):

1. **Squash/fixup иттерационных hotfix-цепочек** — последовательные исправления
   одной фичи объединяются с базовым коммитом (e.g. `feat(X)` + `fix(X)`).
   Финальная история должна выглядеть так, как будто каждая фича написана
   набело с первой попытки.

2. **Drop коммитов с нулевым net-diff** — особенно DIAG/debug-логи добавлены
   в одном коммите и удалены в следующем (или через N коммитов). Они не
   несут ничего в финальный `git diff master..HEAD` и только захламляют
   историю. Drop всех таких пар целиком.

⚠️ **Цель НЕ «минимум коммитов любой ценой».** Главная метрика — понятная
история без потерь evidence и **без rebase-merge-conflicts**. 8 чистых
коммитов в chronological order значительно лучше чем 5 с переставленными
местами, вызвавшими конфликты. Если конфликт в rebase — это сигнал, что
план был слишком агрессивный → abort, упростить план.

## Quality gate `HISTORY_CLEAN`

Считается зелёным, если:

1. **Каждый коммит ветки несёт substantive change** (не «починка предыдущего»).
2. **Commit messages** соответствуют [conventional commits](https://www.conventionalcommits.org/)
   стилю проекта (`<type>(<scope>): <subject>` + body с «почему»).
3. **CI зелёный на каждом коммите** (можно автоматически проверить через
   `git rebase --exec`).
4. **Diff vs master сохранён** (rebase не привёл к потере/добавлению строк).
5. **Backup-ветка существует** для безопасного rollback: `backup/<branch>-<date>`.

## Когда чистить

- В конце любой нетривиальной работы перед PR creation / готовности к merge.
- После каждой существенной hotfix-серии (>3 hotfix-ов подряд на одну фичу).
- Перед `gh pr ready` / переключением PR из draft в ready-for-review.

## Кто исполняет

- Subagent [`git-historian`](../agents/git-historian.md) — автоматический
  audit + плановый rebase.
- Slash-команда: `/git-cleanup` (TBD).
- Вручную через `git rebase -i master` — если ты уверен в действиях.

## Что НЕ делать

- 🔴 НЕ force-push в `master` / `main` / `dev` (даже с `--force-with-lease`).
- 🔴 НЕ амендить коммиты, которые уже в master (только в feature-ветке).
- 🔴 НЕ использовать `--no-verify` / `--no-gpg-sign` при reword.
- 🔴 НЕ объединять коммиты, если их diff конфликтует семантически (теряется
  evidence о промежуточных решениях).
- 🔴 НЕ удалять коммиты с уникальной информацией в commit message только ради
  «красивости».
- 🔴 НЕ делать reorder коммитов, трогающих одни и те же файлы — это главный
  источник rebase-merge-conflicts. Проверяй пересечение файлов через
  `git show --stat` перед reorder. Если есть пересечение — оставляй
  chronological order.
- 🔴 НЕ разрешать rebase-merge-conflicts вручную внутри `git rebase` —
  это звонок что план неверный. `git rebase --abort`, пересмотри план
  менее агрессивно (меньше squash, больше keep-as-is).

## Типичные anti-patterns в коммитах

```
❌  fix: типо
❌  WIP
❌  Update file
❌  Возврат к предыдущей версии
❌  asdf
❌  Merge branch 'master' into feat/X  (если не нужен — сделай rebase)
```

## Образцовые коммиты для проекта

```
✅  feat(entities): Bronze IQS entity polish (slice 3c)

    Закрывает A-12, A-13, A-14, A-34 — последний слайс для Bronze
    Integration Quality Scale. См. ADR-0002 §Entity naming.

    - Stable unique_id (A-12): camera, lock через entity_migration.
    - has_entity_name + device_info (A-13): sensor translation_key.
    - Sensor balance long-term statistics (A-14): MONETARY, TOTAL, RUB.
    - manifest (A-34): quality_scale=bronze, integration_type=service.

    Co-Authored-By: ...
```

## Связь

- [`.claude/agents/git-historian.md`](../agents/git-historian.md) — исполнитель.
- [`docs/aidd/quality-gates.md`](../../docs/aidd/quality-gates.md) — gate `HISTORY_CLEAN`.
- [`AGENTS.md`](../../AGENTS.md) §git contract.
- [Conventional Commits](https://www.conventionalcommits.org/).
