#!/usr/bin/env bash
# Canonical cross-tool entrypoint for the secret-log scanner.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
COMMON_GIT_DIR="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)"
COMMON_ROOT="$(dirname "$COMMON_GIT_DIR")"

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif [[ -x "$COMMON_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$COMMON_ROOT/.venv/bin/python"
else
    PYTHON_BIN="${PYTHON:-python3}"
fi

cd "$REPO_ROOT"
exec "$PYTHON_BIN" .agents/hooks/check-secret-logs.py "$@"
