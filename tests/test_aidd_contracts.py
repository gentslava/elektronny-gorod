"""Regression tests for cross-tool AIDD operational contracts."""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

import custom_components.elektronny_gorod  # noqa: F401  # load patch targets


REPO_ROOT = Path(__file__).parents[1]
CANONICAL_ROLES = REPO_ROOT / ".agents/roles"
CANONICAL_COMMANDS = REPO_ROOT / ".agents/commands"
CANONICAL_RULES = REPO_ROOT / ".agents/rules"


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


def _role_names(directory: Path, suffix: str) -> set[str]:
    return {
        path.name.removesuffix(suffix)
        for path in directory.glob(f"*{suffix}")
        if path.name != "README.md"
    }


def test_tool_role_adapters_match_canonical_roles() -> None:
    canonical = _role_names(CANONICAL_ROLES, ".md")
    claude = _role_names(REPO_ROOT / ".claude/agents", ".md")
    codex = _role_names(REPO_ROOT / ".codex/agents", ".toml")

    assert canonical
    assert claude == canonical
    assert codex == canonical


def test_tool_command_adapters_match_canonical_commands() -> None:
    canonical = _role_names(CANONICAL_COMMANDS, ".md")
    claude = _role_names(REPO_ROOT / ".claude/commands", ".md")
    skills = {
        path.parent.name.removeprefix("source-command-")
        for path in (REPO_ROOT / ".agents/skills").glob(
            "source-command-*/SKILL.md"
        )
    }

    assert canonical
    assert claude == canonical
    assert skills == canonical


def test_claude_rule_adapters_match_canonical_rules() -> None:
    canonical = _role_names(CANONICAL_RULES, ".md")
    claude = _role_names(REPO_ROOT / ".claude/rules", ".md")

    assert canonical
    assert claude == canonical
    for rule_name in canonical:
        adapter = _read(f".claude/rules/{rule_name}.md")
        assert f".agents/rules/{rule_name}.md" in adapter
        assert len(adapter.splitlines()) <= 16


@pytest.mark.parametrize(
    "role_name",
    sorted(_role_names(CANONICAL_ROLES, ".md")),
)
def test_role_adapters_are_thin_and_point_to_canonical_role(
    role_name: str,
) -> None:
    canonical_path = f".agents/roles/{role_name}.md"
    claude_text = _read(f".claude/agents/{role_name}.md")
    codex_path = REPO_ROOT / f".codex/agents/{role_name}.toml"
    codex_text = codex_path.read_text()
    codex_config = tomllib.loads(codex_text)

    assert canonical_path in claude_text
    assert canonical_path in codex_config["developer_instructions"]
    assert "AGENTS.md" in claude_text
    assert "AGENTS.md" in codex_config["developer_instructions"]
    assert len(claude_text.splitlines()) <= 10
    assert len(codex_text.splitlines()) <= 8


def test_release_check_is_bound_to_candidate_sha() -> None:
    text = _read(".agents/commands/release-check.md")

    assert "headRefOid" in text
    assert "git rev-parse HEAD" in text
    assert "gh pr checks --watch" in text
    assert "gh run list --branch master" not in text


@pytest.mark.parametrize(
    "relative_path",
    (
        ".agents/commands/git-cleanup.md",
        ".agents/commands/docs-update.md",
    ),
)
def test_operational_commands_support_target_ref(relative_path: str) -> None:
    text = _read(relative_path)

    assert "<target-ref>" in text
    assert "merge-base HEAD master" not in text
    assert "master..HEAD" not in text


@pytest.mark.parametrize(
    "command_name",
    sorted(_role_names(CANONICAL_COMMANDS, ".md")),
)
def test_command_adapters_delegate_without_copying_procedure(
    command_name: str,
) -> None:
    canonical_path = f".agents/commands/{command_name}.md"
    claude_text = _read(f".claude/commands/{command_name}.md")
    skill_text = _read(
        f".agents/skills/source-command-{command_name}/SKILL.md"
    )

    assert canonical_path in claude_text
    assert canonical_path in skill_text
    assert len(claude_text.splitlines()) <= 9
    assert len(skill_text.splitlines()) <= 10


@pytest.mark.parametrize(
    "role_name",
    (
        "code-reviewer",
        "docs-keeper",
        "ha-expert",
        "qa-engineer",
        "security-auditor",
    ),
)
def test_final_reviewer_roles_share_candidate_invariants(
    role_name: str,
) -> None:
    text = _read(f".agents/roles/{role_name}.md")

    assert "base/head/tree" in text
    assert "Participated in implementation: no" in text
    assert "Critical/Important" in text
    assert "delta-scoped" in text
    assert "кажд" in text


def test_instruction_adapters_have_no_parent_relative_markdown_paths() -> None:
    roots = (
        REPO_ROOT / ".agents",
        REPO_ROOT / ".claude",
        REPO_ROOT / ".codex",
        REPO_ROOT / ".cursor",
    )
    files = [REPO_ROOT / ".github/copilot-instructions.md"]
    for root in roots:
        files.extend(path for path in root.rglob("*") if path.is_file())

    for path in files:
        if path.suffix not in {".md", ".mdc", ".toml"}:
            continue
        assert "](../" not in path.read_text(), path.relative_to(REPO_ROOT)


def test_claude_imports_repository_contract() -> None:
    text = _read("CLAUDE.md")

    assert "@AGENTS.md" in text
    assert "## Boundaries" not in text


def test_hook_launchers_delegate_to_canonical_implementations() -> None:
    for tool_name in (".claude", ".codex"):
        for adapter in (REPO_ROOT / tool_name / "hooks").glob("*.sh"):
            text = adapter.read_text()
            canonical_path = f".agents/hooks/{adapter.name}"
            assert (REPO_ROOT / canonical_path).is_file()
            assert canonical_path in text
            assert len(text.splitlines()) <= 10

    python_adapter = _read(".codex/hooks/check-secret-logs.py")
    assert '".agents" / "hooks" / "check-secret-logs.py"' in python_adapter
    assert len(python_adapter.splitlines()) <= 12


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
    assert ".agents/hooks/check-secret-logs.sh" in text
