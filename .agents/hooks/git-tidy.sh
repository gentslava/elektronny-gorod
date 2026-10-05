#!/usr/bin/env bash
# Canonical cross-tool entrypoint для уборки служебных веток и worktree агентов.
# См. .agents/rules/git-history.md § «Жизненный цикл служебных веток»

set -euo pipefail

# Работает с репозиторием текущего каталога: из любого его worktree видны все.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$SCRIPT_DIR/git-tidy.py" "$@"
