#!/usr/bin/env bash
# Claude adapter for the canonical cleanup of agent worktrees and service branches.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
exec bash "$REPO_ROOT/.agents/hooks/git-tidy.sh" "$@"
