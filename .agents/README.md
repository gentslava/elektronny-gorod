# Cross-tool agent contracts

Этот каталог — нейтральный source of truth для инструкций, которые должны одинаково работать в Claude Code, Codex, Cursor, Copilot и других agents.

- `roles/` — поведение специализированных ролей;
- `rules/` — инженерные и process rules;
- `commands/` — процедуры команд;
- `hooks/` — исполняемые cross-tool gates;
- `skills/source-command-*` — только adapters для discovery команд как skills.

Tool-specific каталоги хранят только metadata и wiring. Изменение поведения начинается здесь и затем, при необходимости, обновляет только ссылки adapters.
