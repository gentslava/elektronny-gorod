#!/usr/bin/env bash
# Canonical hook: post-edit-markdown-wrap.sh
# Срабатывает после Edit / Write в markdown. Ловит перенос посреди фразы.
#
# Установка: через adapters в .claude/hooks и .codex/hooks (PostToolUse).
# См. также: .agents/rules/markdown-formatting.md

set -uo pipefail

# Путь может прийти как $1. Штатный PostToolUse positional argument не
# передаёт, поэтому при пустом $1 сканируем всё дерево.
FILE="${1:-}"

if [[ -n "$FILE" && ! "$FILE" =~ \.md$ ]]; then
    exit 0
fi
if [[ -n "$FILE" && ! -f "$FILE" ]]; then
    exit 0
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
if [[ -n "$FILE" ]]; then
    exec bash "$REPO_ROOT/.agents/hooks/check-markdown-wrap.sh" "$FILE"
fi
exec bash "$REPO_ROOT/.agents/hooks/check-markdown-wrap.sh"
