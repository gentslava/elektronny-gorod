"""Regression tests for the audit reconciliation shell gate."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

import custom_components.elektronny_gorod  # noqa: F401  # load patch targets


REPO_ROOT = Path(__file__).parents[1]
HOOKS = (
    REPO_ROOT / ".agents/hooks/check-audit-reconciliation.sh",
    REPO_ROOT / ".claude/hooks/check-audit-reconciliation.sh",
    REPO_ROOT / ".codex/hooks/check-audit-reconciliation.sh",
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_audit(repo: Path, status: str) -> None:
    audit = repo / "docs/audit/project-audit.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        "# Audit\n\n"
        "### A-01. Test finding\n\n"
        f"- **Status:** {status}\n"
        "- **Evidence:** deterministic fixture.\n"
    )


def _init_repo(tmp_path: Path, status: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _write_audit(repo, status)
    _git(repo, "add", "docs/audit/project-audit.md")
    _git(repo, "commit", "-m", "docs: seed audit")
    return repo


def _run_hook(repo: Path, hook: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(hook)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("hook", HOOKS)
def test_reconciliation_accepts_resolved_inherited_from_master(
    tmp_path: Path, hook: Path
) -> None:
    repo = _init_repo(tmp_path, "✅ **RESOLVED**.\n")
    _git(repo, "switch", "-c", "feature")

    result = _run_hook(repo, hook)

    assert result.returncode == 0, result.stdout
    assert "legacy RESOLVED inherited from master: 1" in result.stdout


@pytest.mark.parametrize("hook", HOOKS)
def test_reconciliation_rejects_new_resolved_without_evidence(
    tmp_path: Path, hook: Path
) -> None:
    repo = _init_repo(tmp_path, "🔴 **OPEN**.\n")
    _git(repo, "switch", "-c", "feature")
    _write_audit(repo, "✅ **RESOLVED**.\n")

    result = _run_hook(repo, hook)

    assert result.returncode == 1
    assert "RESOLVED без commit SHA" in result.stdout


@pytest.mark.parametrize("hook", HOOKS)
def test_reconciliation_rejects_non_ancestor_sha(
    tmp_path: Path, hook: Path
) -> None:
    repo = _init_repo(tmp_path, "🔴 **OPEN**.\n")
    tree = _git(repo, "rev-parse", "master^{tree}")
    unrelated = _git(repo, "commit-tree", tree, "-m", "unrelated evidence")
    _git(repo, "switch", "-c", "feature")
    _write_audit(repo, f"✅ **RESOLVED** — commit `{unrelated}`.\n")

    result = _run_hook(repo, hook)

    assert result.returncode == 1
    assert f"commit {unrelated} НЕ в master" in result.stdout


@pytest.mark.parametrize("hook", HOOKS)
@pytest.mark.parametrize(
    "status",
    (
        "🟢 **resolved-in-branch** — pending merge feature.",
        "🟢 **RESOLVED-IN-BRANCH** — pending merge feature.",
    ),
)
def test_reconciliation_reports_pending_branch_status_case_insensitively(
    tmp_path: Path, hook: Path, status: str
) -> None:
    repo = _init_repo(tmp_path, "🔴 **OPEN**.\n")
    _git(repo, "switch", "-c", "feature")
    _write_audit(repo, status)

    result = _run_hook(repo, hook)

    assert result.returncode == 0, result.stdout
    assert "resolved-in-branch findings: 1" in result.stdout
    assert "pending findings remain open" in result.stdout
    assert "Reconciliation clean" not in result.stdout


@pytest.mark.parametrize("hook", HOOKS)
def test_reconciliation_rejects_unknown_green_status(
    tmp_path: Path, hook: Path
) -> None:
    repo = _init_repo(tmp_path, "🔴 **OPEN**.\n")
    _git(repo, "switch", "-c", "feature")
    _write_audit(repo, "🟢 **READY** — ambiguous green state.\n")

    result = _run_hook(repo, hook)

    assert result.returncode == 1
    assert "Неверный зелёный status" in result.stdout


@pytest.mark.parametrize("hook", HOOKS)
def test_reconciliation_reports_remediation_in_review_as_open(
    tmp_path: Path, hook: Path
) -> None:
    repo = _init_repo(tmp_path, "🔴 **OPEN**.\n")
    _git(repo, "switch", "-c", "feature")
    audit = repo / "docs/audit/project-audit.md"
    audit.write_text(
        "# Audit\n\n"
        "- **🟡 REMEDIATION-IN-REVIEW** — candidate lifecycle is incomplete.\n\n"
        "### A-01. Test finding\n\n"
        "- **Status:** 🟡 **REMEDIATION-IN-REVIEW** — reviews pending.\n"
    )

    result = _run_hook(repo, hook)

    assert result.returncode == 0, result.stdout
    assert "remediation-in-review findings: 1" in result.stdout
    assert "pending findings remain open" in result.stdout
    assert "Reconciliation clean" not in result.stdout
