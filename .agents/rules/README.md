# Canonical rules

Файлы в этом каталоге содержат нормативные правила и явный `Применимо к` scope. Tool adapters могут повторить только machine-readable glob/path scope, не содержание правила.

Agent читает `AGENTS.md`, затем все matching rules из этого каталога, затем роль или команду, если задача их активирует.
