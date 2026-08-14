# Canonical roles

Каждый `*.md` — полный cross-tool контракт одной роли. Имена файлов обязаны
совпадать с Claude adapter `.claude/agents/{name}.md` и Codex adapter
`.codex/agents/{name}.toml`.

Required discovery metadata остаются в adapters; нормативные обязанности,
constraints, output и hand-off описываются только здесь.
