# Claude Code adapter

@AGENTS.md

## Claude-specific discovery

- `.claude/agents/*.md` keeps Claude subagent frontmatter and delegates to `.agents/roles/*.md`.
- `.claude/rules/*.md` delegates to matching canonical files in `.agents/rules/*.md`.
- `.claude/commands/*.md` exposes slash commands backed by `.agents/commands/*.md`.
- `.claude/settings.json` wires Claude lifecycle events to launch adapters in `.claude/hooks/`; implementations live in `.agents/hooks/`.

Claude-specific metadata and wiring belong in `.claude/**`; shared policy does not. Always resolve repository paths from the repository root.
