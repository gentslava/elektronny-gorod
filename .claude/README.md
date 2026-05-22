# .claude/

Конфигурация Claude Code для проекта `elektronny-gorod`. Часть Full AIDD.

## Содержимое

```
.claude/
├── README.md                    ← этот файл
├── settings.json                ← permissions + hooks для проекта
├── agents/                      ← 5 субагентов (роли)
│   ├── lead-architect.md
│   ├── ha-expert.md
│   ├── security-auditor.md
│   ├── qa-engineer.md
│   └── docs-keeper.md
├── commands/                    ← slash-команды
│   ├── audit.md
│   ├── test-config-flow.md
│   ├── security-check.md
│   ├── docs-update.md
│   └── release-check.md
├── rules/                       ← path-specific правила
│   ├── no-secret-logs.md
│   ├── coordinator-pattern.md
│   ├── ha-best-practices.md
│   ├── test-coverage.md
│   └── async-rules.md
└── hooks/                       ← shell-хуки
    ├── post-edit-redaction-check.sh
    └── pre-commit-hassfest.sh
```

## settings.json

Содержит allow-list разрешённых Bash/MCP-команд и регистрирует hooks. См. [`../docs/aidd/mcp-tools.md`](../docs/aidd/mcp-tools.md).

Не коммитить `settings.local.json` — это пользовательские overrides.

## Когда что использовать

- **Сложная задача** → активировать релевантный subagent через `Agent` tool.
- **Повторяющаяся процедура** → slash-команда (`/audit`, `/security-check`, …).
- **Деталь, специфичная для области** → правило из `rules/` (читать перед изменением соответствующих файлов).
- **Безопасность по умолчанию** → hooks (срабатывают автоматически).

## Описание

Полная методология — в [`../docs/aidd/multi-agent-workflow.md`](../docs/aidd/multi-agent-workflow.md), [`../docs/aidd/skills.md`](../docs/aidd/skills.md), [`../docs/aidd/prompt-library.md`](../docs/aidd/prompt-library.md).
