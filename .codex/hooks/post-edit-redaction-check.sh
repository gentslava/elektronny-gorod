#!/usr/bin/env bash
# Hook: post-edit-redaction-check.sh
# Срабатывает после Edit / Write в custom_components/.
# Блокирует, если в файле есть прямое логирование sensitive ключей.
#
# Установка: автоматическая через .claude/settings.json (PostToolUse matcher: Edit|Write).
# См. также: docs/decisions/0004-token-redaction.md
# См. также: .claude/rules/no-secret-logs.md

set -uo pipefail

# Путь может прийти как $1. Штатный PostToolUse не передаёт
# positional argument, поэтому при пустом $1 запускаем full-tree scan.
FILE="${1:-}"

# Если путь известен, триггер нужен только для integration Python.
if [[ -n "$FILE" && ! "$FILE" =~ custom_components/elektronny_gorod/.*\.py$ ]]; then
    exit 0
fi

if [[ -n "$FILE" && ! -f "$FILE" ]]; then
    exit 0
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
if [[ -n "$FILE" ]]; then
    exec bash "$REPO_ROOT/.codex/hooks/check-secret-logs.sh" "$FILE"
fi
exec bash "$REPO_ROOT/.codex/hooks/check-secret-logs.sh"
