# Canonical rule: Чистая git история

**Применимо к:** все нетривиальные feature-ветки до candidate freeze и merge.

## Правило

🔴 **Запрещено мерджить в master** feature-ветки, содержащие «иттерационный мусор»: hotfix-цепочки, DIAG-логи добавлены→удалены, «fix typo», revert собственных коммитов из той же серии. До `CANDIDATE_FROZEN` → squash/rebase до **достаточного** числа осмысленных коммитов.

⚠️ **Две цели одновременно** (равно важные):

1. **Squash/fixup иттерационных hotfix-цепочек** — последовательные исправления одной фичи объединяются с базовым коммитом (e.g. `feat(X)` + `fix(X)`). Финальная история должна выглядеть так, как будто каждая фича написана набело с первой попытки.

2. **Drop коммитов с нулевым net-diff** — особенно DIAG/debug-логи добавлены в одном коммите и удалены в следующем (или через N коммитов). Они не несут ничего в финальный `git diff <target-ref>..HEAD` и только захламляют историю. Drop всех таких пар целиком.

⚠️ **Цель НЕ «минимум коммитов любой ценой».** Главная метрика — понятная история без потерь evidence и **без rebase-merge-conflicts**. 8 чистых коммитов в chronological order значительно лучше чем 5 с переставленными местами, вызвавшими конфликты. Если конфликт в rebase — это сигнал, что план был слишком агрессивный → abort, упростить план.

## Quality gate `HISTORY_CLEAN`

Считается зелёным, если:

1. **Каждый коммит ветки несёт substantive change** (не «починка предыдущего»).
2. **Commit messages** соответствуют [conventional commits](https://www.conventionalcommits.org/) стилю проекта (`<type>(<scope>): <subject>` + body с «почему»).
3. **CI/test gate зелёный для итоговой логической серии**; если проверяется самостоятельная cherry-pick/revert пригодность каждого commit, допустим `git rebase --exec` до freeze.
4. **Diff vs `<target-ref>` сохранён** (для stacked PR это parent feature branch; rebase не привёл к потере/добавлению строк).
5. **Backup-ветка существует** для безопасного rollback: `backup/<branch>-<date>`.

## Когда чистить

- После implementation/tests/docs и перед `CANDIDATE_FROZEN`.
- После каждой существенной hotfix-серии (>3 hotfix-ов подряд на одну фичу).
- Перед обычным push/PR; после freeze/review history rewrite запрещён без нового candidate и повторных attestations всех обязательных reviewers (ADR-0015), а после публикации — также без нового PR evidence comment и CI run (ADR-0015).

Исключение — **tree-preserving rewrite**: если после squash/rebase итоговое дерево совпадает с аттестованным (`git rev-parse HEAD^{tree}`) и `git diff <backup-ref>..HEAD` пуст, ревьюерам нечего перепроверять — содержимое кандидата не изменилось. Аттестации остаются в силе, меняется только head. Требуется приложить доказательство: старый и новый head, совпадающий tree SHA и пустой diff с backup-веткой.

## Жизненный цикл служебных веток

Служебные ветки и worktree сами себя не убирают, поэтому у каждой есть срок жизни, а уборку делает `bash .agents/hooks/git-tidy.sh --apply`. Без `--apply` скрипт только печатает план; на старте сессии хук показывает его, если убирать есть что.

| Что | Откуда | Живёт до |
|---|---|---|
| `.claude/worktrees/agent-*` и ветка `worktree-agent-*` | worktree, в котором subagent делал read-only пробы; ревьюер делает в нём checkout кандидата, и инструмент перестаёт считать его неизменённым | получения вердикта: оркестратор, собрав все вердикты раунда, запускает `git-tidy.sh --apply --unlock` — только когда не работает ни один subagent, иначе `--unlock` снимет worktree из-под живого агента |
| `backup/<branch>-<date>` | этот rule перед переписыванием истории | merge PR ветки `<branch>` в основную ветку |
| локальная feature-ветка | работа над PR | merge её PR |

Скрипт не теряет работу, и всё сомнительное остаётся в отчёте как «оставлено»: worktree с незакоммиченными правками, с игнорируемыми файлами (кроме пересоздаваемых кэшей вроде `__pycache__` и `.coverage`) или с коммитами агента — любыми, созданными в этом worktree, а не только текущим HEAD; ветка с коммитами, которых нет на remote и в остающихся ветках. Ветки из того же плана на удаление и backup чужие коммиты не защищают — иначе две удаляемые ветки с общим неотправленным коммитом прикрыли бы друг друга. Исключение — сам backup: его коммиты уникальны по построению, и он удаляется по факту merge PR. Влитым PR считается только по merge-коммиту GitHub `Merge pull request #N from <owner>/<branch>` от владельца origin (если origin — GitHub), и этот merge должен быть не старше самой ветки или backup — имя ветки бывает повторным. Amend или rebase внутри worktree агента оставляют в его reflog уникальный прежний коммит, и такой worktree остаётся «с коммитами агента», пока его не уберут вручную — в worktree для read-only проб так быть не должно. Ветка, которая просто стала предком основной, не влита — так выглядит и пустая новая ветка. Remote-ветки скрипт не трогает.

## Кто исполняет

- Каноническая роль `.agents/roles/git-historian.md`; Claude и Codex запускают её через свои тонкие адаптеры.
- Если отдельная роль недоступна — Validator/root выполняет тот же audit.
- Slash-команда: `/git-cleanup` (TBD).
- Вручную через `git rebase -i <target-ref>` — если ты уверен в действиях.

## Что НЕ делать

- 🔴 НЕ force-push в `master` / `main` / `dev` (даже с `--force-with-lease`).
- 🔴 НЕ амендить коммиты, которые уже в master (только в feature-ветке).
- 🔴 НЕ использовать `--no-verify` / `--no-gpg-sign` при reword.
- 🔴 НЕ объединять коммиты, если их diff конфликтует семантически (теряется evidence о промежуточных решениях).
- 🔴 НЕ удалять коммиты с уникальной информацией в commit message только ради «красивости».
- 🔴 НЕ делать reorder коммитов, трогающих одни и те же файлы — это главный источник rebase-merge-conflicts. Проверяй пересечение файлов через `git show --stat` перед reorder. Если есть пересечение — оставляй chronological order.
- 🔴 НЕ разрешать rebase-merge-conflicts вручную внутри `git rebase` — это звонок что план неверный. `git rebase --abort`, пересмотри план менее агрессивно (меньше squash, больше keep-as-is).

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

- `.agents/roles/git-historian.md` — исполнитель.
- `docs/aidd/quality-gates.md` — gate `HISTORY_CLEAN`.
- `AGENTS.md` §git contract.
- [Conventional Commits](https://www.conventionalcommits.org/).
