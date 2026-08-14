#!/usr/bin/env bash
# Codex adapter for the canonical post-edit secret-log gate.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
exec bash "$REPO_ROOT/.agents/hooks/post-edit-redaction-check.sh" "$@"
