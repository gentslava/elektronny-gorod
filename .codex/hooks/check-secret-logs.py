#!/usr/bin/env python3
"""Codex adapter for the canonical secret-log scanner."""

from pathlib import Path
import runpy


REPO_ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(
    str(REPO_ROOT / ".agents" / "hooks" / "check-secret-logs.py"),
    run_name="__main__",
)
