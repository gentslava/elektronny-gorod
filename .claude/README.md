# Claude Code adapters

Этот каталог содержит только Claude-specific discovery metadata, settings и
launch adapters:

- `agents/` → canonical `.agents/roles/`;
- `rules/` → canonical `.agents/rules/`;
- `commands/` → canonical `.agents/commands/`;
- `hooks/` → canonical `.agents/hooks/`;
- `settings.json` → Claude permissions и lifecycle wiring.

Общий contract импортируется корневым `CLAUDE.md` из `AGENTS.md`. Изменения
поведения вносятся в `.agents/**`, а здесь меняется только Claude wiring.
