"""Regression tests for cross-tool AIDD operational contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

import custom_components.elektronny_gorod  # noqa: F401  # load patch targets


REPO_ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


@pytest.mark.parametrize(
    "relative_path",
    (
        ".claude/commands/release-check.md",
        ".agents/skills/source-command-release-check/SKILL.md",
    ),
)
def test_release_check_is_bound_to_candidate_sha(relative_path: str) -> None:
    text = _read(relative_path)

    assert "headRefOid" in text
    assert "git rev-parse HEAD" in text
    assert "gh pr checks --watch" in text
    assert "gh run list --branch master" not in text


@pytest.mark.parametrize(
    "relative_path",
    (
        ".claude/commands/git-cleanup.md",
        ".agents/skills/source-command-git-cleanup/SKILL.md",
        ".claude/commands/docs-update.md",
        ".agents/skills/source-command-docs-update/SKILL.md",
    ),
)
def test_operational_adapters_support_target_ref(relative_path: str) -> None:
    text = _read(relative_path)

    assert "<target-ref>" in text
    assert "merge-base HEAD master" not in text
    assert "master..HEAD" not in text


@pytest.mark.parametrize(
    "relative_path",
    (
        ".claude/agents/code-reviewer.md",
        ".claude/agents/docs-keeper.md",
        ".claude/agents/ha-expert.md",
        ".claude/agents/qa-engineer.md",
        ".claude/agents/security-auditor.md",
        ".codex/agents/code-reviewer.toml",
        ".codex/agents/docs-keeper.toml",
        ".codex/agents/ha-expert.toml",
        ".codex/agents/qa-engineer.toml",
        ".codex/agents/security-auditor.toml",
    ),
)
def test_final_reviewer_profiles_share_candidate_invariants(
    relative_path: str,
) -> None:
    text = _read(relative_path)

    assert "base/head/tree" in text
    assert "Participated in implementation: no" in text
    assert "Critical/Important" in text
    assert "delta-scoped" in text
    assert "кажд" in text


def test_plans_are_tool_independent() -> None:
    for plan in (REPO_ROOT / "docs/plans").glob("*.md"):
        if plan.name == "README.md":
            continue
        assert "superpowers:" not in plan.read_text(), plan


def test_live_hook_docs_use_canonical_implementation() -> None:
    text = "\n".join(
        (
            _read("docs/aidd/mcp-tools.md"),
            _read("docs/roadmap.md"),
            _read(".claude/README.md"),
        )
    )

    assert "pre-commit-redaction-check.sh" not in text
    assert ".codex/hooks/check-secret-logs.sh" in text
