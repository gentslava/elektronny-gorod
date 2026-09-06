#!/usr/bin/env bash
# Codex hook adapter: срабатывает после Edit / Write в markdown.
# Реализация — .agents/hooks/check-markdown-wrap.sh

set -uo pipefail

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
