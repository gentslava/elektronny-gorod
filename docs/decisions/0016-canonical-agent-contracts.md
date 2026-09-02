# ADR-0016: Нейтральный source of truth для agent contracts

- **Status:** accepted
- **Date:** 2026-08-14
- **Owner:** [@gentslava](https://github.com/gentslava) + Lead Architect Agent
- **Supersedes:** ADR-0004 §5 только в части размещения hook implementation
- **Refines:** ADR-0015 в части cross-tool размещения process contracts

## Context

Роли, правила и процедуры одновременно существовали в `.claude/**`, `.codex/**`, `.cursor/**`, Copilot instructions и command skills. Одно изменение требовало синхронной правки нескольких почти одинаковых файлов. Копии уже расходились, а Markdown links зависели от глубины каталога и порождали цепочки `../../..` при переносе текста между tools.

Инструменты при этом действительно требуют разные discovery formats. Claude
Code использует `CLAUDE.md`, Markdown subagents/rules/commands и settings hooks; Codex читает `AGENTS.md` и TOML agent profiles. Эти форматы являются runtime metadata, но не основанием хранить несколько версий поведения.

## Decision

### 1. Общий контракт и специализации разделены

- `AGENTS.md` — repository-wide contract.
- `.agents/roles/*.md` — единственное полное описание ролей.
- `.agents/rules/*.md` — единственное полное описание правил.
- `.agents/commands/*.md` — единственное полное описание процедур.
- `.agents/hooks/*` — единственная реализация cross-tool executable gates.

### 2. Tool-specific файлы являются adapters

`.claude/**`, `.codex/**`, `.cursor/**`, `.github/copilot-instructions.md` и `.agents/skills/source-command-*` могут хранить только обязательные discovery metadata, path/glob scope и launch wiring. Каждый adapter указывает точный repository-root-relative canonical path и требует прочитать его полностью.

Claude root adapter использует нативный `@AGENTS.md`. Claude agent frontmatter, command `allowed-tools`, rule discovery и settings остаются в `.claude/**`.
Codex agent `name`, `description` и `developer_instructions` остаются в `.codex/agents/*.toml`.

`description` — единственное поле, которое приходится хранить в нескольких местах: инструменты читают его буквально (Claude выбирает по нему субагента, Codex подставляет в профиль), поэтому заменить ссылкой на канон его нельзя. Написан он один раз — в каноническом `.agents/roles/*.md`, а adapters обязаны копировать его дословно; расхождение падает в contract tests. Подробное правило «когда применять роль» вынесено в канонический `use_when` и в adapters не копируется вовсе.

### 3. Пути не зависят от глубины adapter-а

В agent contracts используются пути от корня репозитория в backticks. Parent relative Markdown links вида `](../../../...)` в canonical и adapter layers запрещены. Это исключает path drift при переносе файла между tools.

### 4. Drift блокируется contract tests

Tests проверяют одинаковый набор canonical/Claude/Codex ролей, дословное совпадение `description` каждой роли между каноном и обоими adapters, присутствие `use_when` в каноне и его отсутствие в adapters, точную ссылку каждого adapter-а, ограничение его размера, command mapping, отсутствие parent relative links и canonical hook placement. Нормативные invariants проверяются в `.agents/**`, а не повторно в каждом tool adapter.

## Consequences

### Positive

- Изменение роли, правила, команды или gate делается один раз.
- Claude/Codex/Cursor/Copilot получают одинаковое поведение.
- Tool-specific capabilities сохраняются без копирования policy.
- Пути переживают перенос adapters между каталогами.

### Negative

- Tool без механизма include должен сначала явно прочитать canonical file.
- Discovery metadata всё ещё существует в нескольких форматах.
- Добавление новой роли требует создать два коротких discovery adapter-а.

### Mitigation

- Adapters содержат прямую инструкцию прочитать canonical path полностью.
- Contract tests проверяют parity и не дают превратить adapters в новые копии.
- `.agents/README.md` документирует mapping каталогов.

## Alternatives considered

1. **Считать `.claude/**` каноническим.** Отклонено: источник истины становится привязан к одному runtime и снова создаёт глубокие relative paths для Codex.
2. **Использовать symlinks.** Отклонено: discovery и поддержка symlinks различаются между tools и платформами; metadata formats всё равно несовместимы.
3. **Генерировать adapters с copied body.** Отклонено: generated copies остаются drift-prone и усложняют review diff.

## Sources

- Claude Code memory/imports: <https://code.claude.com/docs/en/memory>
- Claude Code subagents: <https://code.claude.com/docs/en/sub-agents>
- Codex `AGENTS.md`: <https://learn.chatgpt.com/docs/agent-configuration/agents-md>
- Codex custom agents: <https://learn.chatgpt.com/docs/agent-configuration/subagents>

## Supersedes / Superseded by

- supersedes: ADR-0004 §5 только в части tool-specific hook path;
- superseded by: —.

## Notes

- Process finding: A-97.
- Production code интеграции не меняется.
